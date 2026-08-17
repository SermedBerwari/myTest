"""
build_2026_27_gw1_features.py
==============================
Constructs GW1 feature vectors for the new 2026-27 season using prior season
(2025-26) historical performance and current FPL 2026-27 player prices,
teams, and fixture difficulties.

FIX (data integrity): FPL's numeric `player_id` (aka "element") is NOT
stable across seasons -- the same id can be reassigned to a different
player the following season (verified: player_id=4 was Arsenal's third-
choice keeper "Tommy Setford" in 2025-26, but is the defender "Gabriel" in
2026-27). The previous version of this script joined prior-season history
onto the current season by raw player_id, which silently attached the
wrong player's rolling stats to most of the pool, and separately left
`team_id`/`position_id` defaulted to placeholder values instead of using
the current season's own (correct) metadata.

This version:
  1. Always sets team_id, position_id, and cost directly from the CURRENT
     season's players.csv -- never inherited from last season.
  2. Joins prior-season history via FPL's stable `code` field (unique to
     a player across seasons), not the season-local `player_id`.
  3. Computes opponent_team_id / was_home / fixture_difficulty from the
     current season's own fixtures.csv.

Output:
  data/features/2026-27/player_gameweek_features.csv
"""

from __future__ import annotations

import json
from pathlib import Path
import pandas as pd

# Columns that must ALWAYS come from the current season's own metadata /
# fixture data and must never be overwritten by inherited prior-season rows.
CURRENT_SEASON_ONLY_COLUMNS = {
    "player_id",
    "season",
    "target_gw",
    "gameweek",
    "feature_cutoff_gw",
    "web_name",
    "position_id",
    "position_name",
    "team_id",
    "opponent_team_id",
    "was_home",
    "fixture_difficulty",
    "value",
    "target_points",
    "target_minutes",
    "target_goals",
    "target_assists",
    "target_clean_sheets",
    "target_bonus",
    "target_xg",
    "target_xa",
}


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]

    print("=" * 72)
    print("BUILDING 2026-27 GW1 FEATURE DATASET")
    print("=" * 72)

    # 1. Load 2026-27 players, teams, and fixtures (all CURRENT season truth)
    players_26 = pd.read_csv(project_root / "data" / "processed" / "2026-27" / "players.csv")
    fixtures_26 = pd.read_csv(project_root / "data" / "processed" / "2026-27" / "fixtures.csv")

    # 2. Load 2025-26 historical features to inherit rolling performance stats
    features_25 = pd.read_csv(project_root / "data" / "features" / "2025-26" / "player_gameweek_features.csv")
    pgw_25 = pd.read_csv(
        project_root / "data" / "processed" / "2025-26" / "player_gameweek.csv",
        low_memory=False,
    )

    # Build a STABLE cross-season identity map: 2025-26 player_id -> code.
    id_to_code_25 = (
        pgw_25.dropna(subset=["player_code"])
        .drop_duplicates("player_id")
        .set_index("player_id")["player_code"]
        .astype("Int64")
    )

    features_25 = features_25.copy()
    features_25["code"] = features_25["player_id"].map(id_to_code_25)

    # Last known feature row per player, keyed by the STABLE code -- not by
    # the season-local player_id, which can be reassigned between seasons.
    last_known_25 = (
        features_25.dropna(subset=["code"])
        .sort_values(["code", "target_gw"])
        .groupby("code")
        .last()
        .reset_index()
    )
    last_known_25["code"] = last_known_25["code"].astype("Int64")

    unmatched_prior = features_25["code"].isna().sum()
    if unmatched_prior:
        print(
            f"NOTE: {unmatched_prior} historical 2025-26 feature rows had no "
            f"resolvable player_code and were excluded from inheritance."
        )

    # 3. Filter GW1 fixtures
    gw1_fixtures = fixtures_26[fixtures_26["gameweek"] == 1].copy()

    # Prepare feature columns template from training dataset
    train_df = pd.read_csv(project_root / "data" / "processed" / "training_dataset_v1.csv", nrows=1)
    feature_template = {c: 0.0 for c in train_df.columns}

    records = []
    no_fixture = 0
    no_history_match = 0

    for _, p in players_26.iterrows():
        pid = p["player_id"]
        code = p.get("code")
        tid = p.get("team_id")
        pos_id = p.get("position_id")

        # Find GW1 fixture for player's team (current season truth)
        fix = gw1_fixtures[(gw1_fixtures["team_h"] == tid) | (gw1_fixtures["team_a"] == tid)]
        if fix.empty:
            no_fixture += 1
            continue

        fix_row = fix.iloc[0]
        was_home = 1 if fix_row["team_h"] == tid else 0
        opp_id = fix_row["team_a"] if was_home == 1 else fix_row["team_h"]
        fixture_difficulty = (
            fix_row["team_h_difficulty"] if was_home == 1 else fix_row["team_a_difficulty"]
        )

        # Base record: identity / fixture context ALWAYS from current season.
        row_feat = feature_template.copy()
        row_feat["season"] = "2026-27"
        row_feat["player_id"] = pid
        row_feat["target_gw"] = 1
        row_feat["gameweek"] = 1
        row_feat["feature_cutoff_gw"] = 0
        row_feat["web_name"] = p.get("web_name", "")
        row_feat["position_id"] = pos_id
        row_feat["team_id"] = tid
        row_feat["opponent_team_id"] = opp_id
        row_feat["was_home"] = was_home
        row_feat["fixture_difficulty"] = fixture_difficulty
        row_feat["value"] = p.get("now_cost", 50)
        row_feat["target_points"] = 0  # To be predicted

        # Inherit historical ROLLING PERFORMANCE metrics from last season,
        # matched by stable player code. Identity/team/position/fixture
        # fields are explicitly protected and never overwritten here.
        if pd.notna(code):
            p_hist = last_known_25[last_known_25["code"] == int(code)]
        else:
            p_hist = last_known_25.iloc[0:0]

        if not p_hist.empty:
            p_hist_row = p_hist.iloc[0]
            for col in train_df.columns:
                if col in CURRENT_SEASON_ONLY_COLUMNS:
                    continue
                if col in p_hist_row and pd.notna(p_hist_row[col]):
                    row_feat[col] = p_hist_row[col]
        else:
            no_history_match += 1

        records.append(row_feat)

    df_26_gw1 = pd.DataFrame(records)
    print(f"Constructed GW1 feature vectors for {len(df_26_gw1)} players.")
    print(f"  Players with no GW1 fixture found : {no_fixture}")
    print(f"  Players with no matched prior history (new signings / promoted players): {no_history_match}")

    if (df_26_gw1["team_id"] == 0).any() or df_26_gw1["team_id"].isna().any():
        bad = df_26_gw1[(df_26_gw1["team_id"] == 0) | (df_26_gw1["team_id"].isna())]
        raise ValueError(
            f"{len(bad)} rows have an invalid team_id after build. "
            f"player_ids: {bad['player_id'].tolist()[:20]}"
        )

    output_dir = project_root / "data" / "features" / "2026-27"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_csv = output_dir / "player_gameweek_features.csv"
    df_26_gw1.to_csv(output_csv, index=False)

    print(f"Saved 2026-27 GW1 features to: {output_csv}")
    print("=" * 72)


if __name__ == "__main__":
    main()
