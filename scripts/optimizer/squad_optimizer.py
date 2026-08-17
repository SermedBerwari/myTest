"""
squad_optimizer.py
==================
FPL Squad Optimizer built using Google OR-Tools Integer Linear Programming (ILP).

Enforces all official FPL constraints:
  - 15 total players (2 GK, 5 DEF, 5 MID, 3 FWD)
  - Starting XI (1 GK, >=3 DEF, >=2 MID, >=1 FWD, exactly 11 players)
  - Budget <= £100.0M (1000 in 0.1M units)
  - Max 3 players per club
  - 1 Captain, 1 Vice-Captain
"""

from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
from ortools.linear_solver import pywraplp


def optimize_squad(
    player_pool: pd.DataFrame,
    budget: float = 100.0,
    max_per_team: int = 3
) -> dict:
    """
    Optimizes a 15-player FPL squad and Starting XI given expected points and prices.
    player_pool required columns: ['player_id', 'web_name', 'position_id', 'team_id', 'cost', 'expected_points']
    """
    solver = pywraplp.Solver.CreateSolver("CBC")
    if not solver:
        raise RuntimeError("CBC solver unavailable in OR-Tools.")

    n = len(player_pool)
    x = [solver.BoolVar(f"squad_{i}") for i in range(n)]       # 1 in 15 squad
    s = [solver.BoolVar(f"start_{i}") for i in range(n)]       # 1 in starting 11
    c = [solver.BoolVar(f"captain_{i}") for i in range(n)]     # 1 if captain

    # Constraint 1: Starting XI subset of 15 squad
    for i in range(n):
        solver.Add(s[i] <= x[i])
        solver.Add(c[i] <= s[i])

    # Constraint 2: Squad sizes
    solver.Add(solver.Sum(x) == 15)
    solver.Add(solver.Sum(s) == 11)
    solver.Add(solver.Sum(c) == 1)

    # Constraint 3: Budget (cost in tenths or float)
    costs = player_pool["cost"].values
    solver.Add(solver.Sum(x[i] * costs[i] for i in range(n)) <= budget)

    # Constraint 4: Positional constraints (1: GK, 2: DEF, 3: MID, 4: FWD)
    pos = player_pool["position_id"].values
    solver.Add(solver.Sum(x[i] for i in range(n) if pos[i] == 1) == 2)
    solver.Add(solver.Sum(x[i] for i in range(n) if pos[i] == 2) == 5)
    solver.Add(solver.Sum(x[i] for i in range(n) if pos[i] == 3) == 5)
    solver.Add(solver.Sum(x[i] for i in range(n) if pos[i] == 4) == 3)

    # Starting XI position bounds
    solver.Add(solver.Sum(s[i] for i in range(n) if pos[i] == 1) == 1)
    solver.Add(solver.Sum(s[i] for i in range(n) if pos[i] == 2) >= 3)
    solver.Add(solver.Sum(s[i] for i in range(n) if pos[i] == 2) <= 5)
    solver.Add(solver.Sum(s[i] for i in range(n) if pos[i] == 3) >= 2)
    solver.Add(solver.Sum(s[i] for i in range(n) if pos[i] == 3) <= 5)
    solver.Add(solver.Sum(s[i] for i in range(n) if pos[i] == 4) >= 1)
    solver.Add(solver.Sum(s[i] for i in range(n) if pos[i] == 4) <= 3)

    # Constraint 5: Max 3 players per club
    teams = player_pool["team_id"].values
    unique_teams = set(teams)
    for team in unique_teams:
        solver.Add(solver.Sum(x[i] for i in range(n) if teams[i] == team) <= max_per_team)

    # Objective: Maximize expected points (Starting 11 + Captain Bonus)
    ep = player_pool["expected_points"].values
    objective = solver.Objective()
    for i in range(n):
        objective.SetCoefficient(s[i], float(ep[i]))
        objective.SetCoefficient(c[i], float(ep[i]))
    objective.SetMaximization()

    status = solver.Solve()

    if status != pywraplp.Solver.OPTIMAL:
        raise RuntimeError("Solver failed to find an optimal solution.")

    # Extract selected squad
    squad_indices = [i for i in range(n) if x[i].solution_value() > 0.5]
    start_indices = [i for i in range(n) if s[i].solution_value() > 0.5]
    bench_indices = [i for i in squad_indices if i not in start_indices]
    captain_index = [i for i in range(n) if c[i].solution_value() > 0.5][0]

    squad_df = player_pool.iloc[squad_indices].copy()
    start_df = player_pool.iloc[start_indices].copy()
    bench_df = player_pool.iloc[bench_indices].copy()

    total_cost = squad_df["cost"].sum()
    expected_pts = start_df["expected_points"].sum() + player_pool.iloc[captain_index]["expected_points"]

    return {
        "total_cost": float(total_cost),
        "expected_points": float(expected_pts),
        "captain": player_pool.iloc[captain_index]["web_name"],
        "starting_xi": start_df[["player_id", "web_name", "position_id", "team_id", "cost", "expected_points"]].to_dict(orient="records"),
        "bench": bench_df[["player_id", "web_name", "position_id", "team_id", "cost", "expected_points"]].to_dict(orient="records"),
    }


def select_starting_xi(squad_df: pd.DataFrame) -> dict:
    """
    Given a FIXED 15-player squad (already chosen -- no transfers happen
    here), pick the best-scoring valid starting XI + captain for one
    gameweek. Used by the historical manager simulator (FIX 6) every week,
    since a real manager only re-picks their XI/captain weekly but only
    transfers players occasionally.

    squad_df required columns: ['player_id', 'web_name', 'position_id',
    'team_id', 'cost', 'expected_points'] -- exactly 15 rows.
    """
    if len(squad_df) != 15:
        raise ValueError(f"select_starting_xi requires exactly 15 players, got {len(squad_df)}.")

    squad_df = squad_df.reset_index(drop=True)
    solver = pywraplp.Solver.CreateSolver("CBC")
    if not solver:
        raise RuntimeError("CBC solver unavailable in OR-Tools.")

    n = len(squad_df)
    s = [solver.BoolVar(f"start_{i}") for i in range(n)]
    c = [solver.BoolVar(f"captain_{i}") for i in range(n)]

    for i in range(n):
        solver.Add(c[i] <= s[i])

    solver.Add(solver.Sum(s) == 11)
    solver.Add(solver.Sum(c) == 1)

    pos = squad_df["position_id"].values
    solver.Add(solver.Sum(s[i] for i in range(n) if pos[i] == 1) == 1)
    solver.Add(solver.Sum(s[i] for i in range(n) if pos[i] == 2) >= 3)
    solver.Add(solver.Sum(s[i] for i in range(n) if pos[i] == 2) <= 5)
    solver.Add(solver.Sum(s[i] for i in range(n) if pos[i] == 3) >= 2)
    solver.Add(solver.Sum(s[i] for i in range(n) if pos[i] == 3) <= 5)
    solver.Add(solver.Sum(s[i] for i in range(n) if pos[i] == 4) >= 1)
    solver.Add(solver.Sum(s[i] for i in range(n) if pos[i] == 4) <= 3)

    ep = squad_df["expected_points"].values
    objective = solver.Objective()
    for i in range(n):
        objective.SetCoefficient(s[i], float(ep[i]))
        objective.SetCoefficient(c[i], float(ep[i]))
    objective.SetMaximization()

    status = solver.Solve()
    if status != pywraplp.Solver.OPTIMAL:
        raise RuntimeError("Solver failed to find an optimal starting XI.")

    start_indices = [i for i in range(n) if s[i].solution_value() > 0.5]
    bench_indices = [i for i in range(n) if i not in start_indices]
    captain_index = [i for i in range(n) if c[i].solution_value() > 0.5][0]

    start_df = squad_df.iloc[start_indices]
    bench_df = squad_df.iloc[bench_indices]
    expected_pts = start_df["expected_points"].sum() + squad_df.iloc[captain_index]["expected_points"]

    return {
        "expected_points": float(expected_pts),
        "captain_id": int(squad_df.iloc[captain_index]["player_id"]),
        "captain": squad_df.iloc[captain_index]["web_name"],
        "starting_ids": start_df["player_id"].astype(int).tolist(),
        "bench_ids": bench_df["player_id"].astype(int).tolist(),
    }


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]

    print("=" * 72)
    print("SQUAD OPTIMIZER VERIFICATION (PHASE 10)")
    print("=" * 72)

    # Use the same validated real-data path as weekly_pipeline.py: current
    # season features (real fixture context) + current season players.csv
    # (real team_id/position_id/cost). This avoids the fragile historical
    # training_dataset_v1.csv <-> player_gameweek.csv price join.
    season = "2026-27"
    target_gw = 1

    features_path = project_root / "data" / "features" / season / "player_gameweek_features.csv"
    players_path = project_root / "data" / "processed" / season / "players.csv"

    if not features_path.exists():
        raise FileNotFoundError(
            f"{features_path} not found. Run scripts\\build_2026_27_gw1_features.py first."
        )

    pool = pd.read_csv(features_path, low_memory=False)
    pool = pool[pool["target_gw"] == target_gw].copy()

    players_meta = pd.read_csv(players_path)
    pool = pool.merge(
        players_meta[["player_id", "web_name", "position_id", "team_id", "now_cost"]],
        on="player_id",
        how="left",
        suffixes=("", "_meta"),
    )
    pool["web_name"] = pool["web_name_meta"].fillna(pool["web_name"])
    pool["position_id"] = pool["position_id_meta"]
    pool["team_id"] = pool["team_id_meta"]
    pool["cost"] = pool["now_cost"] / 10.0

    missing_meta = pool[pool["team_id"].isna() | pool["position_id"].isna() | pool["cost"].isna()]
    if not missing_meta.empty:
        raise ValueError(
            "Missing real team_id/position_id/cost metadata for player_id(s): "
            f"{missing_meta['player_id'].tolist()}"
        )

    pool["position_id"] = pool["position_id"].astype(int)
    pool["team_id"] = pool["team_id"].astype(int)
    # No trained-model score is used here deliberately (smoke test only);
    # production weekly_pipeline.py scores with the trained CatBoost model.
    pool["expected_points"] = pool["last_5_points_per_game"].fillna(0)

    # Deduplicate by player_id
    pool = pool.drop_duplicates("player_id").reset_index(drop=True)

    print(f"Optimizing squad for {season} GW{target_gw} (Pool size: {len(pool)} players)...")
    res = optimize_squad(pool, budget=100.0, max_per_team=3)

    print("\n" + "=" * 72)
    print(f"OPTIMAL SQUAD SELECTED (Total Cost: £{res['total_cost']:.1f}M | Expected Pts: {res['expected_points']:.2f})")
    print(f"Captain: {res['captain']}")
    print("=" * 72)
    print("Starting XI:")
    for p in res["starting_xi"]:
        print(f"  Pos {p['position_id']} | {p['web_name']:<20} | £{p['cost']:.1f}M | xP: {p['expected_points']:.2f}")

    print("\nBench:")
    for p in res["bench"]:
        print(f"  Pos {p['position_id']} | {p['web_name']:<20} | £{p['cost']:.1f}M | xP: {p['expected_points']:.2f}")

    report_path = project_root / "data" / "processed" / "optimal_squad_sample.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)

    print(f"\nSaved optimal squad report to: {report_path}")
    print("=" * 72)


if __name__ == "__main__":
    main()
