#!/usr/bin/env python3
"""
FPL AI Weekly Squad Prediction System
=====================================

Build the normalized/processed dataset from the immutable raw FPL snapshots.

This script is designed for the ACTUAL raw snapshot structure used by the
project:

data/
└── raw/
    └── 2026-27/
        ├── bootstrap/
        │   └── YYYY-MM-DD_HH-MM-SS.json
        ├── fixtures/
        │   └── YYYY-MM-DD_HH-MM-SS.json
        └── players/
            ├── 1/
            │   └── YYYY-MM-DD_HH-MM-SS.json
            ├── 2/
            │   └── YYYY-MM-DD_HH-MM-SS.json
            └── ...

The player endpoint payload is expected to contain:
    fixtures
    history
    history_past

The bootstrap payload is expected to contain:
    elements
    teams
    events
    element_types

The global fixtures endpoint is expected to return a list of fixture objects.

Outputs:
data/processed/<season>/
    players.csv
    teams.csv
    gameweeks.csv
    fixtures.csv
    player_gameweek.csv
    player_season_history.csv
    dataset_manifest.json

Design principles:
- Raw data is never modified.
- Latest valid snapshot is selected deterministically.
- CSV schemas are explicit and stable.
- IDs remain integers and are used as relationships.
- Numeric API strings are normalized to numeric values.
- Current-season player history is preserved even when empty.
- Historical season summaries from history_past are preserved.
- Referential integrity is checked before writing final outputs.
- The script is safe to run repeatedly.
- Existing processed output is replaced only after successful validation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import re
import shutil
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG = logging.getLogger("build_dataset")

SEASON_RE = re.compile(r"^\d{4}-\d{2}$")
SNAPSHOT_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.json$"
)


# ---------------------------------------------------------------------------
# Explicit output schemas
# ---------------------------------------------------------------------------

PLAYERS_FIELDS = [
    "player_id",
    "code",
    "first_name",
    "second_name",
    "web_name",
    "known_name",
    "team_id",
    "team_code",
    "position_id",
    "position_name",
    "now_cost",
    "now_cost_m",
    "cost_change_event",
    "cost_change_event_fall",
    "cost_change_start",
    "cost_change_start_fall",
    "price_change_percent",
    "total_points",
    "points_per_game",
    "form",
    "event_points",
    "ep_next",
    "ep_this",
    "selected_by_percent",
    "transfers_in",
    "transfers_in_event",
    "transfers_out",
    "transfers_out_event",
    "value_form",
    "value_season",
    "minutes",
    "starts",
    "goals_scored",
    "assists",
    "clean_sheets",
    "goals_conceded",
    "own_goals",
    "penalties_saved",
    "penalties_missed",
    "yellow_cards",
    "red_cards",
    "saves",
    "bonus",
    "bps",
    "influence",
    "creativity",
    "threat",
    "ict_index",
    "clearances_blocks_interceptions",
    "recoveries",
    "tackles",
    "defensive_contribution",
    "expected_goals",
    "expected_assists",
    "expected_goal_involvements",
    "expected_goals_conceded",
    "expected_goals_per_90",
    "expected_assists_per_90",
    "expected_goal_involvements_per_90",
    "expected_goals_conceded_per_90",
    "saves_per_90",
    "goals_conceded_per_90",
    "starts_per_90",
    "clean_sheets_per_90",
    "defensive_contribution_per_90",
    "chance_of_playing_next_round",
    "chance_of_playing_this_round",
    "status",
    "removed",
    "can_select",
    "can_transact",
    "news",
    "news_added",
    "team_join_date",
    "birth_date",
    "squad_number",
    "selected_rank",
    "selected_rank_type",
    "form_rank",
    "form_rank_type",
    "points_per_game_rank",
    "points_per_game_rank_type",
    "influence_rank",
    "influence_rank_type",
    "creativity_rank",
    "creativity_rank_type",
    "threat_rank",
    "threat_rank_type",
    "ict_index_rank",
    "ict_index_rank_type",
    "now_cost_rank",
    "now_cost_rank_type",
]

TEAMS_FIELDS = [
    "team_id",
    "code",
    "name",
    "short_name",
    "strength",
    "strength_overall_home",
    "strength_overall_away",
    "strength_attack_home",
    "strength_attack_away",
    "strength_defence_home",
    "strength_defence_away",
    "position",
    "played",
    "win",
    "draw",
    "loss",
    "points",
    "form",
    "team_division",
    "unavailable",
    "pulse_id",
]

GAMEWEEKS_FIELDS = [
    "gameweek",
    "name",
    "deadline_time",
    "deadline_time_epoch",
    "release_time",
    "release_time_epoch",
    "average_entry_score",
    "finished",
    "data_checked",
    "highest_scoring_entry",
    "highest_score",
    "is_previous",
    "is_current",
    "is_next",
    "cup_leagues_created",
    "h2h_ko_matches_created",
    "ranked_count",
    "transfers_made",
    "most_selected",
    "most_transferred_in",
    "top_element",
    "top_element_info",
    "chip_plays",
    "most_vice_captained",
    "most_captained",
]

FIXTURES_FIELDS = [
    "fixture_id",
    "code",
    "gameweek",
    "event_name",
    "team_h",
    "team_a",
    "team_h_score",
    "team_a_score",
    "team_h_difficulty",
    "team_a_difficulty",
    "finished",
    "finished_provisional",
    "started",
    "minutes",
    "provisional_start_time",
    "kickoff_time",
    "pulse_id",
]

PLAYER_GAMEWEEK_FIELDS = [
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
    "own_goals",
    "penalties_saved",
    "penalties_missed",
    "yellow_cards",
    "red_cards",
    "saves",
    "bonus",
    "bps",
    "influence",
    "creativity",
    "threat",
    "ict_index",
    "clearances_blocks_interceptions",
    "recoveries",
    "tackles",
    "defensive_contribution",
    "starts",
    "expected_goals",
    "expected_assists",
    "expected_goal_involvements",
    "expected_goals_conceded",
]

PLAYER_SEASON_HISTORY_FIELDS = [
    "player_id",
    "season",
    "element_code",
    "start_cost",
    "end_cost",
    "total_points",
    "minutes",
    "goals_scored",
    "assists",
    "clean_sheets",
    "goals_conceded",
    "own_goals",
    "penalties_saved",
    "penalties_missed",
    "yellow_cards",
    "red_cards",
    "saves",
    "bonus",
    "bps",
    "influence",
    "creativity",
    "threat",
    "ict_index",
    "clearances_blocks_interceptions",
    "recoveries",
    "tackles",
    "defensive_contribution",
    "starts",
    "expected_goals",
    "expected_assists",
    "expected_goal_involvements",
    "expected_goals_conceded",
]

OUTPUT_SCHEMAS = {
    "players.csv": PLAYERS_FIELDS,
    "teams.csv": TEAMS_FIELDS,
    "gameweeks.csv": GAMEWEEKS_FIELDS,
    "fixtures.csv": FIXTURES_FIELDS,
    "player_gameweek.csv": PLAYER_GAMEWEEK_FIELDS,
    "player_season_history.csv": PLAYER_SEASON_HISTORY_FIELDS,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build normalized FPL processed datasets from raw snapshots."
    )
    parser.add_argument(
        "--season",
        required=True,
        help="Season in YYYY-YY format, e.g. 2026-27",
    )
    parser.add_argument(
        "--project-root",
        default=None,
        help="Project root. Defaults to the parent of scripts/ when this file is in scripts/.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional explicit processed output directory.",
    )
    parser.add_argument(
        "--all-player-snapshots",
        action="store_true",
        help=(
            "Read every player snapshot and combine current-season history "
            "across snapshots. Default: latest snapshot per player."
        ),
    )
    parser.add_argument(
        "--keep-output-on-failure",
        action="store_true",
        help="Keep the temporary build directory if validation fails.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only show warnings/errors.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
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


def ensure_season(season: str) -> None:
    if not SEASON_RE.fullmatch(season):
        fail(f"Invalid season '{season}'. Expected YYYY-YY, e.g. 2026-27.")


def project_root_from_script() -> Path:
    # Expected location: <project>/scripts/build_dataset.py
    return Path(__file__).resolve().parents[1]


def resolve_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    root = (
        Path(args.project_root).resolve()
        if args.project_root
        else project_root_from_script()
    )

    raw_dir = root / "data" / "raw" / args.season

    if args.output_dir:
        processed_dir = Path(args.output_dir).resolve()
    else:
        processed_dir = root / "data" / "processed" / args.season

    return root, raw_dir, processed_dir


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        fail(f"Invalid JSON: {path} ({exc})")
    except OSError as exc:
        fail(f"Cannot read {path}: {exc}")


def json_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []

    files = [
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() == ".json"
    ]
    return sorted(files, key=lambda p: p.name)


def snapshot_files(directory: Path) -> list[Path]:
    files = json_files(directory)
    valid = [p for p in files if SNAPSHOT_RE.fullmatch(p.name)]

    # Be tolerant of legacy/non-standard filenames but warn.
    for p in files:
        if p not in valid:
            LOG.warning("Ignoring non-snapshot JSON filename: %s", p)

    return valid


def latest_snapshot(directory: Path) -> Path:
    files = snapshot_files(directory)
    if not files:
        fail(f"No snapshot JSON files found in {directory}")
    # Snapshot filenames use sortable ISO-like timestamps.
    return files[-1]


def snapshot_timestamp(path: Path) -> str:
    stem = path.stem
    return stem


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_replace_directory(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)

    backup = target.parent / f".{target.name}.backup"

    if backup.exists():
        shutil.rmtree(backup)

    if target.exists():
        target.replace(backup)

    try:
        source.replace(target)
    except Exception:
        if backup.exists() and not target.exists():
            backup.replace(target)
        raise
    else:
        if backup.exists():
            shutil.rmtree(backup)


def value(obj: dict[str, Any], key: str, default: Any = None) -> Any:
    return obj.get(key, default)


def as_int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def as_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def as_bool(v: Any) -> bool | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    text = str(v).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def epoch_from_iso(value_: Any) -> int | None:
    if not value_:
        return None

    text = str(value_).strip()

    try:
        normalized = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return int(dt.timestamp())
    except ValueError:
        return None


def csv_value(v: Any) -> Any:
    if isinstance(v, bool):
        return "1" if v else "0"
    if v is None:
        return ""
    return v


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> int:
    rows = list(rows)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=fields,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()

        for row in rows:
            writer.writerow({
                field: csv_value(row.get(field))
                for field in fields
            })

    return len(rows)


def write_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(
            data,
            fh,
            ensure_ascii=False,
            indent=2,
            sort_keys=False,
        )
        fh.write("\n")


# ---------------------------------------------------------------------------
# Raw payload extraction
# ---------------------------------------------------------------------------

def extract_bootstrap_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        fail("Bootstrap snapshot root must be a JSON object.")

    required = ["elements", "teams", "events", "element_types"]
    missing = [key for key in required if key not in payload]
    if missing:
        fail(
            "Bootstrap snapshot is missing required keys: "
            + ", ".join(missing)
        )

    return payload


def extract_fixtures_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        fixtures = payload
    elif isinstance(payload, dict) and isinstance(payload.get("fixtures"), list):
        fixtures = payload["fixtures"]
    else:
        fail(
            "Fixtures snapshot must be a JSON list or an object containing "
            "a 'fixtures' list."
        )

    if not all(isinstance(item, dict) for item in fixtures):
        fail("Fixtures snapshot contains non-object fixture records.")

    return fixtures


def extract_player_payload(payload: Any, path: Path) -> dict[str, Any]:
    if not isinstance(payload, dict):
        fail(f"Player snapshot root must be an object: {path}")

    for key in ("history", "history_past", "fixtures"):
        if key not in payload:
            fail(f"Player snapshot missing '{key}': {path}")

        if not isinstance(payload[key], list):
            fail(f"Player snapshot '{key}' must be a list: {path}")

    return payload


# ---------------------------------------------------------------------------
# Position lookup
# ---------------------------------------------------------------------------

def build_position_lookup(element_types: list[dict[str, Any]]) -> dict[int, str]:
    result: dict[int, str] = {}

    for item in element_types:
        position_id = as_int(item.get("id"))
        singular_name = item.get("singular_name")

        if position_id is not None:
            result[position_id] = str(singular_name or position_id)

    return result


# ---------------------------------------------------------------------------
# Normalize teams
# ---------------------------------------------------------------------------

def normalize_teams(bootstrap: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()

    for raw in bootstrap["teams"]:
        team_id = as_int(raw.get("id"))

        if team_id is None:
            fail("Bootstrap contains a team without a valid id.")

        if team_id in seen:
            fail(f"Duplicate team id in bootstrap: {team_id}")

        seen.add(team_id)

        rows.append({
            "team_id": team_id,
            "code": as_int(raw.get("code")),
            "name": raw.get("name"),
            "short_name": raw.get("short_name"),
            "strength": as_int(raw.get("strength")),
            "strength_overall_home": as_int(raw.get("strength_overall_home")),
            "strength_overall_away": as_int(raw.get("strength_overall_away")),
            "strength_attack_home": as_int(raw.get("strength_attack_home")),
            "strength_attack_away": as_int(raw.get("strength_attack_away")),
            "strength_defence_home": as_int(raw.get("strength_defence_home")),
            "strength_defence_away": as_int(raw.get("strength_defence_away")),
            "position": as_int(raw.get("position")),
            "played": as_int(raw.get("played")),
            "win": as_int(raw.get("win")),
            "draw": as_int(raw.get("draw")),
            "loss": as_int(raw.get("loss")),
            "points": as_int(raw.get("points")),
            "form": raw.get("form"),
            "team_division": raw.get("team_division"),
            "unavailable": as_int(raw.get("unavailable")),
            "pulse_id": as_int(raw.get("pulse_id")),
        })

    return sorted(rows, key=lambda row: row["team_id"])


# ---------------------------------------------------------------------------
# Normalize gameweeks
# ---------------------------------------------------------------------------

def normalize_gameweeks(bootstrap: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()

    for raw in bootstrap["events"]:
        gw = as_int(raw.get("id"))

        if gw is None:
            fail("Bootstrap contains a gameweek without a valid id.")

        if gw in seen:
            fail(f"Duplicate gameweek id in bootstrap: {gw}")

        seen.add(gw)

        rows.append({
            "gameweek": gw,
            "name": raw.get("name"),
            "deadline_time": raw.get("deadline_time"),
            "deadline_time_epoch": epoch_from_iso(raw.get("deadline_time")),
            "release_time": raw.get("release_time"),
            "release_time_epoch": epoch_from_iso(raw.get("release_time")),
            "average_entry_score": as_int(raw.get("average_entry_score")),
            "finished": as_bool(raw.get("finished")),
            "data_checked": as_bool(raw.get("data_checked")),
            "highest_scoring_entry": as_int(raw.get("highest_scoring_entry")),
            "highest_score": as_int(raw.get("highest_score")),
            "is_previous": as_bool(raw.get("is_previous")),
            "is_current": as_bool(raw.get("is_current")),
            "is_next": as_bool(raw.get("is_next")),
            "cup_leagues_created": as_bool(raw.get("cup_leagues_created")),
            "h2h_ko_matches_created": as_bool(raw.get("h2h_ko_matches_created")),
            "ranked_count": as_int(raw.get("ranked_count")),
            "transfers_made": as_int(raw.get("transfers_made")),
            "most_selected": as_int(raw.get("most_selected")),
            "most_transferred_in": as_int(raw.get("most_transferred_in")),
            "top_element": as_int(raw.get("top_element")),
            "top_element_info": json.dumps(
                raw.get("top_element_info"),
                ensure_ascii=False,
                separators=(",", ":"),
            ) if raw.get("top_element_info") is not None else None,
            "chip_plays": json.dumps(
                raw.get("chip_plays"),
                ensure_ascii=False,
                separators=(",", ":"),
            ) if raw.get("chip_plays") is not None else None,
            "most_vice_captained": as_int(raw.get("most_vice_captained")),
            "most_captained": as_int(raw.get("most_captained")),
        })

    return sorted(rows, key=lambda row: row["gameweek"])


# ---------------------------------------------------------------------------
# Normalize players
# ---------------------------------------------------------------------------

PLAYER_INT_FIELDS = {
    "code",
    "team",
    "team_code",
    "element_type",
    "now_cost",
    "cost_change_event",
    "cost_change_event_fall",
    "cost_change_start",
    "cost_change_start_fall",
    "total_points",
    "event_points",
    "transfers_in",
    "transfers_in_event",
    "transfers_out",
    "transfers_out_event",
    "minutes",
    "starts",
    "goals_scored",
    "assists",
    "clean_sheets",
    "goals_conceded",
    "own_goals",
    "penalties_saved",
    "penalties_missed",
    "yellow_cards",
    "red_cards",
    "saves",
    "bonus",
    "bps",
    "clearances_blocks_interceptions",
    "recoveries",
    "tackles",
    "defensive_contribution",
    "chance_of_playing_next_round",
    "chance_of_playing_this_round",
    "selected_rank",
    "selected_rank_type",
    "form_rank",
    "form_rank_type",
    "points_per_game_rank",
    "points_per_game_rank_type",
    "influence_rank",
    "influence_rank_type",
    "creativity_rank",
    "creativity_rank_type",
    "threat_rank",
    "threat_rank_type",
    "ict_index_rank",
    "ict_index_rank_type",
    "now_cost_rank",
    "now_cost_rank_type",
    "squad_number",
}

PLAYER_FLOAT_FIELDS = {
    "price_change_percent",
    "points_per_game",
    "form",
    "ep_next",
    "ep_this",
    "selected_by_percent",
    "value_form",
    "value_season",
    "influence",
    "creativity",
    "threat",
    "ict_index",
    "expected_goals",
    "expected_assists",
    "expected_goal_involvements",
    "expected_goals_conceded",
    "expected_goals_per_90",
    "expected_assists_per_90",
    "expected_goal_involvements_per_90",
    "expected_goals_conceded_per_90",
    "saves_per_90",
    "goals_conceded_per_90",
    "starts_per_90",
    "clean_sheets_per_90",
    "defensive_contribution_per_90",
}


def normalize_players(
    bootstrap: dict[str, Any],
    positions: dict[int, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    team_ids = {
        as_int(team.get("id"))
        for team in bootstrap["teams"]
    }

    for raw in bootstrap["elements"]:
        player_id = as_int(raw.get("id"))

        if player_id is None:
            fail("Bootstrap contains a player without a valid id.")

        if player_id in seen:
            fail(f"Duplicate player id in bootstrap: {player_id}")

        seen.add(player_id)

        team_id = as_int(raw.get("team"))
        position_id = as_int(raw.get("element_type"))

        if team_id not in team_ids:
            fail(
                f"Player {player_id} references unknown team id {team_id}."
            )

        if position_id not in positions:
            fail(
                f"Player {player_id} references unknown position id "
                f"{position_id}."
            )

        row: dict[str, Any] = {
            "player_id": player_id,
            "code": as_int(raw.get("code")),
            "first_name": raw.get("first_name"),
            "second_name": raw.get("second_name"),
            "web_name": raw.get("web_name"),
            "known_name": raw.get("known_name"),
            "team_id": team_id,
            "team_code": as_int(raw.get("team_code")),
            "position_id": position_id,
            "position_name": positions[position_id],
            "now_cost": as_int(raw.get("now_cost")),
            "now_cost_m": (
                as_float(raw.get("now_cost")) / 10
                if raw.get("now_cost") is not None
                else None
            ),
            "cost_change_event": as_int(raw.get("cost_change_event")),
            "cost_change_event_fall": as_int(
                raw.get("cost_change_event_fall")
            ),
            "cost_change_start": as_int(raw.get("cost_change_start")),
            "cost_change_start_fall": as_int(
                raw.get("cost_change_start_fall")
            ),
            "price_change_percent": as_float(
                raw.get("price_change_percent")
            ),
            "total_points": as_int(raw.get("total_points")),
            "points_per_game": as_float(raw.get("points_per_game")),
            "form": as_float(raw.get("form")),
            "event_points": as_int(raw.get("event_points")),
            "ep_next": as_float(raw.get("ep_next")),
            "ep_this": as_float(raw.get("ep_this")),
            "selected_by_percent": as_float(
                raw.get("selected_by_percent")
            ),
            "transfers_in": as_int(raw.get("transfers_in")),
            "transfers_in_event": as_int(
                raw.get("transfers_in_event")
            ),
            "transfers_out": as_int(raw.get("transfers_out")),
            "transfers_out_event": as_int(
                raw.get("transfers_out_event")
            ),
            "value_form": as_float(raw.get("value_form")),
            "value_season": as_float(raw.get("value_season")),
            "minutes": as_int(raw.get("minutes")),
            "starts": as_int(raw.get("starts")),
            "goals_scored": as_int(raw.get("goals_scored")),
            "assists": as_int(raw.get("assists")),
            "clean_sheets": as_int(raw.get("clean_sheets")),
            "goals_conceded": as_int(raw.get("goals_conceded")),
            "own_goals": as_int(raw.get("own_goals")),
            "penalties_saved": as_int(raw.get("penalties_saved")),
            "penalties_missed": as_int(raw.get("penalties_missed")),
            "yellow_cards": as_int(raw.get("yellow_cards")),
            "red_cards": as_int(raw.get("red_cards")),
            "saves": as_int(raw.get("saves")),
            "bonus": as_int(raw.get("bonus")),
            "bps": as_int(raw.get("bps")),
            "influence": as_float(raw.get("influence")),
            "creativity": as_float(raw.get("creativity")),
            "threat": as_float(raw.get("threat")),
            "ict_index": as_float(raw.get("ict_index")),
            "clearances_blocks_interceptions": as_int(
                raw.get("clearances_blocks_interceptions")
            ),
            "recoveries": as_int(raw.get("recoveries")),
            "tackles": as_int(raw.get("tackles")),
            "defensive_contribution": as_int(
                raw.get("defensive_contribution")
            ),
            "expected_goals": as_float(raw.get("expected_goals")),
            "expected_assists": as_float(raw.get("expected_assists")),
            "expected_goal_involvements": as_float(
                raw.get("expected_goal_involvements")
            ),
            "expected_goals_conceded": as_float(
                raw.get("expected_goals_conceded")
            ),
            "expected_goals_per_90": as_float(
                raw.get("expected_goals_per_90")
            ),
            "expected_assists_per_90": as_float(
                raw.get("expected_assists_per_90")
            ),
            "expected_goal_involvements_per_90": as_float(
                raw.get("expected_goal_involvements_per_90")
            ),
            "expected_goals_conceded_per_90": as_float(
                raw.get("expected_goals_conceded_per_90")
            ),
            "saves_per_90": as_float(raw.get("saves_per_90")),
            "goals_conceded_per_90": as_float(
                raw.get("goals_conceded_per_90")
            ),
            "starts_per_90": as_float(raw.get("starts_per_90")),
            "clean_sheets_per_90": as_float(
                raw.get("clean_sheets_per_90")
            ),
            "defensive_contribution_per_90": as_float(
                raw.get("defensive_contribution_per_90")
            ),
            "chance_of_playing_next_round": as_int(
                raw.get("chance_of_playing_next_round")
            ),
            "chance_of_playing_this_round": as_int(
                raw.get("chance_of_playing_this_round")
            ),
            "status": raw.get("status"),
            "removed": as_bool(raw.get("removed")),
            "can_select": as_bool(raw.get("can_select")),
            "can_transact": as_bool(raw.get("can_transact")),
            "news": raw.get("news"),
            "news_added": raw.get("news_added"),
            "team_join_date": raw.get("team_join_date"),
            "birth_date": raw.get("birth_date"),
            "squad_number": as_int(raw.get("squad_number")),
            "selected_rank": as_int(raw.get("selected_rank")),
            "selected_rank_type": as_int(
                raw.get("selected_rank_type")
            ),
            "form_rank": as_int(raw.get("form_rank")),
            "form_rank_type": as_int(raw.get("form_rank_type")),
            "points_per_game_rank": as_int(
                raw.get("points_per_game_rank")
            ),
            "points_per_game_rank_type": as_int(
                raw.get("points_per_game_rank_type")
            ),
            "influence_rank": as_int(raw.get("influence_rank")),
            "influence_rank_type": as_int(
                raw.get("influence_rank_type")
            ),
            "creativity_rank": as_int(raw.get("creativity_rank")),
            "creativity_rank_type": as_int(
                raw.get("creativity_rank_type")
            ),
            "threat_rank": as_int(raw.get("threat_rank")),
            "threat_rank_type": as_int(raw.get("threat_rank_type")),
            "ict_index_rank": as_int(raw.get("ict_index_rank")),
            "ict_index_rank_type": as_int(
                raw.get("ict_index_rank_type")
            ),
            "now_cost_rank": as_int(raw.get("now_cost_rank")),
            "now_cost_rank_type": as_int(
                raw.get("now_cost_rank_type")
            ),
        }

        rows.append(row)

    return sorted(rows, key=lambda row: row["player_id"])


# ---------------------------------------------------------------------------
# Normalize fixtures
# ---------------------------------------------------------------------------

def normalize_fixtures(
    fixture_payload: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()

    for raw in fixture_payload:
        fixture_id = as_int(raw.get("id"))

        if fixture_id is None:
            fail("Fixture without a valid id.")

        if fixture_id in seen:
            fail(f"Duplicate fixture id: {fixture_id}")

        seen.add(fixture_id)

        gameweek = as_int(raw.get("event"))
        team_h = as_int(raw.get("team_h"))
        team_a = as_int(raw.get("team_a"))

        rows.append({
            "fixture_id": fixture_id,
            "code": as_int(raw.get("code")),
            "gameweek": gameweek,
            "event_name": raw.get("event_name"),
            "team_h": team_h,
            "team_a": team_a,
            "team_h_score": as_int(raw.get("team_h_score")),
            "team_a_score": as_int(raw.get("team_a_score")),
            "team_h_difficulty": as_int(
                raw.get("team_h_difficulty", raw.get("difficulty"))
            ),
            "team_a_difficulty": as_int(
                raw.get("team_a_difficulty", raw.get("difficulty"))
            ),
            "finished": as_bool(raw.get("finished")),
            "finished_provisional": as_bool(
                raw.get("finished_provisional")
            ),
            "started": as_bool(raw.get("started")),
            "minutes": as_int(raw.get("minutes")),
            "provisional_start_time": as_bool(
                raw.get("provisional_start_time")
            ),
            "kickoff_time": raw.get("kickoff_time"),
            "pulse_id": as_int(raw.get("pulse_id")),
        })

    return sorted(rows, key=lambda row: row["fixture_id"])


# ---------------------------------------------------------------------------
# Normalize player current-season history
# ---------------------------------------------------------------------------

HISTORY_INT_FIELDS = [
    "element",
    "fixture",
    "opponent_team",
    "total_points",
    "minutes",
    "goals_scored",
    "assists",
    "clean_sheets",
    "goals_conceded",
    "own_goals",
    "penalties_saved",
    "penalties_missed",
    "yellow_cards",
    "red_cards",
    "saves",
    "bonus",
    "bps",
    "clearances_blocks_interceptions",
    "recoveries",
    "tackles",
    "defensive_contribution",
    "starts",
]

HISTORY_FLOAT_FIELDS = [
    "influence",
    "creativity",
    "threat",
    "ict_index",
    "expected_goals",
    "expected_assists",
    "expected_goal_involvements",
    "expected_goals_conceded",
]


def normalize_player_history(
    player_id: int,
    season: str,
    history: list[dict[str, Any]],
    fixture_map: dict[int, dict[str, Any]],
    player_team_map: dict[int, int],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for raw in history:
        gameweek = as_int(raw.get("round"))
        fixture_id = as_int(raw.get("fixture"))

        if gameweek is None:
            fail(
                f"Player {player_id} has a history row without "
                f"a valid round/gameweek."
            )

        if fixture_id is None:
            fail(
                f"Player {player_id}, GW{gameweek} has no fixture id."
            )

        fixture = fixture_map.get(fixture_id)

        if fixture is None:
            LOG.warning(
                "Player %s history references fixture %s not found "
                "in global fixture snapshot.",
                player_id,
                fixture_id,
            )

        team_id = player_team_map.get(player_id)

        if fixture and team_id:
            if fixture["team_h"] == team_id:
                opponent_team = fixture["team_a"]
                was_home = True
            elif fixture["team_a"] == team_id:
                opponent_team = fixture["team_h"]
                was_home = False
            else:
                opponent_team = as_int(raw.get("opponent_team"))
                was_home = as_bool(raw.get("was_home"))
        else:
            opponent_team = as_int(raw.get("opponent_team"))
            was_home = as_bool(raw.get("was_home"))

        rows.append({
            "player_id": player_id,
            "season": season,
            "gameweek": gameweek,
            "fixture_id": fixture_id,
            "opponent_team": opponent_team,
            "was_home": was_home,
            "kickoff_time": (
                fixture.get("kickoff_time")
                if fixture
                else raw.get("kickoff_time")
            ),
            "minutes": as_int(raw.get("minutes")),
            "total_points": as_int(raw.get("total_points")),
            "goals_scored": as_int(raw.get("goals_scored")),
            "assists": as_int(raw.get("assists")),
            "clean_sheets": as_int(raw.get("clean_sheets")),
            "goals_conceded": as_int(raw.get("goals_conceded")),
            "own_goals": as_int(raw.get("own_goals")),
            "penalties_saved": as_int(raw.get("penalties_saved")),
            "penalties_missed": as_int(raw.get("penalties_missed")),
            "yellow_cards": as_int(raw.get("yellow_cards")),
            "red_cards": as_int(raw.get("red_cards")),
            "saves": as_int(raw.get("saves")),
            "bonus": as_int(raw.get("bonus")),
            "bps": as_int(raw.get("bps")),
            "influence": as_float(raw.get("influence")),
            "creativity": as_float(raw.get("creativity")),
            "threat": as_float(raw.get("threat")),
            "ict_index": as_float(raw.get("ict_index")),
            "clearances_blocks_interceptions": as_int(
                raw.get("clearances_blocks_interceptions")
            ),
            "recoveries": as_int(raw.get("recoveries")),
            "tackles": as_int(raw.get("tackles")),
            "defensive_contribution": as_int(
                raw.get("defensive_contribution")
            ),
            "starts": as_int(raw.get("starts")),
            "expected_goals": as_float(raw.get("expected_goals")),
            "expected_assists": as_float(raw.get("expected_assists")),
            "expected_goal_involvements": as_float(
                raw.get("expected_goal_involvements")
            ),
            "expected_goals_conceded": as_float(
                raw.get("expected_goals_conceded")
            ),
        })

    return rows


# ---------------------------------------------------------------------------
# Normalize player historical season summaries
# ---------------------------------------------------------------------------

def normalize_player_season_history(
    player_id: int,
    history_past: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for raw in history_past:
        rows.append({
            "player_id": player_id,
            "season": raw.get("season_name"),
            "element_code": as_int(raw.get("element_code")),
            "start_cost": as_int(raw.get("start_cost")),
            "end_cost": as_int(raw.get("end_cost")),
            "total_points": as_int(raw.get("total_points")),
            "minutes": as_int(raw.get("minutes")),
            "goals_scored": as_int(raw.get("goals_scored")),
            "assists": as_int(raw.get("assists")),
            "clean_sheets": as_int(raw.get("clean_sheets")),
            "goals_conceded": as_int(raw.get("goals_conceded")),
            "own_goals": as_int(raw.get("own_goals")),
            "penalties_saved": as_int(raw.get("penalties_saved")),
            "penalties_missed": as_int(raw.get("penalties_missed")),
            "yellow_cards": as_int(raw.get("yellow_cards")),
            "red_cards": as_int(raw.get("red_cards")),
            "saves": as_int(raw.get("saves")),
            "bonus": as_int(raw.get("bonus")),
            "bps": as_int(raw.get("bps")),
            "influence": as_float(raw.get("influence")),
            "creativity": as_float(raw.get("creativity")),
            "threat": as_float(raw.get("threat")),
            "ict_index": as_float(raw.get("ict_index")),
            "clearances_blocks_interceptions": as_int(
                raw.get("clearances_blocks_interceptions")
            ),
            "recoveries": as_int(raw.get("recoveries")),
            "tackles": as_int(raw.get("tackles")),
            "defensive_contribution": as_int(
                raw.get("defensive_contribution")
            ),
            "starts": as_int(raw.get("starts")),
            "expected_goals": as_float(raw.get("expected_goals")),
            "expected_assists": as_float(raw.get("expected_assists")),
            "expected_goal_involvements": as_float(
                raw.get("expected_goal_involvements")
            ),
            "expected_goals_conceded": as_float(
                raw.get("expected_goals_conceded")
            ),
        })

    return rows


# ---------------------------------------------------------------------------
# Player snapshot discovery
# ---------------------------------------------------------------------------

def discover_player_snapshots(
    players_dir: Path,
) -> dict[int, list[Path]]:
    if not players_dir.exists():
        fail(f"Players directory does not exist: {players_dir}")

    result: dict[int, list[Path]] = {}

    for player_dir in sorted(players_dir.iterdir(), key=lambda p: p.name):
        if not player_dir.is_dir():
            continue

        player_id = as_int(player_dir.name)

        if player_id is None:
            LOG.warning(
                "Ignoring non-numeric player directory: %s",
                player_dir,
            )
            continue

        files = snapshot_files(player_dir)

        if not files:
            LOG.warning(
                "Player directory %s contains no valid snapshots.",
                player_id,
            )
            continue

        result[player_id] = files

    return result


# ---------------------------------------------------------------------------
# Integrity checks
# ---------------------------------------------------------------------------

def assert_unique(
    rows: list[dict[str, Any]],
    key_fields: tuple[str, ...],
    dataset_name: str,
) -> None:
    seen: set[tuple[Any, ...]] = set()

    for row in rows:
        key = tuple(row.get(field) for field in key_fields)

        if key in seen:
            fail(
                f"Duplicate key in {dataset_name}: "
                + ", ".join(
                    f"{field}={row.get(field)!r}"
                    for field in key_fields
                )
            )

        seen.add(key)


def validate_integrity(
    players: list[dict[str, Any]],
    teams: list[dict[str, Any]],
    gameweeks: list[dict[str, Any]],
    fixtures: list[dict[str, Any]],
    player_gameweek: list[dict[str, Any]],
    player_season_history: list[dict[str, Any]],
) -> dict[str, Any]:
    player_ids = {row["player_id"] for row in players}
    team_ids = {row["team_id"] for row in teams}
    gameweek_ids = {row["gameweek"] for row in gameweeks}
    fixture_ids = {row["fixture_id"] for row in fixtures}

    assert_unique(players, ("player_id",), "players")
    assert_unique(teams, ("team_id",), "teams")
    assert_unique(gameweeks, ("gameweek",), "gameweeks")
    assert_unique(fixtures, ("fixture_id",), "fixtures")

    assert_unique(
        player_gameweek,
        ("player_id", "gameweek", "fixture_id"),
        "player_gameweek",
    )

    assert_unique(
        player_season_history,
        ("player_id", "season"),
        "player_season_history",
    )

    invalid_player_team = [
        row for row in players
        if row["team_id"] not in team_ids
    ]

    if invalid_player_team:
        fail(
            "Player/team referential integrity failure: "
            f"{len(invalid_player_team)} players reference unknown teams."
        )

    invalid_fixture_teams = [
        row for row in fixtures
        if row["team_h"] not in team_ids
        or row["team_a"] not in team_ids
    ]

    if invalid_fixture_teams:
        fail(
            "Fixture/team referential integrity failure: "
            f"{len(invalid_fixture_teams)} fixtures reference unknown teams."
        )

    invalid_fixture_gameweeks = [
        row for row in fixtures
        if row["gameweek"] is not None
        and row["gameweek"] not in gameweek_ids
    ]

    if invalid_fixture_gameweeks:
        fail(
            "Fixture/gameweek referential integrity failure: "
            f"{len(invalid_fixture_gameweeks)} fixtures reference "
            "unknown gameweeks."
        )

    invalid_history_players = [
        row for row in player_gameweek
        if row["player_id"] not in player_ids
    ]

    if invalid_history_players:
        fail(
            "Player-history referential integrity failure: "
            f"{len(invalid_history_players)} rows reference unknown players."
        )

    invalid_history_fixtures = [
        row for row in player_gameweek
        if row["fixture_id"] not in fixture_ids
    ]

    if invalid_history_fixtures:
        fail(
            "Player-history/fixture referential integrity failure: "
            f"{len(invalid_history_fixtures)} rows reference unknown fixtures."
        )

    invalid_history_gameweeks = [
        row for row in player_gameweek
        if row["gameweek"] not in gameweek_ids
    ]

    if invalid_history_gameweeks:
        fail(
            "Player-history/gameweek referential integrity failure: "
            f"{len(invalid_history_gameweeks)} rows reference "
            "unknown gameweeks."
        )

    return {
        "unique_players": len(player_ids),
        "unique_teams": len(team_ids),
        "unique_gameweeks": len(gameweek_ids),
        "unique_fixtures": len(fixture_ids),
        "player_gameweek_rows": len(player_gameweek),
        "player_season_history_rows": len(player_season_history),
    }


def validate_business_rules(
    players: list[dict[str, Any]],
    teams: list[dict[str, Any]],
    gameweeks: list[dict[str, Any]],
    fixtures: list[dict[str, Any]],
    player_gameweek: list[dict[str, Any]],
) -> dict[str, Any]:
    warnings: list[str] = []

    if len(teams) != 20:
        warnings.append(
            f"Expected 20 Premier League teams; found {len(teams)}."
        )

    if len(gameweeks) != 38:
        warnings.append(
            f"Expected 38 gameweeks; found {len(gameweeks)}."
        )

    if len(players) < 500:
        warnings.append(
            f"Player count is unexpectedly low: {len(players)}."
        )

    if len(fixtures) < 300:
        warnings.append(
            f"Fixture count is unexpectedly low: {len(fixtures)}."
        )

    duplicate_fixture_codes = [
        code for code, count in Counter(
            row["code"] for row in fixtures
            if row["code"] is not None
        ).items()
        if count > 1
    ]

    if duplicate_fixture_codes:
        fail(
            "Duplicate fixture codes detected: "
            + ", ".join(map(str, duplicate_fixture_codes[:10]))
        )

    invalid_positions = [
        row for row in players
        if row["position_id"] not in {1, 2, 3, 4}
    ]

    if invalid_positions:
        fail(
            f"{len(invalid_positions)} players have invalid FPL positions."
        )

    impossible_minutes = [
        row for row in player_gameweek
        if row["minutes"] is not None
        and not 0 <= row["minutes"] <= 120
    ]

    if impossible_minutes:
        fail(
            f"{len(impossible_minutes)} player-gameweek rows have "
            "invalid minutes."
        )

    negative_points = [
        row for row in player_gameweek
        if row["total_points"] is not None
        and row["total_points"] < -20
    ]

    if negative_points:
        fail(
            f"{len(negative_points)} player-gameweek rows have "
            "implausibly low total_points."
        )

    for warning in warnings:
        LOG.warning(warning)

    return {
        "warnings": warnings,
        "duplicate_fixture_codes": len(duplicate_fixture_codes),
        "invalid_positions": len(invalid_positions),
        "invalid_minutes_rows": len(impossible_minutes),
        "negative_points_rows": len(negative_points),
    }


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()
    configure_logging(args)
    ensure_season(args.season)

    root, raw_dir, processed_dir = resolve_paths(args)

    bootstrap_dir = raw_dir / "bootstrap"
    fixtures_dir = raw_dir / "fixtures"
    players_dir = raw_dir / "players"

    LOG.info("=" * 72)
    LOG.info("FPL PROCESSED DATASET BUILDER")
    LOG.info("=" * 72)
    LOG.info("Version       : %s", VERSION)
    LOG.info("Season        : %s", args.season)
    LOG.info("Project root  : %s", root)
    LOG.info("Raw directory : %s", raw_dir)
    LOG.info("Output        : %s", processed_dir)
    LOG.info(
        "Player mode   : %s",
        "ALL SNAPSHOTS" if args.all_player_snapshots else "LATEST SNAPSHOTS",
    )
    LOG.info("")

    if not raw_dir.exists():
        fail(f"Raw season directory does not exist: {raw_dir}")

    # ---------------------------------------------------------------
    # Select latest bootstrap and fixtures snapshots.
    # ---------------------------------------------------------------

    bootstrap_path = latest_snapshot(bootstrap_dir)
    fixtures_path = latest_snapshot(fixtures_dir)

    LOG.info("Bootstrap snapshot : %s", bootstrap_path.name)
    LOG.info("Fixtures snapshot  : %s", fixtures_path.name)

    bootstrap_payload = extract_bootstrap_payload(
        load_json(bootstrap_path)
    )
    fixtures_payload = extract_fixtures_payload(
        load_json(fixtures_path)
    )

    positions = build_position_lookup(
        bootstrap_payload["element_types"]
    )

    LOG.info(
        "Bootstrap entities: teams=%d players=%d gameweeks=%d",
        len(bootstrap_payload["teams"]),
        len(bootstrap_payload["elements"]),
        len(bootstrap_payload["events"]),
    )

    # ---------------------------------------------------------------
    # Normalize base datasets.
    # ---------------------------------------------------------------

    teams = normalize_teams(bootstrap_payload)
    gameweeks = normalize_gameweeks(bootstrap_payload)
    players = normalize_players(bootstrap_payload, positions)
    fixtures = normalize_fixtures(fixtures_payload)

    LOG.info("Normalized teams      : %d", len(teams))
    LOG.info("Normalized players    : %d", len(players))
    LOG.info("Normalized gameweeks  : %d", len(gameweeks))
    LOG.info("Normalized fixtures   : %d", len(fixtures))

    fixture_map = {
        row["fixture_id"]: row
        for row in fixtures
    }

    player_team_map = {
        row["player_id"]: row["team_id"]
        for row in players
    }

    # ---------------------------------------------------------------
    # Discover player snapshots.
    # ---------------------------------------------------------------

    snapshot_map = discover_player_snapshots(players_dir)

    bootstrap_player_ids = set(player_team_map)
    snapshot_player_ids = set(snapshot_map)

    missing_snapshot_players = sorted(
        bootstrap_player_ids - snapshot_player_ids
    )
    extra_snapshot_players = sorted(
        snapshot_player_ids - bootstrap_player_ids
    )

    if missing_snapshot_players:
        fail(
            "Missing player snapshots for bootstrap players: "
            + ", ".join(map(str, missing_snapshot_players[:20]))
        )

    if extra_snapshot_players:
        fail(
            "Extra player snapshot directories not present in bootstrap: "
            + ", ".join(map(str, extra_snapshot_players[:20]))
        )

    LOG.info(
        "Player snapshot coverage: %d/%d",
        len(snapshot_player_ids),
        len(bootstrap_player_ids),
    )

    # ---------------------------------------------------------------
    # Normalize player histories.
    # ---------------------------------------------------------------

    player_gameweek_rows: list[dict[str, Any]] = []
    player_season_history_rows: list[dict[str, Any]] = []

    snapshot_manifest: list[dict[str, Any]] = []

    for index, player_id in enumerate(sorted(snapshot_map), start=1):
        paths = snapshot_map[player_id]

        selected_paths = paths if args.all_player_snapshots else [paths[-1]]

        for path in selected_paths:
            payload = extract_player_payload(
                load_json(path),
                path,
            )

            # Current-season history.
            current_history = normalize_player_history(
                player_id=player_id,
                season=args.season,
                history=payload["history"],
                fixture_map=fixture_map,
                player_team_map=player_team_map,
            )

            player_gameweek_rows.extend(current_history)

            # Historical season summaries.
            past_history = normalize_player_season_history(
                player_id=player_id,
                history_past=payload["history_past"],
            )

            # If processing multiple snapshots, the same historical
            # summaries will occur repeatedly. We deduplicate later.
            player_season_history_rows.extend(past_history)

            snapshot_manifest.append({
                "player_id": player_id,
                "snapshot": path.name,
                "snapshot_timestamp": snapshot_timestamp(path),
                "sha256": sha256_file(path),
                "current_history_rows": len(payload["history"]),
                "past_season_rows": len(payload["history_past"]),
            })

        if index == 1 or index % 50 == 0 or index == len(snapshot_map):
            LOG.info(
                "Processed player snapshots: %d/%d",
                index,
                len(snapshot_map),
            )

    # ---------------------------------------------------------------
    # Deterministic deduplication.
    # ---------------------------------------------------------------

    def dedupe_rows(
        rows: list[dict[str, Any]],
        keys: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        result: dict[tuple[Any, ...], dict[str, Any]] = {}

        for row in rows:
            key = tuple(row.get(k) for k in keys)

            # Later snapshot wins when --all-player-snapshots is used.
            result[key] = row

        return sorted(
            result.values(),
            key=lambda row: tuple(
                "" if row.get(k) is None else row.get(k)
                for k in keys
            ),
        )

    player_gameweek_rows = dedupe_rows(
        player_gameweek_rows,
        ("player_id", "gameweek", "fixture_id"),
    )

    player_season_history_rows = dedupe_rows(
        player_season_history_rows,
        ("player_id", "season"),
    )

    LOG.info(
        "Current-season player-gameweek rows: %d",
        len(player_gameweek_rows),
    )
    LOG.info(
        "Historical player-season rows: %d",
        len(player_season_history_rows),
    )

    # ---------------------------------------------------------------
    # Validate.
    # ---------------------------------------------------------------

    LOG.info("")
    LOG.info("Running referential-integrity checks...")

    integrity = validate_integrity(
        players=players,
        teams=teams,
        gameweeks=gameweeks,
        fixtures=fixtures,
        player_gameweek=player_gameweek_rows,
        player_season_history=player_season_history_rows,
    )

    LOG.info("Referential integrity : PASSED")

    business = validate_business_rules(
        players=players,
        teams=teams,
        gameweeks=gameweeks,
        fixtures=fixtures,
        player_gameweek=player_gameweek_rows,
    )

    LOG.info("Business rules        : PASSED")

    # ---------------------------------------------------------------
    # Build manifest before writing.
    # ---------------------------------------------------------------

    generated_at = datetime.now(timezone.utc).isoformat()

    manifest = {
        "schema_version": "1.0.0",
        "builder_version": VERSION,
        "season": args.season,
        "generated_at_utc": generated_at,
        "project_root": str(root),
        "raw_directory": str(raw_dir),
        "processed_directory": str(processed_dir),
        "source_snapshots": {
            "bootstrap": {
                "path": str(bootstrap_path),
                "filename": bootstrap_path.name,
                "timestamp": snapshot_timestamp(bootstrap_path),
                "sha256": sha256_file(bootstrap_path),
            },
            "fixtures": {
                "path": str(fixtures_path),
                "filename": fixtures_path.name,
                "timestamp": snapshot_timestamp(fixtures_path),
                "sha256": sha256_file(fixtures_path),
            },
        },
        "player_snapshot_mode": (
            "all_snapshots" if args.all_player_snapshots
            else "latest_per_player"
        ),
        "player_snapshot_count": len(snapshot_manifest),
        "counts": {
            "teams": len(teams),
            "players": len(players),
            "gameweeks": len(gameweeks),
            "fixtures": len(fixtures),
            "player_gameweek_rows": len(player_gameweek_rows),
            "player_season_history_rows": len(
                player_season_history_rows
            ),
        },
        "integrity": integrity,
        "business_rules": business,
        "files": {
            filename: {
                "columns": fields,
            }
            for filename, fields in OUTPUT_SCHEMAS.items()
        },
        "notes": [
            "Raw snapshots are immutable and were not modified.",
            "Bootstrap player data is used for the normalized current player table.",
            "Global fixtures are used as the authoritative fixture dimension.",
            "Player current-season history is empty before the first FPL gameweek.",
            "history_past contains season-level historical summaries, not per-gameweek history.",
            "Feature engineering and prediction targets are intentionally not created at this stage.",
        ],
        "player_snapshots": snapshot_manifest,
    }

    # ---------------------------------------------------------------
    # Write atomically to a temporary directory.
    # ---------------------------------------------------------------

    processed_dir.parent.mkdir(parents=True, exist_ok=True)

    temp_dir = Path(
        tempfile.mkdtemp(
            prefix=f".{processed_dir.name}.build-",
            dir=str(processed_dir.parent),
        )
    )

    LOG.info("")
    LOG.info("Writing processed dataset to temporary directory...")
    LOG.info("Temporary output: %s", temp_dir)

    try:
        counts_written = {}

        counts_written["players.csv"] = write_csv(
            temp_dir / "players.csv",
            players,
            PLAYERS_FIELDS,
        )

        counts_written["teams.csv"] = write_csv(
            temp_dir / "teams.csv",
            teams,
            TEAMS_FIELDS,
        )

        counts_written["gameweeks.csv"] = write_csv(
            temp_dir / "gameweeks.csv",
            gameweeks,
            GAMEWEEKS_FIELDS,
        )

        counts_written["fixtures.csv"] = write_csv(
            temp_dir / "fixtures.csv",
            fixtures,
            FIXTURES_FIELDS,
        )

        counts_written["player_gameweek.csv"] = write_csv(
            temp_dir / "player_gameweek.csv",
            player_gameweek_rows,
            PLAYER_GAMEWEEK_FIELDS,
        )

        counts_written["player_season_history.csv"] = write_csv(
            temp_dir / "player_season_history.csv",
            player_season_history_rows,
            PLAYER_SEASON_HISTORY_FIELDS,
        )

        manifest["counts_written"] = counts_written

        write_json(
            temp_dir / "dataset_manifest.json",
            manifest,
        )

        # Final sanity check: every expected file exists.
        expected_files = list(OUTPUT_SCHEMAS) + [
            "dataset_manifest.json"
        ]

        missing_outputs = [
            name for name in expected_files
            if not (temp_dir / name).exists()
        ]

        if missing_outputs:
            fail(
                "Build produced missing output files: "
                + ", ".join(missing_outputs)
            )

        # Commit only after all files are complete.
        atomic_replace_directory(temp_dir, processed_dir)

    except Exception:
        if args.keep_output_on_failure:
            LOG.error(
                "Build failed. Temporary output retained at: %s",
                temp_dir,
            )
        else:
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise

    # ---------------------------------------------------------------
    # Final summary.
    # ---------------------------------------------------------------

    LOG.info("")
    LOG.info("=" * 72)
    LOG.info("FPL PROCESSED DATASET BUILD COMPLETE")
    LOG.info("=" * 72)
    LOG.info("")
    LOG.info("Season                 : %s", args.season)
    LOG.info("Status                 : PASSED")
    LOG.info("")
    LOG.info("Teams                  : %d", len(teams))
    LOG.info("Players                : %d", len(players))
    LOG.info("Gameweeks              : %d", len(gameweeks))
    LOG.info("Fixtures               : %d", len(fixtures))
    LOG.info("Player-gameweek rows   : %d", len(player_gameweek_rows))
    LOG.info(
        "Player-season rows     : %d",
        len(player_season_history_rows),
    )
    LOG.info("")
    LOG.info("Processed directory:")
    LOG.info("  %s", processed_dir)
    LOG.info("")
    LOG.info("Output files:")

    for filename in list(OUTPUT_SCHEMAS) + ["dataset_manifest.json"]:
        LOG.info("  %s", processed_dir / filename)

    LOG.info("")
    LOG.info("=" * 72)
    LOG.info("RESULT: PASSED")
    LOG.info("Processed data is ready for feature engineering.")
    LOG.info("=" * 72)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        LOG.error("Interrupted by user.")
        raise SystemExit(130)
    except Exception as exc:
        LOG.error("BUILD FAILED: %s", exc)
        raise SystemExit(1)
