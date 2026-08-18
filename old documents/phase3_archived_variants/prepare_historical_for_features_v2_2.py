"""
prepare_historical_for_features_v2.py
======================================
Converts a normalized historical season (data/processed/<season>/historical/)
into the flat file layout expected by build_features_v1_3.py.

Input  : data/processed/<season>/historical/{player_gameweek.csv, fixtures.csv}
Output : data/processed/<season>/{players.csv, teams.csv, gameweeks.csv,
          fixtures.csv, player_gameweek.csv, player_season_history.csv,
          dataset_manifest.json}

Works for any historical season. Falls back gracefully when team names are
missing by using team_code as a unique identifier and resolving names from
the live bootstrap snapshot when available.
"""

from __future__ import annotations

import argparse
import glob
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

VERSION = "2.2.0"

POSITION_MAP = {
    "GK": (1, "Goalkeeper"),
    "GKP": (1, "Goalkeeper"),
    "DEF": (2, "Defender"),
    "MID": (3, "Midfielder"),
    "FWD": (4, "Forward"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare normalized historical season for feature building."
    )
    parser.add_argument("--season", required=True, help="e.g. 2023-24")
    parser.add_argument(
        "--project-root",
        default=None,
        help="Project root. Defaults to two levels above this script.",
    )
    return parser.parse_args()


def load_bootstrap_team_map(root: Path) -> dict[int, str]:
    """Load team_code -> team_name mapping from the latest bootstrap snapshot."""
    bootstrap_dir = root / "data" / "raw" / "2026-27" / "bootstrap"
    snapshots = sorted(bootstrap_dir.glob("*.json"))
    if not snapshots:
        return {}
    latest = snapshots[-1]
    try:
        with open(latest, encoding="utf-8") as f:
            data = json.load(f)
        teams = data.get("teams", [])
        return {int(t["code"]): str(t["name"]) for t in teams if "code" in t and "name" in t}
    except Exception as e:
        print(f"  Warning: Could not load bootstrap teams: {e}")
        return {}


def build_teams_df(pgw: pd.DataFrame, bootstrap_map: dict[int, str]) -> pd.DataFrame:
    """
    Build a teams DataFrame with sequential team_id (1-20).
    Strategy:
      1. Use 'team' column if present and non-null.
      2. Fall back to resolving 'team_code' via bootstrap_map.
      3. Fall back to using team_code as name.
    """
    if "team" in pgw.columns and pgw["team"].notna().any():
        # Have team names — derive from them
        team_series = pgw["team"].dropna().astype(str)
        unique_names = sorted(team_series.unique().tolist())
        return pd.DataFrame({
            "team_id": range(1, len(unique_names) + 1),
            "name": unique_names,
            "short_name": unique_names,
            "team_code": [None] * len(unique_names),
        })

    if "team_code" in pgw.columns and pgw["team_code"].notna().any():
        unique_codes = sorted(pgw["team_code"].dropna().unique().astype(int).tolist())
        names = [bootstrap_map.get(c, f"Team_{c}") for c in unique_codes]
        return pd.DataFrame({
            "team_id": range(1, len(unique_codes) + 1),
            "name": names,
            "short_name": names,
            "team_code": unique_codes,
        })

    raise RuntimeError("Cannot determine team identifiers from player_gameweek data.")


def resolve_fixtures(
    fixtures: pd.DataFrame, teams_df: pd.DataFrame, season: str
) -> pd.DataFrame:
    """
    Ensure fixture team_h / team_a are sequential integer team_ids (1-N).

    Handles mixed columns: values may be numeric team IDs (from raw source),
    team names (strings), or team_codes. Builds a unified lookup covering all
    possible representations present in teams_df.
    """
    fixtures = fixtures.copy()

    # Build a comprehensive lookup: any identifier -> sequential team_id
    lookup: dict = {}

    for _, row in teams_df.iterrows():
        tid = int(row["team_id"])
        name = str(row["name"]).strip().lower()
        lookup[name] = tid

        if pd.notna(row.get("team_code")):
            code = int(row["team_code"])
            lookup[code] = tid

    # Check if team_h and team_a are already valid sequential team_ids (1..len(teams_df))
    valid_team_ids = set(teams_df["team_id"].astype(int))
    h_set = set(pd.to_numeric(fixtures.get("team_h"), errors="coerce").dropna().astype(int))
    a_set = set(pd.to_numeric(fixtures.get("team_a"), errors="coerce").dropna().astype(int))

    if h_set and a_set and h_set.issubset(valid_team_ids) and a_set.issubset(valid_team_ids):
        fixtures["team_h"] = pd.to_numeric(fixtures["team_h"]).astype("Int64")
        fixtures["team_a"] = pd.to_numeric(fixtures["team_a"]).astype("Int64")
        return fixtures

    def resolve_col(series: pd.Series) -> pd.Series:
        result = []
        for v in series:
            if pd.isna(v) or str(v).strip() == "":
                result.append(pd.NA)
                continue
            # Try numeric first
            try:
                numeric_v = int(float(str(v)))
                if numeric_v in lookup:
                    result.append(lookup[numeric_v])
                    continue
            except (ValueError, TypeError):
                pass
            # Try string name lookup
            name_key = str(v).strip().lower()
            if name_key in lookup:
                result.append(lookup[name_key])
            else:
                result.append(pd.NA)
        return pd.array(result, dtype="Int64")

    for col in ("team_h", "team_a"):
        if col in fixtures.columns:
            fixtures[col] = resolve_col(fixtures[col])

    return fixtures


def reconstruct_fixture_teams(
    fixtures: pd.DataFrame,
    pgw: pd.DataFrame,
    teams_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Fill in missing team_h / team_a by deriving them from player_gameweek data.

    For each fixture_id:
      - Home team  = team_id of players where was_home=True
      - Away team  = team_id of players where was_home=False

    This handles cases where the normalization step only recorded one team column.
    Requires pgw to have team_id already resolved (call after resolve_pgw_team_id).
    """
    fixtures = fixtures.copy()

    # Build team_id mapping per fixture from player data
    pgw_copy = pgw.copy()
    pgw_copy["fixture_id"] = pd.to_numeric(pgw_copy.get("fixture_id"), errors="coerce")
    pgw_copy["team_id"] = pd.to_numeric(pgw_copy.get("team_id"), errors="coerce")

    def parse_was_home(v):
        if pd.isna(v):
            return None
        s = str(v).strip().lower()
        if s in ("true", "1", "yes"):
            return True
        if s in ("false", "0", "no"):
            return False
        return None

    pgw_copy["_was_home"] = pgw_copy["was_home"].map(parse_was_home)

    # home team per fixture
    home_df = (
        pgw_copy[pgw_copy["_was_home"] == True]
        .groupby("fixture_id")["team_id"]
        .agg(lambda x: x.dropna().mode().iloc[0] if x.dropna().any() else pd.NA)
        .reset_index()
        .rename(columns={"team_id": "_team_h_derived"})
    )

    # away team per fixture
    away_df = (
        pgw_copy[pgw_copy["_was_home"] == False]
        .groupby("fixture_id")["team_id"]
        .agg(lambda x: x.dropna().mode().iloc[0] if x.dropna().any() else pd.NA)
        .reset_index()
        .rename(columns={"team_id": "_team_a_derived"})
    )

    fixtures = fixtures.merge(home_df, on="fixture_id", how="left")
    fixtures = fixtures.merge(away_df, on="fixture_id", how="left")

    # Fill missing team_h / team_a with derived values
    if "team_h" not in fixtures.columns:
        fixtures["team_h"] = pd.NA
    if "team_a" not in fixtures.columns:
        fixtures["team_a"] = pd.NA

    fixtures["team_h"] = pd.to_numeric(fixtures["team_h"], errors="coerce")
    fixtures["team_a"] = pd.to_numeric(fixtures["team_a"], errors="coerce")

    # Replace NaN with derived
    mask_h = fixtures["team_h"].isna()
    mask_a = fixtures["team_a"].isna()

    if mask_h.any() and "_team_h_derived" in fixtures.columns:
        fixtures.loc[mask_h, "team_h"] = fixtures.loc[mask_h, "_team_h_derived"]
    if mask_a.any() and "_team_a_derived" in fixtures.columns:
        fixtures.loc[mask_a, "team_a"] = fixtures.loc[mask_a, "_team_a_derived"]

    fixtures["team_h"] = pd.to_numeric(fixtures["team_h"], errors="coerce").astype("Int64")
    fixtures["team_a"] = pd.to_numeric(fixtures["team_a"], errors="coerce").astype("Int64")

    fixtures.drop(columns=["_team_h_derived", "_team_a_derived"], inplace=True, errors="ignore")

    # Report
    missing_h = fixtures["team_h"].isna().sum()
    missing_a = fixtures["team_a"].isna().sum()
    if missing_h > 0 or missing_a > 0:
        print(f"  Warning: {missing_h} fixtures missing team_h, {missing_a} missing team_a after reconstruction")
    else:
        print(f"  Fixture teams: fully resolved (team_h + team_a for all {len(fixtures)} fixtures)")

    return fixtures




def resolve_pgw_team_id(pgw: pd.DataFrame, teams_df: pd.DataFrame) -> pd.DataFrame:
    """Add/fix team_id column in player_gameweek using teams_df as lookup."""
    pgw = pgw.copy()

    if teams_df["team_code"].notna().all():
        # Map player team_code -> sequential team_id
        code_to_id = dict(zip(teams_df["team_code"].astype(int), teams_df["team_id"]))
        if "team_code" in pgw.columns:
            pgw["team_id"] = (
                pd.to_numeric(pgw["team_code"], errors="coerce")
                .map(lambda v: code_to_id.get(int(v)) if pd.notna(v) else pd.NA)
            )
    else:
        # Map player team name -> sequential team_id
        name_to_id = dict(zip(teams_df["name"].str.strip().str.lower(), teams_df["team_id"]))
        if "team" in pgw.columns:
            pgw["team_id"] = (
                pgw["team"].astype(str).str.strip().str.lower()
                .map(name_to_id)
            )

    return pgw


def main() -> None:
    args = parse_args()
    season = args.season

    root = (
        Path(args.project_root).resolve()
        if args.project_root
        else Path(__file__).resolve().parents[2]
    )

    historical_dir = root / "data" / "processed" / season / "historical"
    output_dir = root / "data" / "processed" / season

    player_path = historical_dir / "player_gameweek.csv"
    fixture_path = historical_dir / "fixtures.csv"

    print("=" * 72)
    print(f"FPL HISTORICAL DATASET PREPARATION  (v{VERSION})")
    print("=" * 72)
    print(f"Season      : {season}")
    print(f"Input       : {historical_dir}")
    print(f"Output      : {output_dir}")

    for p in (player_path, fixture_path):
        if not p.exists():
            raise RuntimeError(f"Missing required file: {p}")

    output_dir.mkdir(parents=True, exist_ok=True)

    pgw_raw = pd.read_csv(player_path)
    fixtures_hist = pd.read_csv(fixture_path)

    # HISTORICAL PLAYER FILTER — v2.2
    # Only official FPL player positions are allowed.
    # The normalized historical source also contains manager records
    # with position="AM"; those are not FPL fantasy players.
    if "position" not in pgw_raw.columns:
        raise RuntimeError(
            f"{season}: historical player_gameweek.csv is missing the "
            "required position column."
        )

    valid_positions = set(POSITION_MAP)
    normalized_position = (
        pgw_raw["position"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    invalid_mask = ~normalized_position.isin(valid_positions)
    excluded = pgw_raw.loc[invalid_mask].copy()

    if not excluded.empty:
        excluded_ids = (
            pd.to_numeric(excluded["player_id"], errors="coerce")
            .dropna()
            .astype(int)
            .drop_duplicates()
            .sort_values()
            .tolist()
        )
        excluded_positions = (
            excluded["position"]
            .fillna("<missing>")
            .astype(str)
            .value_counts()
            .to_dict()
        )

        print(
            f"HISTORICAL PLAYER FILTER: excluded {len(excluded)} "
            f"non-FPL player-GW rows across {len(excluded_ids)} player IDs."
        )
        print(f"  Excluded positions: {excluded_positions}")
        print(f"  Excluded player IDs: {excluded_ids}")

    pgw_raw = pgw_raw.loc[~invalid_mask].copy()

    if pgw_raw.empty:
        raise RuntimeError(
            f"{season}: no valid FPL player rows remain after filtering."
        )

    # Load bootstrap team map for fallback (team_code -> name)
    bootstrap_map = load_bootstrap_team_map(root)
    print(f"Bootstrap   : {len(bootstrap_map)} team codes loaded")

    # ------------------------------------------------------------------
    # 1. teams.csv
    # ------------------------------------------------------------------
    teams_df = build_teams_df(pgw_raw, bootstrap_map)
    teams_df.to_csv(output_dir / "teams.csv", index=False)
    print(f"teams.csv   : {len(teams_df)} teams")

    # ------------------------------------------------------------------
    # 2. Resolve player_gameweek team_id
    # ------------------------------------------------------------------
    pgw = resolve_pgw_team_id(pgw_raw, teams_df)

    # Also add team name for seasons that only have team_code
    if teams_df["team_code"].notna().all() and ("team" not in pgw.columns or pgw["team"].isna().all()):
        code_to_name = dict(zip(teams_df["team_code"].astype(int), teams_df["name"]))
        if "team_code" in pgw.columns:
            pgw["team"] = (
                pd.to_numeric(pgw["team_code"], errors="coerce")
                .map(lambda v: code_to_name.get(int(v)) if pd.notna(v) else pd.NA)
            )

    # ------------------------------------------------------------------
    # 3. players.csv
    # ------------------------------------------------------------------
    pos_col = "position" if "position" in pgw.columns else None
    fn_col = "first_name" if "first_name" in pgw.columns else None
    sn_col = "second_name" if "second_name" in pgw.columns else None
    nm_col = "player_name" if "player_name" in pgw.columns else None

    players = pgw[["player_id"]].drop_duplicates("player_id").copy()

    players["first_name"] = pgw.drop_duplicates("player_id").set_index("player_id").reindex(players["player_id"])[fn_col].values if fn_col else ""
    players["second_name"] = pgw.drop_duplicates("player_id").set_index("player_id").reindex(players["player_id"])[sn_col].values if sn_col else ""
    
    # Construct web_name from player_name or first_name + second_name
    names_from_pgw = pgw.drop_duplicates("player_id").set_index("player_id").reindex(players["player_id"])[nm_col].values if nm_col else None
    web_names = []
    for i in range(len(players)):
        row = players.iloc[i]
        p_name = names_from_pgw[i] if names_from_pgw is not None else None
        if pd.notna(p_name) and str(p_name).strip():
            web_names.append(str(p_name).strip())
        else:
            fn = str(row["first_name"]).strip() if pd.notna(row["first_name"]) else ""
            sn = str(row["second_name"]).strip() if pd.notna(row["second_name"]) else ""
            full = f"{fn} {sn}".strip()
            web_names.append(full if full else f"Player_{row['player_id']}")
    players["web_name"] = web_names

    pos_series = (
        pgw.drop_duplicates("player_id").set_index("player_id").reindex(players["player_id"])[pos_col]
        if pos_col else pd.Series([""] * len(players))
    )
    players["position_id"] = pos_series.map(
        lambda x: POSITION_MAP.get(str(x), (None, None))[0]
    ).values
    players["position_name"] = pos_series.map(
        lambda x: POSITION_MAP.get(str(x), (None, None))[1]
    ).values

    invalid_player_rows = players[
        players["position_id"].isna() | players["position_name"].isna()
    ]

    if not invalid_player_rows.empty:
        raise RuntimeError(
            f"{season}: player universe contains unmapped positions after filtering."
        )

    players = players.sort_values("player_id").reset_index(drop=True)
    players.to_csv(output_dir / "players.csv", index=False)
    print(f"players.csv : {len(players)} players")

    # ------------------------------------------------------------------
    # 4. fixtures.csv
    # ------------------------------------------------------------------
    fixtures = resolve_fixtures(fixtures_hist, teams_df, season)
    fixtures = reconstruct_fixture_teams(fixtures, pgw, teams_df)
    fixtures.to_csv(output_dir / "fixtures.csv", index=False)
    print(f"fixtures.csv: {len(fixtures)} fixtures")

    # ------------------------------------------------------------------
    # 5. player_gameweek.csv — write resolved version
    # ------------------------------------------------------------------
    pgw.to_csv(output_dir / "player_gameweek.csv", index=False)
    print(f"player_gameweek.csv: {len(pgw)} rows")

    # ------------------------------------------------------------------
    # 6. gameweeks.csv
    # ------------------------------------------------------------------
    pgw_copy = pgw.copy()
    pgw_copy["gameweek"] = pd.to_numeric(pgw_copy["gameweek"], errors="coerce")
    pgw_copy["kickoff_time"] = pd.to_datetime(pgw_copy.get("kickoff_time"), utc=True, errors="coerce")

    # If player_gameweek has no kickoff_time, pull it from fixtures via fixture_id
    if pgw_copy["kickoff_time"].isna().all() and "fixture_id" in pgw_copy.columns:
        fix_kt = fixtures[["fixture_id", "gameweek", "kickoff_time"]].copy()
        fix_kt["kickoff_time"] = pd.to_datetime(fix_kt["kickoff_time"], utc=True, errors="coerce")
        gw_earliest = fix_kt.groupby("gameweek")["kickoff_time"].min().reset_index()
        gw_df = gw_earliest.dropna(subset=["kickoff_time"]).copy()
        gw_df["deadline_time"] = (gw_df["kickoff_time"] - pd.Timedelta(hours=1)).dt.isoformat() if False else gw_df["kickoff_time"].apply(lambda x: (x - pd.Timedelta(hours=1)).isoformat())
        gw_df = gw_df[["gameweek", "deadline_time"]].sort_values("gameweek").reset_index(drop=True)
        # Also enrich pgw_copy with kickoff_time from fixtures for downstream use
        fix_map = fix_kt.set_index("fixture_id")["kickoff_time"]
        pgw_copy["kickoff_time"] = pgw_copy["fixture_id"].map(fix_map)
        pgw["kickoff_time"] = pgw_copy["kickoff_time"]
    else:
        gameweeks = []
        for gw, group in pgw_copy.groupby("gameweek"):
            if pd.isna(gw):
                continue
            earliest = group["kickoff_time"].min()
            if pd.isna(earliest):
                continue
            deadline = earliest - pd.Timedelta(hours=1)
            gameweeks.append({"gameweek": int(gw), "deadline_time": deadline.isoformat()})
        gw_df = pd.DataFrame(gameweeks).sort_values("gameweek").reset_index(drop=True)
    gw_df.to_csv(output_dir / "gameweeks.csv", index=False)
    print(f"gameweeks.csv: {len(gw_df)} gameweeks")

    # ------------------------------------------------------------------
    # 7. player_season_history.csv
    # ------------------------------------------------------------------
    agg_cols = {"gameweek": "count", "minutes": "sum", "total_points": "sum"}
    for c in ("goals_scored", "assists"):
        if c in pgw_copy.columns:
            agg_cols[c] = "sum"

    history = pgw_copy.groupby("player_id", as_index=False).agg(agg_cols)
    history.rename(columns={
        "gameweek": "appearances",
        "minutes": "total_minutes",
        "goals_scored": "goals",
    }, inplace=True)
    history.insert(1, "season", season)
    history.to_csv(output_dir / "player_season_history.csv", index=False)
    print(f"player_season_history.csv: {len(history)} players")

    # ------------------------------------------------------------------
    # 8. dataset_manifest.json
    # ------------------------------------------------------------------
    manifest = {
        "schema_version": "historical-feature-input-2.1",
        "generated_by": f"prepare_historical_for_features_v{VERSION}",
        "player_filter": {
            "valid_positions": sorted(valid_positions),
            "invalid_historical_player_gw_rows_excluded": int(len(excluded)),
            "invalid_player_ids_excluded": int(excluded["player_id"].nunique()),
        },
        "season": season,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "type": "normalized_historical_dataset",
            "directory": str(historical_dir),
        },
        "input_counts": {
            "players": int(len(players)),
            "fixtures": int(len(fixtures)),
            "gameweeks": int(len(gw_df)),
            "player_gameweek_rows": int(len(pgw)),
            "teams": int(len(teams_df)),
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
            "Teams derived from normalized player_gameweek team/team_code fields.",
            "Bootstrap snapshot used for team_code -> team_name resolution when needed.",
            "Gameweek deadlines are deterministic proxies (1h before earliest kickoff).",
        ],
    }
    with open(output_dir / "dataset_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print()
    print("PREPARATION COMPLETE")
    print(f"  Teams    : {len(teams_df)}")
    print(f"  Players  : {len(players)}")
    print(f"  Fixtures : {len(fixtures)}")
    print(f"  GWs      : {len(gw_df)}")
    print(f"  PGW rows : {len(pgw)}")
    print(f"  Output   : {output_dir}")


if __name__ == "__main__":
    main()
