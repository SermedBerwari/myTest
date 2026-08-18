from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


SEASON_TEAMS = {
    "2022-23": [
        "Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton",
        "Chelsea", "Crystal Palace", "Everton", "Fulham", "Leeds",
        "Leicester", "Liverpool", "Man City", "Man Utd", "Newcastle",
        "Nott'm Forest", "Southampton", "Spurs", "West Ham", "Wolves",
    ],
}


POSITION_MAP = {
    "GK": (1, "Goalkeeper"),
    "DEF": (2, "Defender"),
    "MID": (3, "Midfielder"),
    "FWD": (4, "Forward"),
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", required=True)
    return parser.parse_args()



def normalize_fixture_team_ids(
    fixtures: pd.DataFrame,
    pgw: pd.DataFrame,
    season: str,
) -> pd.DataFrame:
    """
    Ensure fixture team_h/team_a are canonical numeric team IDs.

    Historical normalized fixture sources may contain team names in one or
    both columns. The player-GW source contains the canonical numeric
    team_id/opponent_team relationship, so derive the mapping from the same
    season instead of hard-coding club names.
    """
    fixtures = fixtures.copy()

    if "team_h" not in fixtures.columns or "team_a" not in fixtures.columns:
        raise RuntimeError(
            f"{season}: fixtures.csv must contain team_h and team_a."
        )

    required = {"team_id", "team", "opponent_team", "was_home"}
    missing = required - set(pgw.columns)
    if missing:
        raise RuntimeError(
            f"{season}: player_gameweek.csv missing mapping columns: "
            f"{sorted(missing)}"
        )

    team_map = {}

    pairs = pgw[["team_id", "team"]].dropna().copy()
    pairs["team_id"] = pd.to_numeric(pairs["team_id"], errors="coerce")
    pairs = pairs.dropna(subset=["team_id"])

    for _, row in pairs.drop_duplicates().iterrows():
        name = str(row["team"]).strip().lower()
        if not name:
            continue
        team_id = int(row["team_id"])
        existing = team_map.get(name)
        if existing is not None and existing != team_id:
            raise RuntimeError(
                f"{season}: conflicting team mapping for '{row['team']}': "
                f"{existing} vs {team_id}"
            )
        team_map[name] = team_id

    def resolve(value):
        numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        if pd.notna(numeric):
            return int(numeric)

        key = str(value).strip().lower()
        return team_map.get(key, pd.NA)

    for col in ("team_h", "team_a"):
        fixtures[col] = fixtures[col].map(resolve).astype("Int64")

        if fixtures[col].isna().any():
            bad = (
                fixtures.loc[fixtures[col].isna(), col]
                .drop_duplicates()
                .astype(str)
                .tolist()[:20]
            )
            raise RuntimeError(
                f"{season}: unable to resolve {col} to numeric team IDs. "
                f"Unresolved sample: {bad}"
            )

    if len(fixtures) != 380:
        raise RuntimeError(
            f"{season}: expected 380 fixtures, found {len(fixtures)}"
        )

    if fixtures["fixture_id"].duplicated().any():
        raise RuntimeError(
            f"{season}: duplicate fixture_id values detected."
        )

    return fixtures


def main():
    args = parse_args()
    season = args.season

    root = Path(__file__).resolve().parents[2]

    historical_dir = (
        root / "data" / "processed" / season / "historical"
    )

    output_dir = root / "data" / "processed" / season

    raw_player_path = (
        root / "data" / "raw" / season /
        "historical_source" / "player_gameweek.csv"
    )

    player_path = historical_dir / "player_gameweek.csv"
    fixture_path = historical_dir / "fixtures.csv"

    if not player_path.exists():
        raise RuntimeError(f"Missing: {player_path}")

    if not fixture_path.exists():
        raise RuntimeError(f"Missing: {fixture_path}")

    if not raw_player_path.exists():
        raise RuntimeError(f"Missing: {raw_player_path}")

    print("=" * 72)
    print("FPL HISTORICAL DATASET PREPARATION")
    print("=" * 72)
    print(f"Season : {season}")
    print(f"Input  : {historical_dir}")
    print(f"Output : {output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    pgw = pd.read_csv(player_path)
    fixtures = pd.read_csv(fixture_path)
    raw = pd.read_csv(raw_player_path)

    fixtures = normalize_fixture_team_ids(
        fixtures,
        pgw,
        season,
    )

    # ------------------------------------------------------------------
    # 1. player_gameweek.csv
    # ------------------------------------------------------------------

    required_pgw = [
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
    ]

    missing = [c for c in required_pgw if c not in pgw.columns]
    if missing:
        raise RuntimeError(
            f"player_gameweek.csv missing columns: {missing}"
        )

    pgw.to_csv(
        output_dir / "player_gameweek.csv",
        index=False,
    )
    fixtures.to_csv(
    output_dir / "fixtures.csv",
    index=False,
)

    # ------------------------------------------------------------------
    # 2. players.csv
    # ------------------------------------------------------------------

    players = (
        raw[["element", "name", "position"]]
        .drop_duplicates("element")
        .copy()
    )

    players["element"] = pd.to_numeric(
        players["element"], errors="coerce"
    )

    players = players.dropna(subset=["element"])

    players["player_id"] = players["element"].astype(int)

    players["first_name"] = players["name"].fillna("").apply(
        lambda x: str(x).split(" ", 1)[0]
    )

    players["second_name"] = players["name"].fillna("").apply(
        lambda x: str(x).split(" ", 1)[1]
        if len(str(x).split(" ", 1)) > 1
        else ""
    )

    players["web_name"] = players["name"]

    players["position_id"] = players["position"].map(
        lambda x: POSITION_MAP.get(str(x), (None, None))[0]
    )

    players["position_name"] = players["position"].map(
        lambda x: POSITION_MAP.get(str(x), (None, None))[1]
    )

    players = players[
        [
            "player_id",
            "first_name",
            "second_name",
            "web_name",
            "position_id",
            "position_name",
        ]
    ].drop_duplicates("player_id")

    players.to_csv(
        output_dir / "players.csv",
        index=False,
    )

    # ------------------------------------------------------------------
    # 3. teams.csv
    # ------------------------------------------------------------------

    team_names = SEASON_TEAMS.get(season)

    if team_names is None:
        team_names = sorted(
            set(raw["team"].dropna().astype(str))
        )

    teams = pd.DataFrame(
        {
            "team_id": range(1, len(team_names) + 1),
            "name": team_names,
            "short_name": team_names,
        }
    )

    teams.to_csv(
        output_dir / "teams.csv",
        index=False,
    )

    # ------------------------------------------------------------------
    # 4. gameweeks.csv
    # ------------------------------------------------------------------

    pgw["gameweek"] = pd.to_numeric(
        pgw["gameweek"], errors="coerce"
    )

    pgw["kickoff_time"] = pd.to_datetime(
        pgw["kickoff_time"], utc=True, errors="coerce"
    )

    # FPL deadline is normally before the first kickoff.
    # For historical feature generation, we use a deterministic
    # season-local proxy: one hour before the earliest kickoff.
    gameweeks = []

    for gw, group in pgw.groupby("gameweek"):
        if pd.isna(gw):
            continue

        earliest = group["kickoff_time"].min()

        deadline = earliest - pd.Timedelta(hours=1)

        gameweeks.append(
            {
                "gameweek": int(gw),
                "deadline_time": deadline.isoformat(),
            }
        )

    gameweeks = pd.DataFrame(gameweeks).sort_values(
        "gameweek"
    )

    gameweeks.to_csv(
        output_dir / "gameweeks.csv",
        index=False,
    )

    # ------------------------------------------------------------------
    # 5. player_season_history.csv
    # ------------------------------------------------------------------

    # The production feature builder calculates rolling history directly
    # from player_gameweek.csv. This file is therefore a compatibility
    # artifact rather than an independent feature source.

    history = (
        pgw.groupby("player_id", as_index=False)
        .agg(
            appearances=("gameweek", "count"),
            total_minutes=("minutes", "sum"),
            total_points=("total_points", "sum"),
            goals=("goals_scored", "sum"),
            assists=("assists", "sum"),
        )
    )

    history.insert(1, "season", season)

    history.to_csv(
        output_dir / "player_season_history.csv",
        index=False,
    )

    # ------------------------------------------------------------------
    # 6. dataset_manifest.json
    # ------------------------------------------------------------------

    manifest = {
        "schema_version": "historical-feature-input-1.1",
        "season": season,
        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),

        "source": {
            "type": "historical_normalized_dataset",
            "directory": str(historical_dir),
        },

        "input_counts": {
            "players": int(len(players)),
            "fixtures": int(len(fixtures)),
            "gameweeks": int(len(gameweeks)),
            "player_gameweek_rows": int(len(pgw)),
        },

        "files": {
            "players.csv": "players.csv",
            "teams.csv": "teams.csv",
            "gameweeks.csv": "gameweeks.csv",
            "fixtures.csv": "fixtures.csv",
            "player_gameweek.csv": "player_gameweek.csv",
            "player_season_history.csv": "player_season_history.csv",
        },

        "leakage_policy": {
            "historical_features": "gameweek < target_gameweek",
            "target": "gameweek == target_gameweek",
            "current_aggregate_fields_excluded": True,
        },

        "notes": [
            "Historical source does not provide official bootstrap snapshots.",
            "Stable player identity is reconstructed from historical player records.",
            "Gameweek deadlines are deterministic historical proxies.",
            "Rolling model features must be calculated from prior gameweeks only.",
            "Fixture team_h/team_a values are normalized to numeric team IDs before feature preparation.",
            "Fixture team mapping is derived from the same season's player_gameweek team_id/team fields.",
        ],
    }

    with open(
        output_dir / "dataset_manifest.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(manifest, f, indent=2)

    print()
    print("PREPARATION COMPLETE")
    print(f"Players       : {len(players)}")
    print(f"Fixtures      : {len(fixtures)}")
    print(
        "Fixture teams : "
        f"{fixtures['team_h'].notna().all() and fixtures['team_a'].notna().all()}"
    )
    print(f"Gameweeks     : {len(gameweeks)}")
    print(f"Player-GW rows: {len(pgw)}")
    print(f"Output        : {output_dir}")


if __name__ == "__main__":
    main()
