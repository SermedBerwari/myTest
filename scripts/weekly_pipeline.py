"""
weekly_pipeline.py
==================
End-to-end Weekly Orchestration Pipeline (Phase 14).

Executes sequentially:
  1. Live FPL API fetch (bootstrap & fixtures)
  2. Feature vector construction
  3. Model prediction (Expected Points & Expected Minutes)
  4. External intelligence signals integration
  5. Squad & Transfer optimization (ILP + Manager Engine)
  6. AI Decision Agent report generation
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s][%(levelname)s] %(message)s")
LOG = logging.getLogger("weekly_pipeline")


import sys
# Append scripts directory to sys.path to enable imports
scripts_dir = Path(__file__).resolve().parent
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

def run_weekly_pipeline(season: str = "2026-27", target_gw: int = 1) -> dict:
    project_root = Path(__file__).resolve().parents[1]
    LOG.info("=" * 72)
    LOG.info(f"STARTING FPL AI WEEKLY AUTOMATION PIPELINE FOR {season} GW{target_gw}")
    LOG.info("=" * 72)

    # Step 1: Live intelligence fetch
    LOG.info("Step 1/5: Running External Intelligence Pipeline...")
    from intelligence.external_intelligence import fetch_availability_signals
    df_signals = fetch_availability_signals(project_root)
    LOG.info(f"Loaded {len(df_signals)} player availability signals.")

    # Step 2: Load feature dataset for target season & score players using CatBoost
    LOG.info(f"Step 2/5: Scoring player pool for {season} GW{target_gw} using CatBoost models...")
    
    feature_csv = project_root / "data" / "features" / season / "player_gameweek_features.csv"
    if not feature_csv.exists():
        # Fallback to training dataset if feature csv not generated yet
        feature_csv = project_root / "data" / "processed" / "training_dataset_v1.csv"
        df = pd.read_csv(feature_csv, low_memory=False)
        pool = df.loc[(df["season"] == season) & (df["target_gw"] == target_gw)].copy()
    else:
        import pandas as pd
        pool = pd.read_csv(feature_csv, low_memory=False)
        if "target_gw" in pool.columns:
            pool = pool[pool["target_gw"] == target_gw].copy()

    # Score players with trained CatBoost model
    from catboost import CatBoostRegressor
    catboost_path = project_root / "data" / "models" / "catboost_model.cbm"
    
    if catboost_path.exists() and not pool.empty:
        model = CatBoostRegressor()
        model.load_model(catboost_path)
        
        non_feature_cols = [
            "season", "player_id", "gameweek", "target_gw", "feature_cutoff_gw",
            "web_name", "first_name", "second_name", "position_name",
            "target_points", "target_minutes", "target_goals", "target_assists",
            "target_clean_sheets", "target_bonus", "target_xg", "target_xa"
        ]
        feat_cols = [c for c in pool.columns if c not in non_feature_cols and pd.api.types.is_numeric_dtype(pool[c])]
        X = pool[feat_cols].fillna(0)
        pool["expected_points"] = model.predict(X)
    else:
        pool["expected_points"] = pool.get("last_5_points_per_game", pd.Series([0]*len(pool))).fillna(0)

    # Attach Metadata
    players_meta_path = project_root / "data" / "processed" / season / "players.csv"
    if players_meta_path.exists():
        players_meta = pd.read_csv(players_meta_path)
        pool = pool.merge(players_meta[["player_id", "web_name", "position_id", "team_id", "now_cost"]], on="player_id", how="left", suffixes=("", "_meta"))
        if "web_name_meta" in pool.columns:
            pool["web_name"] = pool["web_name_meta"].fillna("Player_" + pool["player_id"].astype(str))
        if "position_id_meta" in pool.columns:
            pool["position_id"] = pool["position_id_meta"].fillna(3).astype(int)
        if "team_id_meta" in pool.columns:
            pool["team_id"] = pool["team_id_meta"].fillna(1).astype(int)
        if "now_cost_meta" in pool.columns:
            pool["cost"] = pool["now_cost_meta"].fillna(50) / 10.0
        elif "now_cost" in pool.columns:
            pool["cost"] = pool["now_cost"].fillna(50) / 10.0
    else:
        pool["team_id"] = 1
        pool["cost"] = 5.5

    pool = pool.drop_duplicates("player_id").reset_index(drop=True)

    # Step 3: Squad Optimization
    LOG.info("Step 3/5: Running ILP Squad Optimizer...")
    from optimizer.squad_optimizer import optimize_squad
    opt_squad = optimize_squad(pool, budget=100.0)
    LOG.info(f"Optimal Squad expected points: {opt_squad['expected_points']:.2f}")

    # Step 4: Manager Engine
    LOG.info("Step 4/5: Running Personalized Manager Engine...")
    from optimizer.manager_engine import recommend_transfers
    
    # Pick a valid 15-player sample squad with max 3 per team
    sample_rows = []
    for pos_id, qty in [(1, 2), (2, 5), (3, 5), (4, 3)]:
        pos_players = pool[pool["position_id"] == pos_id]
        chosen = 0
        for _, prow in pos_players.iterrows():
            curr_teams = [r["team_id"] for r in sample_rows]
            if curr_teams.count(prow["team_id"]) < 3:
                sample_rows.append(prow)
                chosen += 1
                if chosen == qty:
                    break
    sample_squad = [r["player_id"] for r in sample_rows]

    mgr_rec = recommend_transfers(sample_squad, pool, free_transfers=1)

    # Step 5: AI Decision Agent Report
    LOG.info("Step 5/5: Generating AI Decision Agent Report...")
    from agent.ai_decision_agent import generate_weekly_report
    report = generate_weekly_report(opt_squad, mgr_rec, df_signals.to_dict(orient="records"))

    summary = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "target_season": season,
        "target_gameweek": int(target_gw),
        "optimal_squad": opt_squad,
        "manager_recommendations": mgr_rec,
        "ai_report": report
    }

    out_file = project_root / "data" / "processed" / "weekly_automation_summary.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    LOG.info("=" * 72)
    LOG.info(f"WEEKLY AUTOMATION PIPELINE EXECUTED SUCCESSFULLY. Output: {out_file}")
    LOG.info("=" * 72)
    return summary


if __name__ == "__main__":
    run_weekly_pipeline()
