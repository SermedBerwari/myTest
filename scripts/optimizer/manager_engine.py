"""
manager_engine.py
=================
Personalized Manager Engine for Fantasy Premier League (Phase 11).

Evaluates current squad state against optimal recommendations and calculates:
  - Free transfers vs hit penalties (-4 pts)
  - Recommended transfers OUT and IN with net expected points gain (ΔxP)
  - Captain & Vice-Captain choices
"""

from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
try:
    from optimizer.squad_optimizer import optimize_squad
except ImportError:
    from squad_optimizer import optimize_squad


def recommend_transfers(
    current_squad_ids: list[int],
    player_pool: pd.DataFrame,
    free_transfers: int = 1,
    bank: float = 0.0,
    hit_penalty: float = 4.0
) -> dict:
    """
    Recommends optimal transfers considering free transfer allowance and hit penalties.
    """
    # 1. Compute baseline expected points for current squad
    current_squad = player_pool[player_pool["player_id"].isin(current_squad_ids)].copy()
    if len(current_squad) < 15:
        # Fallback if incomplete squad passed
        current_opt = optimize_squad(player_pool, budget=100.0)
        current_xp = current_opt["expected_points"]
    else:
        current_opt = optimize_squad(current_squad, budget=100.0)
        current_xp = current_opt["expected_points"]

    # 2. Compute globally optimal squad
    optimal_squad = optimize_squad(player_pool, budget=100.0 + bank)
    optimal_xp = optimal_squad["expected_points"]

    optimal_ids = {p["player_id"] for p in optimal_squad["starting_xi"] + optimal_squad["bench"]}
    current_set = set(current_squad_ids)

    transfers_out_ids = list(current_set - optimal_ids)
    transfers_in_ids = list(optimal_ids - current_set)

    num_transfers = min(len(transfers_out_ids), len(transfers_in_ids))
    extra_transfers = max(0, num_transfers - free_transfers)
    total_penalty = extra_transfers * hit_penalty

    gross_gain = optimal_xp - current_xp
    net_gain = gross_gain - total_penalty

    return {
        "current_expected_points": current_xp,
        "optimal_expected_points": optimal_xp,
        "gross_expected_gain": gross_gain,
        "transfers_count": num_transfers,
        "free_transfers_used": min(num_transfers, free_transfers),
        "hit_penalty_incurred": total_penalty,
        "net_expected_gain": net_gain,
        "recommended_captain": optimal_squad["captain"],
        "transfers_out_ids": transfers_out_ids[:num_transfers],
        "transfers_in_ids": transfers_in_ids[:num_transfers],
        "optimal_starting_xi": optimal_squad["starting_xi"]
    }


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    dataset_path = project_root / "data" / "processed" / "training_dataset_v1.csv"
    players_meta = pd.read_csv(project_root / "data" / "processed" / "2025-26" / "players.csv")

    print("=" * 72)
    print("PERSONALIZED MANAGER ENGINE TEST (PHASE 11)")
    print("=" * 72)

    df = pd.read_csv(dataset_path, low_memory=False)
    sample_gw = df.loc[df["season"] == "2025-26", "target_gw"].max()
    pool = df.loc[(df["season"] == "2025-26") & (df["target_gw"] == sample_gw)].copy()

    pool = pool.merge(players_meta[["player_id", "web_name", "position_id"]], on="player_id", how="left", suffixes=("", "_meta"))
    if "web_name_meta" in pool.columns:
        pool["web_name"] = pool["web_name_meta"].fillna("Player_" + pool["player_id"].astype(str))
    if "position_id_meta" in pool.columns:
        pool["position_id"] = pool["position_id_meta"].fillna(3).astype(int)

    pool["team_id"] = (pool["player_id"] % 20) + 1
    pool["cost"] = 5.5
    pool["expected_points"] = pool["last_5_points_per_game"].fillna(0)
    pool = pool.drop_duplicates("player_id").reset_index(drop=True)

    # Sample valid 15-player squad (2 GK, 5 DEF, 5 MID, 3 FWD)
    gks = pool[pool["position_id"] == 1]["player_id"].head(2).tolist()
    defs = pool[pool["position_id"] == 2]["player_id"].head(5).tolist()
    mids = pool[pool["position_id"] == 3]["player_id"].head(5).tolist()
    fwds = pool[pool["position_id"] == 4]["player_id"].head(3).tolist()
    sample_squad = gks + defs + mids + fwds

    res = recommend_transfers(sample_squad, pool, free_transfers=1, bank=0.5)

    print(f"Current Squad Expected Pts : {res['current_expected_points']:.2f}")
    print(f"Optimal Squad Expected Pts : {res['optimal_expected_points']:.2f}")
    print(f"Transfers Required         : {res['transfers_count']} (Free: {res['free_transfers_used']}, Penalty: -{res['hit_penalty_incurred']:.0f} pts)")
    print(f"Net Expected Gain (Delta xP) : +{res['net_expected_gain']:.2f} pts")
    print(f"Recommended Captain        : {res['recommended_captain']}")

    report_path = project_root / "data" / "processed" / "manager_engine_sample.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)

    print(f"\nSaved manager engine report to: {report_path}")
    print("=" * 72)


if __name__ == "__main__":
    main()
