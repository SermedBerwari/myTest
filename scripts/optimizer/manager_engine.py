"""
manager_engine.py
=================
Personalized Manager Engine for Fantasy Premier League.

This version removes the unsafe prototype fallback that silently replaced
an incomplete current squad with the globally optimal squad.

The production function now requires a real 15-player squad represented by
player IDs that exist in the supplied player pool.
"""

from __future__ import annotations
import argparse
import argparse

import argparse
import json
from pathlib import Path

import argparse
import pandas as pd

try:
    from .squad_optimizer import optimize_squad, select_starting_xi
except ImportError:
    from squad_optimizer import optimize_squad, select_starting_xi


REQUIRED_POOL_COLUMNS = {
    "player_id",
    "team_id",
    "position_id",
    "cost",
    "expected_points",
}


def _is_unavailable(value: object) -> bool:
    s = str(value or "available").strip().lower()
    return s in {"unavailable", "unknown", "injured", "suspended", "out", "doubtful"}

def _validate_player_pool(player_pool: pd.DataFrame) -> None:
    """Validate the minimum schema required by the manager engine."""
    missing = REQUIRED_POOL_COLUMNS - set(player_pool.columns)
    if missing:
        raise ValueError(
            "Player pool is missing required columns: "
            + ", ".join(sorted(missing))
        )

    if player_pool["player_id"].duplicated().any():
        dupes = (
            player_pool.loc[
                player_pool["player_id"].duplicated(), "player_id"
            ]
            .astype(int)
            .tolist()
        )
        raise ValueError(f"Player pool contains duplicate player_id values: {dupes}")

    if player_pool.empty:
        raise ValueError("Player pool is empty.")

    if player_pool["expected_points"].isna().any():
        raise ValueError("Player pool contains NaN expected_points values.")

    if player_pool["cost"].isna().any():
        raise ValueError("Player pool contains NaN cost values.")


def _validate_current_squad(
    current_squad_ids: list[int],
    player_pool: pd.DataFrame,
) -> None:
    """Require a complete, valid FPL 15-player squad."""
    if not isinstance(current_squad_ids, list):
        raise TypeError("current_squad_ids must be a list of player IDs.")

    if len(current_squad_ids) != 15:
        raise ValueError(
            f"Current squad must contain exactly 15 players; "
            f"received {len(current_squad_ids)}."
        )

    if len(set(current_squad_ids)) != 15:
        raise ValueError("Current squad contains duplicate player IDs.")

    pool_ids = set(player_pool["player_id"].astype(int))
    missing = sorted(set(current_squad_ids) - pool_ids)

    if missing:
        raise ValueError(
            "Current squad contains player IDs missing from player_pool: "
            + ", ".join(map(str, missing))
        )

    squad = player_pool[player_pool["player_id"].isin(current_squad_ids)]

    if len(squad) != 15:
        raise ValueError(
            "Current squad could not be resolved to exactly 15 unique players."
        )

    position_counts = squad["position_id"].value_counts().to_dict()
    expected_positions = {1: 2, 2: 5, 3: 5, 4: 3}

    if position_counts != expected_positions:
        raise ValueError(
            "Current squad must contain exactly 2 GK, 5 DEF, 5 MID and 3 FWD. "
            f"Received: {position_counts}"
        )

    team_counts = squad["team_id"].value_counts()
    if (team_counts > 3).any():
        invalid = team_counts[team_counts > 3].to_dict()
        raise ValueError(
            f"Current squad violates the 3-player-per-team limit: {invalid}"
        )


def _find_best_replacement(
    departing_row: pd.Series,
    player_pool: pd.DataFrame,
    exclude_ids: set[int],
    team_counts_without_departing: dict[int, int],
    budget_available: float,
) -> pd.Series | None:
    """Best same-position, affordable, team-limit-respecting replacement for one departing player."""
    pos = int(departing_row["position_id"])
    candidates = player_pool[
        (player_pool["position_id"] == pos)
        & (~player_pool["player_id"].isin(exclude_ids))
        & (player_pool["cost"] <= budget_available)
    ].copy()
    if candidates.empty:
        return None

    candidates = candidates[
        candidates["team_id"].map(lambda t: team_counts_without_departing.get(int(t), 0) < 3)
    ]
    if candidates.empty:
        return None

    candidates["gain"] = candidates["expected_points"] - float(departing_row["expected_points"])
    best = candidates.sort_values("gain", ascending=False).iloc[0]
    return best


def _search_best_transfers(
    current_squad: pd.DataFrame,
    player_pool: pd.DataFrame,
    bank: float,
    max_transfers: int = 2,
    free_transfers: int = 1,
    hit_penalty: float = 4.0,
) -> dict:
    """
    FIX 8: targeted best-swap search, replacing the old "diff against a
    fully reoptimized global squad" approach. That approach counted every
    difference between the current squad and an unconstrained global
    optimum as a "transfer", which -- whenever the model's weekly picks
    were even slightly unstable -- produced large phantom transfer counts,
    an always-dominant hit penalty, and a manager that never transfers at
    all (validated against the historical simulator: this was the exact
    cause of ai_manager == no_transfer in early seasons).

    This instead finds, for each currently-owned player, the single best
    same-position replacement, then evaluates taking the top 0, 1, or 2 of
    those swaps (by individual gain, checking they don't share a target
    player and jointly respect budget/team-limit), and returns whichever
    transfer COUNT has the best GROSS gain (net gain, including hits, is
    computed by the caller against free_transfers/hit_penalty).
    """
    current_squad = current_squad.reset_index(drop=True)
    team_counts = current_squad["team_id"].value_counts().to_dict()

    single_options = []
    for _, row in current_squad.iterrows():
        pid = int(row["player_id"])
        team_counts_without = dict(team_counts)
        team_counts_without[int(row["team_id"])] = team_counts_without.get(int(row["team_id"]), 0) - 1

        budget_available = bank + float(row["cost"])
        best = _find_best_replacement(
            row, player_pool, exclude_ids=set(current_squad["player_id"]),
            team_counts_without_departing=team_counts_without,
            budget_available=budget_available,
        )
        if best is not None and best["gain"] > 0:
            single_options.append({
                "out_id": pid,
                "out_cost": float(row["cost"]),
                "in_id": int(best["player_id"]),
                "in_cost": float(best["cost"]),
                "gain": float(best["gain"]),
                "position_id": int(row["position_id"]),
                "out_team_id": int(row["team_id"]),
                "in_team_id": int(best["team_id"]),
            })

    single_options.sort(key=lambda o: o["gain"], reverse=True)

    best_combo = {"transfers": [], "gross_gain": 0.0, "net_gain": 0.0}

    for k in range(1, max_transfers + 1):
        used_in_ids: set[int] = set()
        used_out_ids: set[int] = set()
        combo = []
        remaining_bank = bank
        team_counts_running = dict(team_counts)

        for opt in single_options:
            if len(combo) >= k:
                break
            if opt["out_id"] in used_out_ids or opt["in_id"] in used_in_ids:
                continue
            cost_delta = opt["in_cost"] - opt["out_cost"]
            if cost_delta > remaining_bank:
                continue
            projected = dict(team_counts_running)
            projected[opt["out_team_id"]] = projected.get(opt["out_team_id"], 0) - 1
            projected[opt["in_team_id"]] = projected.get(opt["in_team_id"], 0) + 1
            if projected[opt["in_team_id"]] > 3:
                continue

            combo.append(opt)
            used_in_ids.add(opt["in_id"])
            used_out_ids.add(opt["out_id"])
            remaining_bank -= cost_delta
            team_counts_running = projected

        gross_gain = sum(o["gain"] for o in combo)
        net_gain = gross_gain - max(0, k - int(free_transfers)) * float(hit_penalty)
        if len(combo) == k and net_gain > best_combo["net_gain"]:
            best_combo = {"transfers": combo, "gross_gain": gross_gain, "net_gain": net_gain}

    return best_combo


def recommend_transfers(
    current_squad_ids: list[int],
    player_pool: pd.DataFrame,
    free_transfers: int = 1,
    bank: float = 0.0,
    hit_penalty: float = 4.0,
    manager_mode: str = "standard",
) -> dict:
    """
    Recommend transfers via a TARGETED best-swap search (FIX 8) -- not a
    diff against a fully reoptimized global squad (see
    _search_best_transfers docstring for why that approach failed).

    Important:
      - No synthetic replacement is performed for incomplete squads.
      - Current squad expected points are calculated from the actual 15 players.
      - Evaluates taking 0, 1, or 2 transfers and picks whichever yields the
        best NET gain (gross gain minus hit penalty for transfers beyond
        free_transfers).
    """
    _validate_player_pool(player_pool)
    _validate_current_squad(current_squad_ids, player_pool)

    if free_transfers < 0:
        raise ValueError("free_transfers cannot be negative.")
    if bank < 0:
        raise ValueError("bank cannot be negative.")
    if hit_penalty < 0:
        raise ValueError("hit_penalty cannot be negative.")

    supported_modes = {"standard", "free_transfer_only", "hit_allowed"}
    if manager_mode not in supported_modes:
        raise ValueError(f"Unsupported manager_mode {manager_mode!r}; supported: {sorted(supported_modes)}")
    availability_col = "availability" if "availability" in player_pool.columns else ("status" if "status" in player_pool.columns else None)
    if availability_col:
        unavailable = player_pool[availability_col].map(_is_unavailable) 
        unavailable_current = player_pool.loc[player_pool["player_id"].isin(current_squad_ids) & unavailable, "player_id"].astype(int).tolist()
        if unavailable_current:
            raise ValueError(f"Current squad contains unavailable players: {unavailable_current}")
        player_pool = player_pool.loc[~unavailable].copy()

    current_squad = (
        player_pool[player_pool["player_id"].isin(current_squad_ids)]
        .copy()
        .reset_index(drop=True)
    )
    current_xp = float(current_squad["expected_points"].sum())

    max_search_transfers = free_transfers if manager_mode == "free_transfer_only" else 2
    best = _search_best_transfers(current_squad, player_pool, bank, max_transfers=max_search_transfers, free_transfers=free_transfers, hit_penalty=hit_penalty)
    transfers = best["transfers"]
    num_transfers = len(transfers)

    free_transfers_used = min(num_transfers, int(free_transfers))
    extra_transfers = max(0, num_transfers - int(free_transfers))
    total_penalty = float(extra_transfers * hit_penalty)
    gross_gain = best["gross_gain"]
    net_gain = gross_gain - total_penalty

    transfers_out_ids = [t["out_id"] for t in transfers]
    transfers_in_ids = [t["in_id"] for t in transfers]

    new_squad_ids = [pid for pid in current_squad_ids if pid not in transfers_out_ids] + transfers_in_ids
    new_squad = player_pool[player_pool["player_id"].isin(new_squad_ids)]
    optimal_xp = float(new_squad["expected_points"].sum())

    try:
        xi = select_starting_xi(new_squad) if len(new_squad) == 15 else None
    except RuntimeError:
        xi = None
    recommended_captain = None
    recommended_vice_captain = None
    optimal_starting_xi = []
    optimal_squad_ids = sorted(int(pid) for pid in new_squad_ids)
    optimal_bench_ids = []
    if xi is not None:
        captain_id = int(xi["captain_id"])
        vice_id = xi.get("vice_captain_id")
        if vice_id is None:
            candidates = [int(pid) for pid in xi["starting_ids"] if int(pid) != captain_id]
            vice_id = sorted(candidates, key=lambda pid: (-float(new_squad.loc[new_squad["player_id"] == pid, "expected_points"].iloc[0]), pid))[0]
        cap_row = new_squad[new_squad["player_id"] == captain_id].iloc[0]
        vice_row = new_squad[new_squad["player_id"] == int(vice_id)].iloc[0]
        recommended_captain = cap_row.get("web_name", str(captain_id))
        recommended_vice_captain = vice_row.get("web_name", str(vice_id))
        starting_ids = [int(pid) for pid in xi["starting_ids"]]
        optimal_bench_ids = [pid for pid in optimal_squad_ids if pid not in starting_ids]
        optimal_starting_xi = [
            {"player_id": int(pid), "web_name": new_squad.loc[new_squad["player_id"] == pid, "web_name"].iloc[0], "is_captain": int(pid) == captain_id, "is_vice_captain": int(pid) == int(vice_id)}
            for pid in starting_ids
        ]
    return {
        "current_expected_points": current_xp,
        "optimal_expected_points": optimal_xp,
        "gross_expected_gain": gross_gain,
        "transfers_count": num_transfers,
        "free_transfers_used": free_transfers_used,
        "hit_penalty_incurred": total_penalty,
        "net_expected_gain": net_gain,
        "recommended_captain": recommended_captain,
        "recommended_vice_captain": recommended_vice_captain,
        "transfers_out_ids": transfers_out_ids,
        "transfers_in_ids": transfers_in_ids,
        "optimal_squad_ids": optimal_squad_ids,
        "optimal_bench_ids": optimal_bench_ids,
        "optimal_starting_xi": optimal_starting_xi,
        "manager_mode": manager_mode,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Run manager_engine.py.')
    parser.parse_args()
    """
    Smoke test using real metadata from the current (2026-27) season.

    This is intentionally only a validation/demo entry point. It does not
    claim to represent a user's real current FPL squad. It reuses the same
    validated real-data path as weekly_pipeline.py and squad_optimizer.py:
    the current season's built features file (real fixture context) merged
    with players.csv (real team_id/position_id/cost) -- not the historical
    training_dataset_v1.csv <-> player_gameweek.csv join, which requires a
    completed season and it not needed here.
    """
    project_root = Path(__file__).resolve().parents[2]

    season = "2026-27"
    target_gw = 1
    features_path = project_root / "data" / "features" / season / "player_gameweek_features.csv"
    players_path = project_root / "data" / "processed" / season / "players.csv"

    print("=" * 72)
    print("PERSONALIZED MANAGER ENGINE TEST")
    print("=" * 72)

    if not features_path.exists():
        raise FileNotFoundError(
            f"{features_path} not found. Run scripts\\build_2026_27_gw1_features.py first."
        )
    if not players_path.exists():
        raise FileNotFoundError(f"Player metadata not found: {players_path}")

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
    pool["expected_points"] = pool["last_5_points_per_game"].fillna(0.0).astype(float)

    pool = pool.drop_duplicates("player_id").reset_index(drop=True)

    # Build a VALID demonstration squad from actual metadata.
    # We explicitly enforce the 3-player-per-team rule.
    selected = []
    team_counts: dict[int, int] = {}

    for position_id, required in [(1, 2), (2, 5), (3, 5), (4, 3)]:
        candidates = pool[pool["position_id"] == position_id]

        for _, row in candidates.iterrows():
            team_id = int(row["team_id"])
            if team_counts.get(team_id, 0) >= 3:
                continue

            selected.append(int(row["player_id"]))
            team_counts[team_id] = team_counts.get(team_id, 0) + 1

            if sum(
                1 for pid in selected
                if int(pool.loc[pool["player_id"] == pid, "position_id"].iloc[0])
                == position_id
            ) == required:
                break

    if len(selected) != 15:
        raise RuntimeError(
            f"Could not construct a valid 15-player smoke-test squad; "
            f"got {len(selected)}."
        )

    res = recommend_transfers(
        selected,
        pool,
        free_transfers=1,
        bank=0.5,
    )

    print(f"Current Squad Expected Pts   : {res['current_expected_points']:.2f}")
    print(f"Optimal Squad Expected Pts   : {res['optimal_expected_points']:.2f}")
    print(
        "Transfers Required            : "
        f"{res['transfers_count']} "
        f"(Free: {res['free_transfers_used']}, "
        f"Penalty: -{res['hit_penalty_incurred']:.0f} pts)"
    )
    print(f"Net Expected Gain             : {res['net_expected_gain']:+.2f} pts")
    print(f"Recommended Captain           : {res['recommended_captain']}")

    report_path = (
        project_root
        / "data"
        / "processed"
        / "manager_engine_sample.json"
    )

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)

    print(f"\nSaved manager engine report to: {report_path}")
    print("=" * 72)


if __name__ == "__main__":
    main()












