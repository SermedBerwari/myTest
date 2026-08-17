"""
historical_manager_simulator.py
================================
FIX 6 + FIX 7 (see FPL_PROJECT_COMPLETION_AND_FIX_PLAN.md): the project's
single most important missing piece -- an end-to-end, leakage-safe,
gameweek-by-gameweek historical FPL MANAGER simulation (not just a
player-points prediction backtest, which scripts/evaluation/run_backtest.py
already covers).

For every simulated gameweek, only information available BEFORE that
gameweek is used to make decisions (transfers, starting XI, captain).
Actual scoring uses REAL historical results.

Leakage safety
--------------
  - Prediction models (points / minutes) are trained ONCE per target season,
    using only seasons strictly BEFORE that season (seasonal walk-forward).
  - Within a season, each row's engineered features already only encode
    information from gameweeks < that row's target_gw (enforced by the
    feature engine's `feature_cutoff_gw` rule), so a single per-season model
    does not leak future gameweeks within the season either.
  - Real historical price ('value' from player_gameweek.csv) is looked up
    PER GAMEWEEK, so budget constraints reflect the price at that point in
    the season, not a season-end price.
  - Decisions (transfers, starting XI, captain) are driven by PREDICTED
    expected points. Scoring uses the ACTUAL historical target_points.

Strategies benchmarked (FIX 7)
-------------------------------
  - previous_gw       : naive predictor = last gameweek's actual points.
  - rolling_average    : naive predictor = last_5_points_per_game.
  - no_transfer        : AI model prediction, squad fixed after GW1 (only
                          starting XI / captain re-picked weekly).
  - simple_highest_xp  : AI model prediction, unlimited free "wildcard every
                          week" re-optimization (upper-bound benchmark).
  - ai_manager          : AI model prediction, realistic transfer economy
                          (1 free transfer/week, cap 2 saved, -4 hit penalty,
                          only transfers if net predicted gain > 0).

Known simplifications (documented, not hidden):
  - No chip usage (wildcard/free hit/bench boost/triple captain) is modeled.
  - No FPL autosub logic for a starter who scores 0 due to a blank -- the
    picked starting XI's actual points are counted as-is.
  - Free transfers cap at 2 (a reasonable classic-rules approximation).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from catboost import CatBoostRegressor

scripts_dir = Path(__file__).resolve().parents[1]
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from optimizer.squad_optimizer import optimize_squad, select_starting_xi  # noqa: E402
from optimizer.manager_engine import recommend_transfers  # noqa: E402

NON_FEATURE_COLS = [
    "season", "player_id", "gameweek", "target_gw", "feature_cutoff_gw",
    "web_name", "first_name", "second_name", "position_name",
    "target_points", "target_minutes", "target_goals", "target_assists",
    "target_clean_sheets", "target_bonus", "target_xg", "target_xa",
]

STRATEGIES = ["previous_gw", "rolling_average", "no_transfer", "simple_highest_xp", "ai_manager"]
MAX_FREE_TRANSFERS = 2
HIT_PENALTY = 4.0
STARTING_BUDGET = 100.0


def _feature_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in NON_FEATURE_COLS and pd.api.types.is_numeric_dtype(df[c])]


def _train_season_models(df: pd.DataFrame, target_season: str, feat_cols: list[str]):
    """Train points + minutes models using ONLY seasons strictly before target_season."""
    train_mask = df["season"] < target_season
    X_tr = df.loc[train_mask, feat_cols].fillna(0)
    y_points = df.loc[train_mask, "target_points"].fillna(0)
    y_minutes = df.loc[train_mask, "target_minutes"].fillna(0)

    points_model = CatBoostRegressor(iterations=200, learning_rate=0.05, depth=6, random_seed=42, verbose=0)
    points_model.fit(X_tr, y_points)

    minutes_model = CatBoostRegressor(iterations=200, learning_rate=0.05, depth=6, random_seed=42, verbose=0)
    minutes_model.fit(X_tr, y_minutes)

    return points_model, minutes_model


def _load_price_lookup(project_root: Path, season: str) -> pd.DataFrame:
    """
    Authoritative per-gameweek player metadata (team_id, position, price)
    sourced directly from player_gameweek.csv, NOT from the engineered
    features file. The features file derives team_id from fixture
    was_home/team_h/team_a lookups, which have gaps for some historical
    rows (was_home sometimes unparseable in the raw source); this file's
    own team_id/position columns are populated directly and don't have
    that gap, so using it here avoids silently losing squad members from
    the weekly pool (which was otherwise blocking almost all transfer
    decisions -- see FIX 6 validation notes).
    """
    pgw_path = project_root / "data" / "processed" / season / "player_gameweek.csv"
    pgw = pd.read_csv(pgw_path, low_memory=False)
    pgw = pgw.dropna(subset=["value", "team_id", "position"]).copy()
    pgw["cost"] = pgw["value"] / 10.0

    # Position label varies across seasons in the raw data ("GK" in some
    # older season files, "GKP" in newer ones) -- map both defensively.
    position_map = {"GKP": 1, "GK": 1, "DEF": 2, "MID": 3, "FWD": 4, "FW": 4}
    pgw["position_id_real"] = pgw["position"].map(position_map)
    pgw = pgw.dropna(subset=["position_id_real"])
    pgw["position_id_real"] = pgw["position_id_real"].astype(int)
    pgw["team_id_real"] = pgw["team_id"].astype(int)

    return pgw[["player_id", "gameweek", "cost", "team_id_real", "position_id_real"]]


def _build_gw_pool(
    df_season: pd.DataFrame,
    gw: int,
    feat_cols: list[str],
    points_model,
    minutes_model,
    price_lookup: pd.DataFrame,
) -> pd.DataFrame:
    """Build one gameweek's player pool with predicted + actual points and real price."""
    pool = df_season[df_season["target_gw"] == gw].copy()
    if pool.empty:
        return pool

    X = pool[feat_cols].fillna(0)
    pool["raw_points_pred"] = points_model.predict(X)
    minutes_pred = minutes_model.predict(X).clip(0, 90)
    pool["expected_minutes_pred"] = minutes_pred

    recent_minutes_fraction = (
        pool["minutes_per_appearance_last_5"].fillna(45.0) / 90.0
    ).clip(lower=0.15, upper=1.0)
    pool["ai_expected_points"] = (
        (pool["raw_points_pred"] / recent_minutes_fraction) * (minutes_pred / 90.0)
    )

    pool["previous_gw_points"] = pool["last_total_points"].fillna(0.0)
    pool["rolling_average_points"] = pool["last_5_points_per_game"].fillna(0.0)
    pool["actual_points"] = pool["target_points"].fillna(0.0)

    # Real per-gameweek team_id/position_id/price from the authoritative
    # player_gameweek.csv (see _load_price_lookup docstring for why this is
    # more reliable than the features file's own derived columns).
    gw_meta = price_lookup[price_lookup["gameweek"] <= gw].sort_values("gameweek")
    latest_meta = gw_meta.groupby("player_id", as_index=False).last()
    pool = pool.drop(columns=["team_id", "position_id"], errors="ignore")
    pool = pool.merge(latest_meta, on="player_id", how="left")
    pool = pool.rename(columns={"team_id_real": "team_id", "position_id_real": "position_id"})

    pool = pool.dropna(subset=["team_id", "position_id", "cost"])
    pool["team_id"] = pool["team_id"].astype(int)
    pool["position_id"] = pool["position_id"].astype(int)
    pool["player_id"] = pool["player_id"].astype(int)
    pool = pool.drop_duplicates("player_id").reset_index(drop=True)
    return pool


def _pick_squad(pool: pd.DataFrame, expected_col: str, budget: float) -> dict:
    p = pool.copy()
    p["expected_points"] = p[expected_col]
    return optimize_squad(p, budget=budget)


def _force_replace_missing(squad_ids: list[int], squad_meta: dict, pool_s: pd.DataFrame, bank: float) -> tuple[list, dict, float]:
    """
    A squad member can permanently vanish from the per-gameweek data
    (released, transferred out of the Premier League, data gap for the
    rest of the season). A real manager would have to react to that
    regardless of free-transfer availability, so this performs a mandatory,
    no-hit, same-position replacement using the departing player's last
    known price as the budget reference. This must run BEFORE the optional
    (hit-costing) transfer logic each week, otherwise a single vanished
    player permanently freezes that strategy's squad for the rest of the
    season (see FIX 6 validation notes -- this caused ai_manager to exactly
    mirror no_transfer in early testing).
    """
    present_ids = set(pool_s["player_id"])
    missing = [pid for pid in squad_ids if pid not in present_ids]
    if not missing:
        return squad_ids, squad_meta, bank

    squad_ids = list(squad_ids)
    for pid in missing:
        meta = squad_meta.get(pid, {"position_id": None, "cost": 0.0})
        pos = meta["position_id"]
        last_cost = meta["cost"]
        candidates = pool_s[
            (pool_s["position_id"] == pos) & (~pool_s["player_id"].isin(squad_ids))
        ].copy()
        if candidates.empty:
            continue  # nothing valid to replace with this week; squad stays short, scoring will skip this week
        affordable = candidates[candidates["cost"] <= bank + last_cost]
        pick_from = affordable if not affordable.empty else candidates.sort_values("cost")
        new_row = pick_from.sort_values("expected_points", ascending=False).iloc[0]

        squad_ids.remove(pid)
        squad_ids.append(int(new_row["player_id"]))
        bank = bank + last_cost - float(new_row["cost"])
        squad_meta.pop(pid, None)
        squad_meta[int(new_row["player_id"])] = {"position_id": pos, "cost": float(new_row["cost"])}

    return squad_ids, squad_meta, bank


def simulate_season(
    df: pd.DataFrame,
    project_root: Path,
    target_season: str,
) -> dict:
    feat_cols = _feature_cols(df)
    df_season = df[df["season"] == target_season].sort_values("target_gw")
    gameweeks = sorted(df_season["target_gw"].unique())
    if not gameweeks:
        return {"season": target_season, "error": "no rows for this season"}

    print(f"  Training season models for {target_season} on all prior seasons...")
    points_model, minutes_model = _train_season_models(df, target_season, feat_cols)
    price_lookup = _load_price_lookup(project_root, target_season)

    results = {s: {"season_actual_points": 0.0, "transfers": 0, "hits": 0, "weeks": 0,
                    "forced_replacements": 0, "bench_points_wasted": 0.0, "gw_log": []} for s in STRATEGIES}

    state = {s: {"squad_ids": None, "bank": 0.0, "free_transfers": 1, "squad_meta": {}} for s in STRATEGIES}

    expected_col_map = {
        "previous_gw": "previous_gw_points",
        "rolling_average": "rolling_average_points",
        "no_transfer": "ai_expected_points",
        "simple_highest_xp": "ai_expected_points",
        "ai_manager": "ai_expected_points",
    }

    for gw in gameweeks:
        pool = _build_gw_pool(df_season, int(gw), feat_cols, points_model, minutes_model, price_lookup)
        if pool.empty or len(pool) < 15:
            continue

        for strat in STRATEGIES:
            expected_col = expected_col_map[strat]
            pool_s = pool.copy()
            pool_s["expected_points"] = pool_s[expected_col]

            st = state[strat]

            if strat == "simple_highest_xp":
                # Unlimited free re-optimization every week (upper-bound benchmark).
                try:
                    picked = _pick_squad(pool_s, expected_col, STARTING_BUDGET)
                except RuntimeError:
                    continue
                squad_ids = [p["player_id"] for p in picked["starting_xi"] + picked["bench"]]

            elif st["squad_ids"] is None:
                # First week for this strategy: build initial squad.
                try:
                    picked = _pick_squad(pool_s, expected_col, STARTING_BUDGET)
                except RuntimeError:
                    continue
                squad_ids = [p["player_id"] for p in picked["starting_xi"] + picked["bench"]]
                spent = picked["total_cost"]
                st["bank"] = STARTING_BUDGET - spent
                st["squad_ids"] = squad_ids
                st["squad_meta"] = {
                    int(pid): {
                        "position_id": int(pool_s.loc[pool_s["player_id"] == pid, "position_id"].iloc[0]),
                        "cost": float(pool_s.loc[pool_s["player_id"] == pid, "cost"].iloc[0]),
                    }
                    for pid in squad_ids
                }

            else:
                # Mandatory no-hit replacement for any squad member who has
                # vanished from this week's data, THEN (for strategies other
                # than no_transfer) the normal optional transfer decision.
                squad_ids, st["squad_meta"], st["bank"] = _force_replace_missing(
                    st["squad_ids"], st["squad_meta"], pool_s, st["bank"]
                )
                if squad_ids != st["squad_ids"]:
                    results[strat]["forced_replacements"] += 1
                st["squad_ids"] = squad_ids

                if strat != "no_transfer":
                    try:
                        rec = recommend_transfers(
                            squad_ids, pool_s,
                            free_transfers=st["free_transfers"],
                            bank=max(0.0, st["bank"]),
                            hit_penalty=HIT_PENALTY,
                        )
                    except (ValueError, RuntimeError):
                        rec = None

                    if rec is not None and rec["net_expected_gain"] > 0 and rec["transfers_count"] > 0:
                        out_ids = set(rec["transfers_out_ids"])
                        in_ids = rec["transfers_in_ids"]
                        squad_ids = [pid for pid in squad_ids if pid not in out_ids] + in_ids

                        cost_out = pool_s[pool_s["player_id"].isin(out_ids)]["cost"].sum()
                        cost_in = pool_s[pool_s["player_id"].isin(in_ids)]["cost"].sum()
                        st["bank"] = st["bank"] + cost_out - cost_in
                        st["squad_ids"] = squad_ids

                        for pid in out_ids:
                            st["squad_meta"].pop(pid, None)
                        for pid in in_ids:
                            row = pool_s.loc[pool_s["player_id"] == pid].iloc[0]
                            st["squad_meta"][int(pid)] = {
                                "position_id": int(row["position_id"]), "cost": float(row["cost"])
                            }

                        results[strat]["transfers"] += rec["transfers_count"]
                        results[strat]["hits"] += int(rec["hit_penalty_incurred"] / HIT_PENALTY)
                        st["free_transfers"] = max(
                            1, min(MAX_FREE_TRANSFERS, st["free_transfers"] - rec["transfers_count"] + 1)
                        )
                    else:
                        st["free_transfers"] = min(MAX_FREE_TRANSFERS, st["free_transfers"] + 1)

            squad_rows = pool_s[pool_s["player_id"].isin(squad_ids)]
            if len(squad_rows) != 15:
                continue  # still short this week (no valid replacement found) -- skip scoring only

            xi = select_starting_xi(squad_rows)  # decision made on PREDICTED points
            actual_lookup = squad_rows.set_index("player_id")["actual_points"]
            starters_actual = actual_lookup.loc[xi["starting_ids"]].sum()
            captain_actual = actual_lookup.loc[xi["captain_id"]]
            bench_actual = actual_lookup.loc[xi["bench_ids"]].sum()

            week_score = float(starters_actual + captain_actual)  # captain doubled
            results[strat]["season_actual_points"] += week_score
            results[strat]["bench_points_wasted"] += float(bench_actual)
            results[strat]["weeks"] += 1
            results[strat]["gw_log"].append({"gw": int(gw), "points": week_score})

    for strat in STRATEGIES:
        r = results[strat]
        r["avg_gw_points"] = r["season_actual_points"] / r["weeks"] if r["weeks"] else 0.0

    return {"season": target_season, "gameweeks_simulated": len(gameweeks), "strategies": results}


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    dataset_path = project_root / "data" / "processed" / "training_dataset_v1.csv"

    print("=" * 72)
    print("HISTORICAL MANAGER SIMULATOR (FIX 6 + FIX 7)")
    print("=" * 72)

    df = pd.read_csv(dataset_path, low_memory=False)
    df = df.sort_values(["season", "target_gw"]).reset_index(drop=True)

    # 2022-23 is used as training-only history (no prior season to walk
    # forward from within this dataset), matching the plan's recommended
    # multi-season list.
    target_seasons = ["2023-24", "2024-25", "2025-26"]

    all_results = {}
    for season in target_seasons:
        print(f"\nSimulating season {season}...")
        season_result = simulate_season(df, project_root, season)
        all_results[season] = season_result

        for strat, r in season_result.get("strategies", {}).items():
            print(
                f"    {strat:<20} | weeks: {r['weeks']:2d} | season pts: {r['season_actual_points']:7.1f} "
                f"| avg/gw: {r['avg_gw_points']:5.2f} | transfers: {r['transfers']:2d} | hits: {r['hits']}"
            )

    output_path = project_root / "data" / "processed" / "historical_manager_simulation.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    print(f"\nSaved historical manager simulation results to: {output_path}")
    print("=" * 72)


if __name__ == "__main__":
    main()
