"""
build_2026_27_gw1_features.py
==============================
Constructs GW1 feature vectors for the new 2026-27 season using prior season (2025-26)
historical performance and current FPL 2026-27 player prices, teams, and fixture difficulties.

Output:
  data/features/2026-27/player_gameweek_features.csv
"""

from __future__ import annotations

import json
from pathlib import Path
import pandas as pd

def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    
    print("=" * 72)
    print("BUILDING 2026-27 GW1 FEATURE DATASET")
    print("=" * 72)

    # 1. Load 2026-27 players, teams, and fixtures
    players_26 = pd.read_csv(project_root / "data" / "processed" / "2026-27" / "players.csv")
    fixtures_26 = pd.read_csv(project_root / "data" / "processed" / "2026-27" / "fixtures.csv")
    teams_26 = pd.read_csv(project_root / "data" / "processed" / "2026-27" / "teams.csv")

    # 2. Load 2025-26 historical features to map prior performance stats
    features_25 = pd.read_csv(project_root / "data" / "features" / "2025-26" / "player_gameweek_features.csv")
    
    # Get last known feature row per player in 2025-26
    last_known_25 = features_25.sort_values(["player_id", "target_gw"]).groupby("player_id").last().reset_index()

    # 3. Filter GW1 fixtures
    gw1_fixtures = fixtures_26[fixtures_26["gameweek"] == 1].copy()

    # Map team fixtures: player's team -> fixture & opponent
    records = []
    
    # Prepare feature columns template from training dataset
    train_df = pd.read_csv(project_root / "data" / "processed" / "training_dataset_v1.csv", nrows=1)
    feature_template = {c: 0.0 for c in train_df.columns}

    for _, p in players_26.iterrows():
        pid = p["player_id"]
        tid = p.get("team_id", p.get("team"))
        
        # Find GW1 fixture for player's team
        fix = gw1_fixtures[(gw1_fixtures["team_h"] == tid) | (gw1_fixtures["team_a"] == tid)]
        if fix.empty:
            continue
        
        fix_row = fix.iloc[0]
        was_home = 1 if fix_row["team_h"] == tid else 0
        opp_id = fix_row["team_a"] if was_home == 1 else fix_row["team_h"]

        # Base record
        row_feat = feature_template.copy()
        row_feat["season"] = "2026-27"
        row_feat["player_id"] = pid
        row_feat["target_gw"] = 1
        row_feat["gameweek"] = 1
        row_feat["feature_cutoff_gw"] = 0
        row_feat["web_name"] = p.get("web_name", p.get("first_name", ""))
        row_feat["position_id"] = p.get("element_type", 3)
        row_feat["opponent_team_id"] = opp_id
        row_feat["was_home"] = was_home
        row_feat["value"] = p.get("now_cost", 50)
        row_feat["target_points"] = 0  # To be predicted

        # Inherit historical rolling metrics from last season if player existed
        p_hist = last_known_25[last_known_25["player_id"] == pid]
        if not p_hist.empty:
            p_hist_row = p_hist.iloc[0]
            for col in train_df.columns:
                if col in p_hist_row and pd.notna(p_hist_row[col]) and col not in ["season", "target_gw", "gameweek", "target_points"]:
                    row_feat[col] = p_hist_row[col]

        records.append(row_feat)

    df_26_gw1 = pd.DataFrame(records)
    print(f"Constructed GW1 feature vectors for {len(df_26_gw1)} players.")

    output_dir = project_root / "data" / "features" / "2026-27"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_csv = output_dir / "player_gameweek_features.csv"
    df_26_gw1.to_csv(output_csv, index=False)

    print(f"Saved 2026-27 GW1 features to: {output_csv}")
    print("=" * 72)

if __name__ == "__main__":
    main()
