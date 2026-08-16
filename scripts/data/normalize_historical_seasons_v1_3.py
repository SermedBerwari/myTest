from pathlib import Path

script = r'''#!/usr/bin/env python3
"""
FPL Historical Data Normalizer v1.3

Purpose
-------
Normalize historical FPL player-gameweek data into one canonical schema while
supporting different source schemas across historical seasons.

Supported source profiles
-------------------------
2025-26 style:
    player_gameweek.fixture_code -> fixtures.code
    fixtures.event               -> gameweek
    fixtures.id                  -> fixture_id

2023-24 style:
    player_gameweek.GW            -> gameweek
    player_gameweek.fixture       -> fixture_id
    player_gameweek.kickoff_time  -> kickoff_time

Important
---------
- No gameweek is guessed from row order.
- No fixture mapping is invented from dates.
- 2026-27 is protected.
- Existing normalized output is not overwritten unless --force is supplied.
- Source fields are preserved where possible.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

VERSION = "1.3.0"
LIVE_SEASON = "2026-27"
DEFAULT_SEASONS = ("2021-22", "2022-23", "2023-24", "2024-25", "2025-26")
SEASON_RE = re.compile(r"^20\d{2}-\d{2}$")

LOG = logging.getLogger("fpl_historical_normalizer")

CANONICAL_COLUMNS = [
    "season",
    "player_id",
    "gameweek",
    "fixture_id",
    "fixture_code",
    "source_fixture_id",
    "player_code",
    "player_name",
    "first_name",
    "second_name",
    "team_id",
    "team_code",
    "team",
    "position",
    "value",
    "selected",
    "transfers_in",
    "transfers_out",
    "transfers_balance",
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
    "total_points",
    "influence",
    "creativity",
    "threat",
    "ict_index",
    "expected_goals",
    "expected_assists",
    "expected_goal_involvements",
    "expected_goals_conceded",
    "clearances_blocks_interceptions",
    "recoveries",
    "tackles",
    "defensive_contribution",
    "xP",
    "kickoff_time",
    "opponent_team",
    "was_home",
    "team_a_score",
    "team_h_score",
    "round",
]

PLAYER_ALIASES = {
    "player_id": ["element", "id", "player_id", "element_id"],
    "fixture_code": ["fixture_code"],
    "source_fixture_id": ["fixture", "source_fixture_id"],
    "player_code": ["player_code"],
    "first_name": ["first_name", "firstname"],
    "second_name": ["second_name", "last_name", "lastname"],
    "player_name": ["web_name", "name", "player_name"],
    "team_code": ["team_code"],
    "team_id": ["team_id"],
    "team": ["team"],
    "position": ["position", "element_type"],
    "value": ["value", "now_cost", "price"],
    "selected": ["selected", "selected_by"],
    "transfers_in": ["transfers_in"],
    "transfers_out": ["transfers_out"],
    "transfers_balance": ["transfers_balance"],
    "minutes": ["minutes"],
    "starts": ["starts"],
    "goals_scored": ["goals_scored", "goals"],
    "assists": ["assists"],
    "clean_sheets": ["clean_sheets"],
    "goals_conceded": ["goals_conceded"],
    "own_goals": ["own_goals"],
    "penalties_saved": ["penalties_saved"],
    "penalties_missed": ["penalties_missed"],
    "yellow_cards": ["yellow_cards"],
    "red_cards": ["red_cards"],
    "saves": ["saves"],
    "bonus": ["bonus"],
    "bps": ["bps"],
    "total_points": ["total_points", "points"],
    "influence": ["influence"],
    "creativity": ["creativity"],
    "threat": ["threat"],
    "ict_index": ["ict_index"],
    "expected_goals": ["expected_goals", "xg"],
    "expected_assists": ["expected_assists", "xa"],
    "expected_goal_involvements": ["expected_goal_involvements", "xgi"],
    "expected_goals_conceded": ["expected_goals_conceded", "xgc"],
    "clearances_blocks_interceptions": ["clearances_blocks_interceptions"],
    "recoveries": ["recoveries"],
    "tackles": ["tackles"],
    "defensive_contribution": ["defensive_contribution"],
    "xP": ["xP", "xp"],
    "gameweek": ["GW", "gw", "gameweek"],
    "kickoff_time": ["kickoff_time", "kickoff"],
    "opponent_team": ["opponent_team", "opponent"],
    "was_home": ["was_home", "home"],
    "team_a_score": ["team_a_score", "away_score"],
    "team_h_score": ["team_h_score", "home_score"],
    "round": ["round"],
}

FIXTURE_ALIASES = {
    "fixture_code": ["code", "fixture_code"],
    "fixture_id": ["id", "fixture_id"],
    "gameweek": ["event", "gw", "gameweek"],
    "finished": ["finished"],
    "finished_provisional": ["finished_provisional"],
    "kickoff_time": ["kickoff_time", "kickoff"],
    "minutes": ["minutes"],
    "provisional_start_time": ["provisional_start_time"],
    "started": ["started"],
    "team_a": ["team_a", "away_team"],
    "team_a_score": ["team_a_score", "away_score"],
    "team_h": ["team_h", "home_team"],
    "team_h_score": ["team_h_score", "home_score"],
    "team_h_difficulty": ["team_h_difficulty", "home_difficulty"],
    "team_a_difficulty": ["team_a_difficulty", "away_difficulty"],
}


def norm(value: Any) -> str:
    s = str(value).strip().lower().replace("-", "_").replace(" ", "_").replace("/", "_")
    while "__" in s:
        s = s.replace("__", "_")
    return s


def mapping(columns, aliases):
    lookup = {norm(c): str(c) for c in columns}
    out = {}
    for canonical, candidates in aliases.items():
        for candidate in candidates:
            key = norm(candidate)
            if key in lookup:
                out[canonical] = lookup[key]
                break
    return out


def atomic_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    df.to_csv(tmp, index=False, encoding="utf-8")
    tmp.replace(path)


def atomic_json(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def validate_gameweeks(series: pd.Series, season: str) -> list[int]:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        raise RuntimeError(f"{season}: no valid gameweek values found.")
    ints = sorted(set(int(x) for x in values))
    bad = [x for x in ints if x < 1 or x > 38]
    if bad:
        raise RuntimeError(f"{season}: invalid gameweeks {bad}")
    return ints


def normalize_modern(season: str, pdf: pd.DataFrame, fdf: pd.DataFrame):
    """
    2025-26 style:
        player fixture_code -> fixture code -> event/id
    """
    pm = mapping(pdf.columns, PLAYER_ALIASES)
    fm = mapping(fdf.columns, FIXTURE_ALIASES)

    for required in ("player_id", "fixture_code"):
        if required not in pm:
            raise RuntimeError(
                f"{season}: modern player data missing '{required}'; "
                f"columns: {list(pdf.columns)}"
            )

    for required in ("fixture_code", "fixture_id", "gameweek"):
        if required not in fm:
            raise RuntimeError(
                f"{season}: fixture table missing mappings {required}; "
                f"columns: {list(fdf.columns)}"
            )

    fixtures = pd.DataFrame()
    for canonical in FIXTURE_ALIASES:
        src = fm.get(canonical)
        fixtures[canonical] = fdf[src] if src else pd.NA

    fixtures.insert(0, "season", season)

    for col in [
        "fixture_code",
        "fixture_id",
        "gameweek",
        "team_a",
        "team_a_score",
        "team_h",
        "team_h_score",
        "team_h_difficulty",
        "team_a_difficulty",
        "minutes",
    ]:
        if col in fixtures.columns:
            fixtures[col] = pd.to_numeric(fixtures[col], errors="coerce")

    for col in ["fixture_code", "fixture_id", "gameweek"]:
        fixtures[col] = pd.to_numeric(fixtures[col], errors="coerce").astype("Int64")

    fixtures = fixtures.dropna(
        subset=["fixture_code", "fixture_id", "gameweek"]
    ).copy()

    if fixtures.duplicated("fixture_code").any():
        raise RuntimeError(
            f"{season}: duplicate fixture codes: "
            f"{int(fixtures.duplicated('fixture_code').sum())}"
        )
    if fixtures.duplicated("fixture_id").any():
        raise RuntimeError(
            f"{season}: duplicate fixture IDs: "
            f"{int(fixtures.duplicated('fixture_id').sum())}"
        )

    fixture_gws = validate_gameweeks(fixtures["gameweek"], season)

    lookup = fixtures[["fixture_code", "fixture_id", "gameweek"]].set_index(
        "fixture_code"
    )

    source_codes = pd.to_numeric(
        pdf[pm["fixture_code"]], errors="coerce"
    ).astype("Int64")

    out = pd.DataFrame(index=pdf.index)

    for canonical in CANONICAL_COLUMNS:
        if canonical == "season":
            out[canonical] = season
        elif canonical == "fixture_id":
            out[canonical] = source_codes.map(lookup["fixture_id"])
        elif canonical == "fixture_code":
            out[canonical] = source_codes
        elif canonical == "source_fixture_id":
            out[canonical] = source_codes
        elif canonical == "gameweek":
            out[canonical] = source_codes.map(lookup["gameweek"])
        else:
            src = pm.get(canonical)
            out[canonical] = pdf[src] if src else pd.NA

    for col in [
        "player_id",
        "fixture_id",
        "fixture_code",
        "source_fixture_id",
        "gameweek",
        "team_id",
        "value",
        "selected",
        "transfers_in",
        "transfers_out",
        "transfers_balance",
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
        "total_points",
        "team_a_score",
        "team_h_score",
    ]:
        if col in out:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    for col in ["player_id", "fixture_id", "fixture_code", "source_fixture_id", "gameweek"]:
        out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")

    unmatched = int(out["gameweek"].isna().sum())
    if unmatched:
        sample = (
            out.loc[out["gameweek"].isna(), "fixture_code"]
            .dropna()
            .drop_duplicates()
            .astype(int)
            .tolist()[:20]
        )
        raise RuntimeError(
            f"{season}: {unmatched} player rows have fixture codes "
            f"not present in fixtures.code; sample: {sample}"
        )

    dup = int(out.duplicated(["player_id", "fixture_id"]).sum())
    if dup:
        raise RuntimeError(
            f"{season}: {dup} duplicate player-fixture rows"
        )

    out = out.dropna(
        subset=["player_id", "fixture_id", "gameweek"]
    ).copy()
    out = out.sort_values(
        ["gameweek", "player_id", "fixture_id"]
    ).reset_index(drop=True)

    stats = {
        "source_profile": "fixture_code",
        "source_rows": len(pdf),
        "normalized_rows": len(out),
        "unique_players": int(out["player_id"].nunique()),
        "unique_fixtures": int(out["fixture_id"].nunique()),
        "unique_player_fixture_pairs": int(
            out[["player_id", "fixture_id"]].drop_duplicates().shape[0]
        ),
        "unique_player_gameweeks": int(
            out[["player_id", "gameweek"]].drop_duplicates().shape[0]
        ),
        "gameweeks": sorted(int(x) for x in out["gameweek"].unique()),
        "unmatched_fixture_rows": unmatched,
        "duplicate_player_fixture_rows": dup,
        "fixture_rows": len(fixtures),
        "fixture_gameweeks": fixture_gws,
        "player_mapping": pm,
        "fixture_mapping": fm,
    }

    return out, fixtures, stats


def normalize_2023_24(season: str, pdf: pd.DataFrame):
    """
    2023-24 archive style:
        GW            -> gameweek
        fixture       -> fixture_id / source_fixture_id
        kickoff_time  -> kickoff_time

    No external fixture table is required.
    """
    pm = mapping(pdf.columns, PLAYER_ALIASES)

    for required in ("player_id", "gameweek", "source_fixture_id"):
        if required not in pm:
            raise RuntimeError(
                f"{season}: 2023-24 source missing '{required}'; "
                f"columns: {list(pdf.columns)}"
            )

    gameweeks = validate_gameweeks(pdf[pm["gameweek"]], season)

    fixture_series = pd.to_numeric(
        pdf[pm["source_fixture_id"]], errors="coerce"
    ).astype("Int64")
    gw_series = pd.to_numeric(
        pdf[pm["gameweek"]], errors="coerce"
    ).astype("Int64")
    player_series = pd.to_numeric(
        pdf[pm["player_id"]], errors="coerce"
    ).astype("Int64")

    if fixture_series.isna().any():
        raise RuntimeError(
            f"{season}: source fixture contains missing values."
        )
    if player_series.isna().any():
        raise RuntimeError(
            f"{season}: player ID contains missing values."
        )

    out = pd.DataFrame(index=pdf.index)

    for canonical in CANONICAL_COLUMNS:
        if canonical == "season":
            out[canonical] = season
        elif canonical == "player_id":
            out[canonical] = player_series
        elif canonical == "gameweek":
            out[canonical] = gw_series
        elif canonical == "fixture_id":
            # The archive's fixture identifier is the authoritative
            # season-local fixture key for this source profile.
            out[canonical] = fixture_series
        elif canonical == "source_fixture_id":
            out[canonical] = fixture_series
        elif canonical == "fixture_code":
            out[canonical] = pd.NA
        else:
            src = pm.get(canonical)
            out[canonical] = pdf[src] if src else pd.NA

    numeric_columns = [
        "player_id",
        "gameweek",
        "fixture_id",
        "source_fixture_id",
        "value",
        "selected",
        "transfers_in",
        "transfers_out",
        "transfers_balance",
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
        "total_points",
        "influence",
        "creativity",
        "threat",
        "ict_index",
        "expected_goals",
        "expected_assists",
        "expected_goal_involvements",
        "expected_goals_conceded",
        "xP",
        "team_a_score",
        "team_h_score",
        "round",
    ]

    for col in numeric_columns:
        if col in out:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    for col in [
        "player_id",
        "gameweek",
        "fixture_id",
        "source_fixture_id",
    ]:
        out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")

    # Validate the source's fixture/GW relationship.
    fixture_gw = (
        out[["fixture_id", "gameweek"]]
        .drop_duplicates()
        .groupby("fixture_id")["gameweek"]
        .nunique()
    )
    bad_fixture_gw = fixture_gw[fixture_gw > 1]
    if len(bad_fixture_gw):
        raise RuntimeError(
            f"{season}: {len(bad_fixture_gw)} fixtures appear in multiple "
            f"gameweeks; sample: {bad_fixture_gw.index.tolist()[:20]}"
        )

    pair_duplicates = int(
        out.duplicated(
            ["player_id", "gameweek", "source_fixture_id"]
        ).sum()
    )
    if pair_duplicates:
        raise RuntimeError(
            f"{season}: {pair_duplicates} duplicate "
            "player-GW-fixture rows"
        )

    out = out.dropna(
        subset=["player_id", "gameweek", "fixture_id"]
    ).copy()

    out = out.sort_values(
        ["gameweek", "player_id", "fixture_id"]
    ).reset_index(drop=True)

    # Build a canonical fixture table from the source rows.
    fixture_columns = [
        "season",
        "fixture_id",
        "source_fixture_id",
        "gameweek",
        "fixture_code",
        "kickoff_time",
        "team_h",
        "team_a",
        "team_h_score",
        "team_a_score",
    ]

    fixture_rows = []
    for fixture_id, group in out.groupby("fixture_id", sort=True):
        row = {
            "season": season,
            "fixture_id": fixture_id,
            "source_fixture_id": fixture_id,
            "gameweek": group["gameweek"].iloc[0],
            "fixture_code": pd.NA,
            "kickoff_time": group["kickoff_time"].dropna().iloc[0]
            if group["kickoff_time"].notna().any()
            else pd.NA,
            "team_h": pd.NA,
            "team_a": pd.NA,
            "team_h_score": (
                group["team_h_score"].dropna().iloc[0]
                if group["team_h_score"].notna().any()
                else pd.NA
            ),
            "team_a_score": (
                group["team_a_score"].dropna().iloc[0]
                if group["team_a_score"].notna().any()
                else pd.NA
            ),
        }

        # Team/opponent reconstruction is only used as a source-derived
        # convenience field. We do not use it to determine gameweek.
        if "team" in out.columns and "opponent_team" in out.columns:
            pairs = (
                group[["team", "opponent_team", "was_home"]]
                .drop_duplicates()
            )
            home = pairs[pairs["was_home"] == True]
            away = pairs[pairs["was_home"] == False]

            if not home.empty:
                row["team_h"] = home["team"].iloc[0]
                row["team_a"] = home["opponent_team"].iloc[0]
            elif not away.empty:
                row["team_a"] = away["team"].iloc[0]
                row["team_h"] = away["opponent_team"].iloc[0]

        fixture_rows.append(row)

    fixtures = pd.DataFrame(fixture_rows, columns=fixture_columns)

    if len(fixtures) != 380:
        raise RuntimeError(
            f"{season}: expected 380 unique fixtures, found {len(fixtures)}"
        )

    if fixtures["fixture_id"].duplicated().any():
        raise RuntimeError(
            f"{season}: duplicate canonical fixture IDs"
        )

    if fixtures["gameweek"].isna().any():
        raise RuntimeError(
            f"{season}: canonical fixture table contains missing gameweeks"
        )

    stats = {
        "source_profile": "GW_fixture",
        "source_rows": len(pdf),
        "normalized_rows": len(out),
        "unique_players": int(out["player_id"].nunique()),
        "unique_fixtures": int(out["fixture_id"].nunique()),
        "unique_player_fixture_pairs": int(
            out[["player_id", "fixture_id"]].drop_duplicates().shape[0]
        ),
        "unique_player_gameweeks": int(
            out[["player_id", "gameweek"]].drop_duplicates().shape[0]
        ),
        "gameweeks": gameweeks,
        "fixture_rows": len(fixtures),
        "duplicate_player_gameweek_fixture_rows": pair_duplicates,
        "fixtures_in_multiple_gameweeks": 0,
        "player_mapping": pm,
    }

    return out, fixtures, stats


def parse_args():
    parser = argparse.ArgumentParser(
        description="Normalize historical FPL seasons into a canonical schema."
    )
    parser.add_argument(
        "--seasons",
        nargs="+",
        default=list(DEFAULT_SEASONS),
    )
    parser.add_argument("--project-root")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    logging.basicConfig(
        level=(
            logging.DEBUG
            if args.verbose
            else logging.WARNING
            if args.quiet
            else logging.INFO
        ),
        format="[%(levelname)-8s] %(message)s",
    )

    seasons = []
    for season in args.seasons:
        if not SEASON_RE.fullmatch(season):
            raise ValueError(
                f"Invalid season '{season}'. Expected YYYY-YY."
            )
        if season not in seasons:
            seasons.append(season)

    root = (
        Path(args.project_root).expanduser().resolve()
        if args.project_root
        else Path(__file__).resolve().parents[2]
    )

    LOG.info("FPL HISTORICAL NORMALIZER")
    LOG.info("=" * 72)
    LOG.info("Version      : %s", VERSION)
    LOG.info("Project root : %s", root)
    LOG.info("Seasons      : %s", ", ".join(seasons))
    LOG.info("Protected    : %s", LIVE_SEASON)

    failures = []

    for season in seasons:
        try:
            if season == LIVE_SEASON:
                raise RuntimeError(
                    "2026-27 is the live season and is protected."
                )

            src = root / "data" / "raw" / season / "historical_source"
            outdir = root / "data" / "processed" / season / "historical"

            player_path = src / "player_gameweek.csv"
            fixture_path = src / "fixtures.csv"

            if not player_path.exists():
                raise FileNotFoundError(player_path)

            LOG.info("")
            LOG.info("=" * 72)
            LOG.info("NORMALIZING HISTORICAL SEASON: %s", season)
            LOG.info("=" * 72)
            LOG.info("Source : %s", src)
            LOG.info("Output : %s", outdir)

            player_sample = pd.read_csv(
                player_path, nrows=5, low_memory=False
            )

            fixture_sample = None
            if fixture_path.exists():
                fixture_sample = pd.read_csv(
                    fixture_path, nrows=5, low_memory=False
                )

            LOG.info(
                "Player source columns: %d",
                len(player_sample.columns),
            )

            if fixture_sample is not None:
                LOG.info(
                    "Fixture source columns: %d",
                    len(fixture_sample.columns),
                )
            else:
                LOG.info(
                    "Fixture source: not present; checking player-native schema..."
                )

            # Explicit source-profile selection.
            player_mapping = mapping(
                player_sample.columns, PLAYER_ALIASES
            )

            if (
                season == "2023-24"
                and "gameweek" in player_mapping
                and "source_fixture_id" in player_mapping
            ):
                profile = "GW_fixture"
            elif (
                fixture_sample is not None
                and "fixture_code" in player_mapping
            ):
                profile = "fixture_code"
            else:
                # For future seasons, permit automatic detection only when
                # the source clearly matches one of the supported profiles.
                if (
                    "gameweek" in player_mapping
                    and "source_fixture_id" in player_mapping
                    and fixture_sample is None
                ):
                    profile = "GW_fixture"
                else:
                    raise RuntimeError(
                        f"{season}: unsupported historical schema. "
                        f"Player columns: {list(player_sample.columns)}; "
                        f"fixtures.csv present: {fixture_sample is not None}"
                    )

            LOG.info("Detected source profile: %s", profile)

            if args.dry_run:
                LOG.info("DRY RUN: no files written.")
                continue

            if not args.force:
                for path in (
                    outdir / "player_gameweek.csv",
                    outdir / "fixtures.csv",
                    outdir / "normalization_manifest.json",
                ):
                    if path.exists():
                        raise FileExistsError(
                            f"Output exists: {path}. Use --force to rebuild."
                        )

            LOG.info("Loading player data...")
            pdf = pd.read_csv(player_path, low_memory=False)

            if profile == "fixture_code":
                LOG.info("Loading fixture data...")
                fdf = pd.read_csv(
                    fixture_path, low_memory=False
                )
                LOG.info(
                    "Normalizing fixtures using code -> event..."
                )
                normalized_players, normalized_fixtures, validation = (
                    normalize_modern(season, pdf, fdf)
                )
                join_definition = {
                    "profile": "fixture_code",
                    "player_fixture_code": "player_gameweek.fixture_code",
                    "fixture_code": "fixtures.code",
                    "canonical_gameweek": "fixtures.event",
                    "canonical_fixture_id": "fixtures.id",
                }
            else:
                LOG.info(
                    "Normalizing player-native GW/fixture source..."
                )
                normalized_players, normalized_fixtures, validation = (
                    normalize_2023_24(season, pdf)
                )
                join_definition = {
                    "profile": "GW_fixture",
                    "canonical_gameweek": "player_gameweek.GW",
                    "canonical_fixture_id": "player_gameweek.fixture",
                    "source_fixture_id": "player_gameweek.fixture",
                    "external_fixture_lookup": False,
                }

            LOG.info(
                "Player rows normalized: %d/%d",
                validation["normalized_rows"],
                validation["source_rows"],
            )
            LOG.info(
                "Unique players : %d",
                validation["unique_players"],
            )
            LOG.info(
                "Unique fixtures: %d",
                validation["unique_fixtures"],
            )
            LOG.info(
                "Gameweeks      : %s",
                ", ".join(map(str, validation["gameweeks"])),
            )

            atomic_csv(
                normalized_players,
                outdir / "player_gameweek.csv",
            )
            atomic_csv(
                normalized_fixtures,
                outdir / "fixtures.csv",
            )

            manifest = {
                "schema_version": "1.3.0",
                "normalizer_version": VERSION,
                "season": season,
                "source_profile": profile,
                "normalized_at_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "source_directory": str(src),
                "output_directory": str(outdir),
                "join_definition": join_definition,
                "source_profiles": {
                    "player_gameweek": {
                        "columns": list(map(str, player_sample.columns)),
                        "mapping": player_mapping,
                    }
                },
                "validation": validation,
                "files": {
                    "player_gameweek": str(
                        outdir / "player_gameweek.csv"
                    ),
                    "fixtures": str(
                        outdir / "fixtures.csv"
                    ),
                },
                "design_notes": [
                    "Historical source schemas are adapted into a canonical schema.",
                    "No gameweek is guessed from row order.",
                    "2023-24 uses the source GW field directly.",
                    "2023-24 fixture is treated as the season-local canonical fixture ID.",
                    "2025-26 uses fixtures.code -> fixtures.event/id.",
                    "Missing source fields remain null.",
                    "Available source fields are preserved where they do not conflict with canonical names.",
                    "No lagged or rolling features are created during normalization.",
                    "2026-27 is protected.",
                ],
            }

            atomic_json(
                manifest,
                outdir / "normalization_manifest.json",
            )

            LOG.info("")
            LOG.info("VALIDATION PASSED: %s", season)
            LOG.info(
                "Player-GW rows : %d",
                validation["normalized_rows"],
            )
            LOG.info(
                "Unique players : %d",
                validation["unique_players"],
            )
            LOG.info(
                "Unique fixtures: %d",
                validation["unique_fixtures"],
            )
            LOG.info(
                "Fixtures       : %d",
                validation["fixture_rows"],
            )
            LOG.info(
                "Gameweeks      : %s",
                ", ".join(map(str, validation["gameweeks"])),
            )
            LOG.info(
                "Manifest       : %s",
                outdir / "normalization_manifest.json",
            )

        except Exception as exc:
            LOG.error("FAILED: %s -> %s", season, exc)
            failures.append((season, str(exc)))

    LOG.info("")
    LOG.info("=" * 72)
    LOG.info("NORMALIZATION SUMMARY")
    LOG.info("=" * 72)

    if failures:
        for season, error in failures:
            LOG.error("%-10s FAIL: %s", season, error)
        return 1

    LOG.info(
        "All requested historical seasons normalized successfully."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

out = Path("/mnt/data/normalize_historical_seasons_v1_3.py")
out.write_text(script, encoding="utf-8")

# Basic syntax validation.
compile(script, str(out), "exec")

print(f"Created and syntax-validated: {out}")
print(f"Version: 1.3.0")
print(f"Lines: {len(script.splitlines())}")
