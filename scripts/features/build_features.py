#!/usr/bin/env python3
"""
FPL AI Weekly Squad Prediction System
======================================

Production-ready, leakage-safe feature builder for the normalized
FPL processed dataset.

Input:
    data/processed/<season>/
        players.csv
        teams.csv
        gameweeks.csv
        fixtures.csv
        player_gameweek.csv
        player_season_history.csv
        dataset_manifest.json

Output:
    data/features/<season>/
        player_gameweek_features.csv
        feature_manifest.json
        feature_build_report.json

Important design rule
---------------------
For a prediction row for gameweek N, every feature must be derived only
from information available BEFORE the GW N deadline.

Therefore:
    historical player performance -> rows with gameweek < N
    target outcome              -> row with gameweek == N

The target columns are kept separately from the feature columns.

This first production version deliberately avoids current aggregate fields
from players.csv and teams.csv as model features because those tables
represent the current processed state and can leak future information when
historical training rows are created.

Features are built primarily from:
    - player_gameweek.csv
    - fixtures.csv
    - gameweeks.csv
    - stable player identity/position metadata

No target outcome columns are used as predictors.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import statistics
import tempfile
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
LOG = logging.getLogger("build_features")

REQUIRED_FILES = [
    "players.csv",
    "teams.csv",
    "gameweeks.csv",
    "fixtures.csv",
    "player_gameweek.csv",
    "player_season_history.csv",
    "dataset_manifest.json",
]

PLAYER_GAMEWEEK_REQUIRED = [
    "player_id",
    "season",
    "gameweek",
    "fixture_id",
    "opponent_team",
    "was_home",
    "kickoff_time",
    "minutes",
    "total_points",
    "goals_scored",
    "assists",
    "clean_sheets",
    "goals_conceded",
    "bonus",
    "bps",
    "influence",
    "creativity",
    "threat",
    "ict_index",
    "starts",
    "expected_goals",
    "expected_assists",
    "expected_goal_involvements",
    "expected_goals_conceded",
]

FIXTURE_REQUIRED = [
    "fixture_id",
    "gameweek",
    "team_h",
    "team_a",
    "kickoff_time",
]

GAMEWEEK_REQUIRED = [
    "gameweek",
    "deadline_time",
]

PLAYER_IDENTITY_FIELDS = [
    "player_id",
    "first_name",
    "second_name",
    "web_name",
    "position_id",
    "position_name",
]

HISTORY_METRICS = [
    "minutes",
    "total_points",
    "goals_scored",
    "assists",
    "clean_sheets",
    "goals_conceded",
    "bonus",
    "bps",
    "influence",
    "creativity",
    "threat",
    "ict_index",
    "starts",
    "expected_goals",
    "expected_assists",
    "expected_goal_involvements",
    "expected_goals_conceded",
]

WINDOWS = (3, 5, 10)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build leakage-safe FPL player/gameweek features."
    )
    parser.add_argument(
        "--season",
        required=True,
        help="Season in YYYY-YY format, e.g. 2026-27",
    )
    parser.add_argument(
        "--project-root",
        default=None,
        help="Project root. Defaults to the parent of scripts/.",
    )
    parser.add_argument(
        "--input-dir",
        default=None,
        help="Explicit processed dataset directory.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Explicit feature output directory.",
    )
    parser.add_argument(
        "--min-history",
        type=int,
        default=1,
        help="Minimum prior player-gameweek observations required for a row.",
    )
    parser.add_argument(
        "--include-no-history",
        action="store_true",
        help="Also emit rows with zero prior history. Useful for cold-start analysis.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only warnings/errors.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Debug logging.",
    )
    return parser.parse_args()


def configure_logging(args: argparse.Namespace) -> None:
    level = logging.DEBUG if args.verbose else logging.INFO
    if args.quiet:
        level = logging.WARNING
    logging.basicConfig(
        level=level,
        format="[%(levelname)-8s] %(message)s",
    )


def fail(message: str) -> None:
    raise RuntimeError(message)


def resolve_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    root = (
        Path(args.project_root).expanduser().resolve()
        if args.project_root
        else Path(__file__).resolve().parents[2]
    )

    input_dir = (
        Path(args.input_dir).expanduser().resolve()
        if args.input_dir
        else root / "data" / "processed" / args.season
    )

    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else root / "data" / "features" / args.season
    )

    return root, input_dir, output_dir


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        fail(f"Required file does not exist: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            fail(f"CSV has no header: {path}")

        fields = list(reader.fieldnames)
        rows = []
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                fail(f"{path}: extra fields on line {row_number}")
            rows.append({k: ("" if v is None else v) for k, v in row.items()})
        return fields, rows


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"Cannot parse JSON {path}: {exc}")


def require_columns(
    filename: str,
    fields: list[str],
    required: list[str],
) -> None:
    missing = [c for c in required if c not in fields]
    if missing:
        fail(
            f"{filename}: missing required columns: {', '.join(missing)}"
        )


def to_int(value: Any, default: int | None = None) -> int | None:
    if value is None or str(value).strip() == "":
        return default
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def to_float(value: Any, default: float | None = None) -> float | None:
    if value is None or str(value).strip() == "":
        return default
    try:
        number = float(str(value).strip())
        if not math.isfinite(number):
            return default
        return number
    except (TypeError, ValueError):
        return default


def bool_value(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes"}:
        return 1
    if text in {"0", "false", "no"}:
        return 0
    return None


def mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def sum_values(values: list[float]) -> float:
    return float(sum(values))


def safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def weighted_recent_mean(values: list[float]) -> float | None:
    """
    Recency-weighted mean.

    values are ordered oldest -> newest.
    Newer observations receive larger linear weights.
    """
    if not values:
        return None
    weights = list(range(1, len(values) + 1))
    denominator = sum(weights)
    return sum(v * w for v, w in zip(values, weights)) / denominator


def build_fixture_index(
    fixtures: list[dict[str, str]],
) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}

    for row in fixtures:
        fixture_id = to_int(row.get("fixture_id"))
        if fixture_id is None:
            continue

        team_h = to_int(row.get("team_h"))
        team_a = to_int(row.get("team_a"))
        gameweek = to_int(row.get("gameweek"))

        if team_h is None or team_a is None:
            continue

        result[fixture_id] = {
            "fixture_id": fixture_id,
            "gameweek": gameweek,
            "team_h": team_h,
            "team_a": team_a,
            "team_h_difficulty": to_float(row.get("team_h_difficulty")),
            "team_a_difficulty": to_float(row.get("team_a_difficulty")),
            "kickoff_time": row.get("kickoff_time", ""),
        }

    return result


def derive_player_team(
    fixture: dict[str, Any],
    player_row: dict[str, Any],
) -> tuple[int | None, int | None, float | None]:
    """
    Return:
        player_team_id,
        opponent_team_id,
        fixture_difficulty

    The player's own team is derived from the fixture and was_home rather
    than from players.csv, avoiding use of today's team assignment.
    """
    was_home = bool_value(player_row.get("was_home"))

    if was_home == 1:
        return (
            fixture["team_h"],
            fixture["team_a"],
            fixture.get("team_h_difficulty"),
        )

    if was_home == 0:
        return (
            fixture["team_a"],
            fixture["team_h"],
            fixture.get("team_a_difficulty"),
        )

    opponent = to_int(player_row.get("opponent_team"))
    return None, opponent, None


def normalize_history_rows(
    rows: list[dict[str, str]],
    fixture_index: dict[int, dict[str, Any]],
    season: str,
) -> dict[int, list[dict[str, Any]]]:
    """
    Normalize player-gameweek records and attach team/opponent information
    from the authoritative fixture table.

    Returns player_id -> chronologically sorted history.
    """
    by_player: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for raw in rows:
        if raw.get("season", "").strip() != season:
            continue

        player_id = to_int(raw.get("player_id"))
        gameweek = to_int(raw.get("gameweek"))
        fixture_id = to_int(raw.get("fixture_id"))

        if player_id is None or gameweek is None or fixture_id is None:
            continue

        fixture = fixture_index.get(fixture_id)
        if fixture is None:
            LOG.warning(
                "Skipping player %s GW%s: fixture %s not found.",
                player_id,
                gameweek,
                fixture_id,
            )
            continue

        team_id, opponent_team_id, fixture_difficulty = derive_player_team(
            fixture, raw
        )

        normalized: dict[str, Any] = {
            "player_id": player_id,
            "season": season,
            "gameweek": gameweek,
            "fixture_id": fixture_id,
            "team_id": team_id,
            "opponent_team_id": opponent_team_id,
            "was_home": bool_value(raw.get("was_home")),
            "kickoff_time": raw.get("kickoff_time") or fixture.get("kickoff_time"),
            "fixture_difficulty": fixture_difficulty,
        }

        for metric in HISTORY_METRICS:
            normalized[metric] = to_float(raw.get(metric))

        # Integer-like fields should remain clean numeric values.
        normalized["minutes"] = to_int(raw.get("minutes"))
        normalized["starts"] = to_int(raw.get("starts"))

        by_player[player_id].append(normalized)

    for player_id in by_player:
        by_player[player_id].sort(
            key=lambda r: (
                r["gameweek"],
                r["kickoff_time"] or "",
                r["fixture_id"],
            )
        )

    return by_player


def historical_slice(
    history: list[dict[str, Any]],
    target_gameweek: int,
) -> list[dict[str, Any]]:
    """
    Only observations strictly before the target gameweek are allowed.
    """
    return [
        row for row in history
        if row["gameweek"] < target_gameweek
    ]


def metric_values(
    history: list[dict[str, Any]],
    metric: str,
    target_gameweek: int,
) -> list[float]:
    values = []
    for row in historical_slice(history, target_gameweek):
        value = row.get(metric)
        if value is not None:
            values.append(float(value))
    return values


def last_value(
    history: list[dict[str, Any]],
    metric: str,
    target_gameweek: int,
) -> float | None:
    values = metric_values(history, metric, target_gameweek)
    return values[-1] if values else None


def rolling_sum(
    history: list[dict[str, Any]],
    metric: str,
    target_gameweek: int,
    window: int,
) -> float | None:
    values = metric_values(history, metric, target_gameweek)[-window:]
    return sum_values(values) if values else None


def rolling_mean(
    history: list[dict[str, Any]],
    metric: str,
    target_gameweek: int,
    window: int,
) -> float | None:
    values = metric_values(history, metric, target_gameweek)[-window:]
    return mean(values)


def rolling_weighted_mean(
    history: list[dict[str, Any]],
    metric: str,
    target_gameweek: int,
    window: int,
) -> float | None:
    values = metric_values(history, metric, target_gameweek)[-window:]
    return weighted_recent_mean(values)


def rolling_rate(
    history: list[dict[str, Any]],
    numerator_metric: str,
    denominator_metric: str,
    target_gameweek: int,
    window: int,
) -> float | None:
    rows = historical_slice(history, target_gameweek)[-window:]
    numerator = sum(
        float(r[numerator_metric])
        for r in rows
        if r.get(numerator_metric) is not None
    )
    denominator = sum(
        float(r[denominator_metric])
        for r in rows
        if r.get(denominator_metric) is not None
    )
    return safe_ratio(numerator, denominator)


def build_player_feature_row(
    player: dict[str, Any],
    history: list[dict[str, Any]],
    target_row: dict[str, Any],
    target_fixture: dict[str, Any],
    target_gameweek: int,
    min_history: int,
) -> dict[str, Any] | None:
    prior = historical_slice(history, target_gameweek)

    if len(prior) < min_history:
        return None

    player_id = player["player_id"]

    target_team_id, target_opponent_id, target_fdr = derive_player_team(
        target_fixture,
        target_row,
    )

    row: dict[str, Any] = {
        # Identity
        "player_id": player_id,
        "season": player.get("season"),
        "gameweek": target_gameweek,
        "web_name": player.get("web_name"),
        "position_id": player.get("position_id"),
        "position_name": player.get("position_name"),

        # Pre-match fixture information
        "team_id": target_team_id,
        "opponent_team_id": target_opponent_id,
        "was_home": bool_value(target_row.get("was_home")),
        "fixture_difficulty": target_fdr,

        # Data availability / reliability
        "prior_gameweeks": len(prior),
        "prior_minutes": sum(
            r["minutes"] for r in prior if r.get("minutes") is not None
        ),
    }

    # Last observed state.
    for metric in (
        "minutes",
        "total_points",
        "goals_scored",
        "assists",
        "clean_sheets",
        "goals_conceded",
        "bonus",
        "bps",
        "influence",
        "creativity",
        "threat",
        "ict_index",
        "starts",
        "expected_goals",
        "expected_assists",
        "expected_goal_involvements",
        "expected_goals_conceded",
    ):
        row[f"last_{metric}"] = last_value(
            history, metric, target_gameweek
        )

    for window in WINDOWS:
        # Rolling totals / means.
        for metric in (
            "total_points",
            "minutes",
            "goals_scored",
            "assists",
            "clean_sheets",
            "goals_conceded",
            "bonus",
            "bps",
            "expected_goals",
            "expected_assists",
            "expected_goal_involvements",
            "expected_goals_conceded",
        ):
            row[f"last_{window}_{metric}"] = rolling_sum(
                history, metric, target_gameweek, window
            )

        for metric in (
            "influence",
            "creativity",
            "threat",
            "ict_index",
        ):
            row[f"last_{window}_{metric}_mean"] = rolling_mean(
                history, metric, target_gameweek, window
            )

        row[f"last_{window}_points_per_game"] = safe_ratio(
            row[f"last_{window}_total_points"] or 0.0,
            min(window, len(prior)),
        )

        row[f"last_{window}_points_per_90"] = safe_ratio(
            row[f"last_{window}_total_points"] or 0.0,
            (row[f"last_{window}_minutes"] or 0.0) / 90.0,
        )

        row[f"last_{window}_xg_per_90"] = safe_ratio(
            row[f"last_{window}_expected_goals"] or 0.0,
            (row[f"last_{window}_minutes"] or 0.0) / 90.0,
        )

        row[f"last_{window}_xa_per_90"] = safe_ratio(
            row[f"last_{window}_expected_assists"] or 0.0,
            (row[f"last_{window}_minutes"] or 0.0) / 90.0,
        )

        row[f"last_{window}_start_rate"] = safe_ratio(
            row[f"last_{window}_starts"] or 0.0,
            min(window, len(prior)),
        )

        row[f"last_{window}_60_plus_rate"] = safe_ratio(
            sum(
                1
                for r in prior[-window:]
                if r.get("minutes") is not None and r["minutes"] >= 60
            ),
            min(window, len(prior)),
        )

        row[f"last_{window}_appearance_rate"] = safe_ratio(
            sum(
                1
                for r in prior[-window:]
                if r.get("minutes") is not None and r["minutes"] > 0
            ),
            min(window, len(prior)),
        )

    # Recency-weighted performance.
    row["weighted_last_5_points"] = rolling_weighted_mean(
        history, "total_points", target_gameweek, 5
    )
    row["weighted_last_5_minutes"] = rolling_weighted_mean(
        history, "minutes", target_gameweek, 5
    )
    row["weighted_last_5_xg"] = rolling_weighted_mean(
        history, "expected_goals", target_gameweek, 5
    )
    row["weighted_last_5_xa"] = rolling_weighted_mean(
        history, "expected_assists", target_gameweek, 5
    )

    # Explicit minutes reliability signals.
    row["minutes_per_appearance_last_5"] = safe_ratio(
        row["last_5_minutes"] or 0.0,
        sum(
            1
            for r in prior[-5:]
            if r.get("minutes") is not None and r["minutes"] > 0
        ),
    )

    # Recent fixture context, derived only from already completed fixtures.
    prior_fixtures = prior[-5:]
    row["recent_home_rate"] = safe_ratio(
        sum(1 for r in prior_fixtures if r.get("was_home") == 1),
        len(prior_fixtures),
    )
    row["recent_avg_fdr"] = mean(
        [
            float(r["fixture_difficulty"])
            for r in prior_fixtures
            if r.get("fixture_difficulty") is not None
        ]
    )

    # ------------------------------------------------------------------
    # Targets
    # ------------------------------------------------------------------
    # These are outcomes of the target GW and MUST NOT be used by the
    # feature calculations above.
    row["target_minutes"] = target_row.get("minutes")
    row["target_points"] = target_row.get("total_points")
    row["target_goals"] = target_row.get("goals_scored")
    row["target_assists"] = target_row.get("assists")
    row["target_clean_sheets"] = target_row.get("clean_sheets")
    row["target_bonus"] = target_row.get("bonus")
    row["target_xg"] = target_row.get("expected_goals")
    row["target_xa"] = target_row.get("expected_assists")

    return row


def output_field_order(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return []

    preferred = [
        "player_id",
        "season",
        "gameweek",
        "web_name",
        "position_id",
        "position_name",
        "team_id",
        "opponent_team_id",
        "was_home",
        "fixture_difficulty",
        "prior_gameweeks",
        "prior_minutes",
    ]

    target_fields = [
        "target_minutes",
        "target_points",
        "target_goals",
        "target_assists",
        "target_clean_sheets",
        "target_bonus",
        "target_xg",
        "target_xa",
    ]

    all_fields = list(rows[0].keys())
    middle = [
        f for f in all_fields
        if f not in preferred and f not in target_fields
    ]

    return preferred + middle + target_fields


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    fields: list[str],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=fields,
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    field: (
                        ""
                        if row.get(field) is None
                        else row.get(field)
                    )
                    for field in fields
                }
            )


def atomic_replace_directory(
    temp_dir: Path,
    final_dir: Path,
) -> None:
    backup = None

    if final_dir.exists():
        backup = final_dir.with_name(
            f".{final_dir.name}.backup-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )
        final_dir.rename(backup)

    try:
        temp_dir.rename(final_dir)
    except Exception:
        if backup and backup.exists() and not final_dir.exists():
            backup.rename(final_dir)
        raise
    else:
        if backup and backup.exists():
            shutil.rmtree(backup, ignore_errors=True)


def main() -> int:
    args = parse_args()
    configure_logging(args)

    root, input_dir, output_dir = resolve_paths(args)

    LOG.info("FPL LEAKAGE-SAFE FEATURE BUILD")
    LOG.info("=" * 72)
    LOG.info("Season       : %s", args.season)
    LOG.info("Input        : %s", input_dir)
    LOG.info("Output       : %s", output_dir)

    if not input_dir.exists():
        fail(f"Processed directory does not exist: {input_dir}")

    for filename in REQUIRED_FILES:
        if not (input_dir / filename).exists():
            fail(f"Missing required processed file: {input_dir / filename}")

    manifest = read_json(input_dir / "dataset_manifest.json")

    # Load core datasets.
    player_fields, player_rows_raw = read_csv(input_dir / "players.csv")
    fixture_fields, fixture_rows_raw = read_csv(input_dir / "fixtures.csv")
    gw_fields, gw_rows_raw = read_csv(input_dir / "gameweeks.csv")
    pgw_fields, pgw_rows_raw = read_csv(
        input_dir / "player_gameweek.csv"
    )

    require_columns(
        "players.csv",
        player_fields,
        PLAYER_IDENTITY_FIELDS,
    )
    require_columns(
        "fixtures.csv",
        fixture_fields,
        FIXTURE_REQUIRED,
    )
    require_columns(
        "gameweeks.csv",
        gw_fields,
        GAMEWEEK_REQUIRED,
    )
    require_columns(
        "player_gameweek.csv",
        pgw_fields,
        PLAYER_GAMEWEEK_REQUIRED,
    )

    # Stable player identity only.
    players: dict[int, dict[str, Any]] = {}
    for raw in player_rows_raw:
        player_id = to_int(raw.get("player_id"))
        if player_id is None:
            continue

        players[player_id] = {
            "player_id": player_id,
            "season": args.season,
            "first_name": raw.get("first_name"),
            "second_name": raw.get("second_name"),
            "web_name": raw.get("web_name"),
            "position_id": to_int(raw.get("position_id")),
            "position_name": raw.get("position_name"),
        }

    fixture_index = build_fixture_index(fixture_rows_raw)

    gameweeks = {}
    for raw in gw_rows_raw:
        gw = to_int(raw.get("gameweek"))
        if gw is None:
            continue
        gameweeks[gw] = {
            "gameweek": gw,
            "deadline_time": raw.get("deadline_time"),
        }

    histories = normalize_history_rows(
        pgw_rows_raw,
        fixture_index,
        args.season,
    )

    # Build target rows from player_gameweek records. This means the
    # resulting training dataset contains only observed gameweeks.
    target_rows_by_player: dict[int, dict[int, list[dict[str, str]]]] = (
        defaultdict(lambda: defaultdict(list))
    )

    for raw in pgw_rows_raw:
        if raw.get("season", "").strip() != args.season:
            continue
        player_id = to_int(raw.get("player_id"))
        gw = to_int(raw.get("gameweek"))
        fixture_id = to_int(raw.get("fixture_id"))

        if player_id is None or gw is None or fixture_id is None:
            continue
        if fixture_id not in fixture_index:
            continue

        target_rows_by_player[player_id][gw].append(raw)

    output_rows: list[dict[str, Any]] = []
    skipped_no_history = 0
    skipped_missing_fixture = 0
    skipped_missing_player = 0

    for player_id in sorted(target_rows_by_player):
        player = players.get(player_id)
        history = histories.get(player_id, [])

        if player is None:
            skipped_missing_player += 1
            continue

        for target_gameweek in sorted(target_rows_by_player[player_id]):
            targets = target_rows_by_player[player_id][target_gameweek]

            # A player can have multiple fixtures in a gameweek (e.g.
            # double gameweeks). Produce one prediction row per fixture.
            for target_raw in targets:
                fixture_id = to_int(target_raw.get("fixture_id"))
                if fixture_id is None:
                    skipped_missing_fixture += 1
                    continue

                target_fixture = fixture_index.get(fixture_id)
                if target_fixture is None:
                    skipped_missing_fixture += 1
                    continue

                prior = historical_slice(history, target_gameweek)

                if not prior and not args.include_no_history:
                    skipped_no_history += 1
                    continue

                feature_row = build_player_feature_row(
                    player=player,
                    history=history,
                    target_row=target_raw,
                    target_fixture=target_fixture,
                    target_gameweek=target_gameweek,
                    min_history=args.min_history,
                )

                if feature_row is not None:
                    output_rows.append(feature_row)

    # Deterministic ordering.
    output_rows.sort(
        key=lambda r: (
            r["gameweek"],
            r["player_id"],
            r.get("fixture_difficulty") or 0,
        )
    )

    fields = output_field_order(output_rows)

    # Sanity checks.
    if output_rows:
        target_fields = {
            "target_minutes",
            "target_points",
            "target_goals",
            "target_assists",
            "target_clean_sheets",
            "target_bonus",
            "target_xg",
            "target_xa",
        }

        # Feature fields must not contain target prefixes.
        feature_fields = [f for f in fields if f not in target_fields]

        leaked_names = [
            f for f in feature_fields
            if f.startswith("target_")
        ]

        if leaked_names:
            fail(
                "Potential target leakage in feature columns: "
                + ", ".join(leaked_names)
            )

    # Report by gameweek.
    rows_by_gw = defaultdict(int)
    for row in output_rows:
        rows_by_gw[int(row["gameweek"])] += 1

    report = {
        "schema_version": "1.0.0",
        "builder_version": VERSION,
        "season": args.season,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_directory": str(input_dir),
        "output_directory": str(output_dir),
        "status": "PASS",
        "source_manifest_schema_version": manifest.get("schema_version"),
        "input_counts": {
            "players": len(players),
            "fixtures": len(fixture_index),
            "gameweeks": len(gameweeks),
            "player_gameweek_rows": len(pgw_rows_raw),
        },
        "output_counts": {
            "feature_rows": len(output_rows),
            "feature_columns": len(fields),
            "gameweeks_with_rows": len(rows_by_gw),
        },
        "rows_by_gameweek": dict(sorted(rows_by_gw.items())),
        "skipped": {
            "no_history": skipped_no_history,
            "missing_fixture": skipped_missing_fixture,
            "missing_player": skipped_missing_player,
        },
        "leakage_policy": {
            "rule": (
                "For target GW N, historical features use only "
                "player-gameweek observations with gameweek < N."
            ),
            "target_columns": [
                "target_minutes",
                "target_points",
                "target_goals",
                "target_assists",
                "target_clean_sheets",
                "target_bonus",
                "target_xg",
                "target_xa",
            ],
            "current_state_tables_used_as_predictors": [],
            "fixture_outcome_fields_used_as_predictors": [],
        },
        "feature_groups": {
            "identity": [
                "player_id",
                "position_id",
                "position_name",
            ],
            "fixture": [
                "team_id",
                "opponent_team_id",
                "was_home",
                "fixture_difficulty",
            ],
            "history": [
                "last_*",
                "last_3_*",
                "last_5_*",
                "last_10_*",
            ],
            "minutes": [
                "prior_minutes",
                "last_*_minutes",
                "last_*_start_rate",
                "last_*_60_plus_rate",
                "last_*_appearance_rate",
                "minutes_per_appearance_last_5",
            ],
        },
        "notes": [
            "players.csv is used only for stable identity/position metadata.",
            "Current price, current form, current ownership and current team aggregates are intentionally excluded from historical predictors.",
            "Fixture scores and actual match outcomes are never read from fixture result fields.",
            "One row is produced per player-fixture target; double gameweeks therefore produce multiple rows.",
            "This dataset is intended for rolling/out-of-sample model training and evaluation.",
        ],
    }

    output_dir.parent.mkdir(parents=True, exist_ok=True)

    temp_dir = Path(
        tempfile.mkdtemp(
            prefix=f".{output_dir.name}.build-",
            dir=str(output_dir.parent),
        )
    )

    try:
        write_csv(
            temp_dir / "player_gameweek_features.csv",
            output_rows,
            fields,
        )

        (temp_dir / "feature_manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "builder_version": VERSION,
                    "season": args.season,
                    "generated_at_utc": report["generated_at_utc"],
                    "input_directory": str(input_dir),
                    "output_files": {
                        "player_gameweek_features.csv": {
                            "rows": len(output_rows),
                            "columns": fields,
                        }
                    },
                    "source_processed_manifest": manifest,
                    "leakage_policy": report["leakage_policy"],
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        (temp_dir / "feature_build_report.json").write_text(
            json.dumps(
                report,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        atomic_replace_directory(temp_dir, output_dir)

    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise

    LOG.info("")
    LOG.info("=" * 72)
    LOG.info("FPL FEATURE BUILD COMPLETE")
    LOG.info("=" * 72)
    LOG.info("Season                 : %s", args.season)
    LOG.info("Status                 : PASS")
    LOG.info("Players                : %d", len(players))
    LOG.info("Fixtures               : %d", len(fixture_index))
    LOG.info("Feature rows           : %d", len(output_rows))
    LOG.info("Feature columns        : %d", len(fields))
    LOG.info("Skipped no history     : %d", skipped_no_history)
    LOG.info("Skipped missing fixture: %d", skipped_missing_fixture)
    LOG.info("Skipped missing player : %d", skipped_missing_player)
    LOG.info("")
    LOG.info("Output directory:")
    LOG.info("  %s", output_dir)
    LOG.info("")
    LOG.info("Files:")
    LOG.info("  player_gameweek_features.csv")
    LOG.info("  feature_manifest.json")
    LOG.info("  feature_build_report.json")
    LOG.info("")
    LOG.info("=" * 72)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        LOG.error("Interrupted by user.")
        raise SystemExit(130)
    except Exception as exc:
        LOG.error("FEATURE BUILD FAILED: %s", exc)
        raise SystemExit(1)
