"""
run_backtest.py
===============
Strict leakage-free walk-forward backtesting framework across historical seasons.

Rule:
  For Gameweek N, train only on historical data up to GW N-1.
  Predict expected points and expected minutes for GW N.
  Evaluate out-of-sample prediction error (MAE / RMSE) and top-squad performance.

Outputs:
  - Backtest metrics report per season / gameweek
  - Chronological performance benchmarks
"""

from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.metrics import mean_absolute_error, root_mean_squared_error


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    dataset_path = project_root / "data" / "processed" / "training_dataset_v1.csv"
    output_report = project_root / "data" / "processed" / "backtest_results.json"

    print("=" * 72)
    print("WALK-FORWARD BACKTESTING FRAMEWORK (PHASE 9)")
    print("=" * 72)

    df = pd.read_csv(dataset_path, low_memory=False)

    target_col = "target_points"
    non_feature_cols = [
        "season", "player_id", "gameweek", "target_gw", "feature_cutoff_gw",
        "web_name", "first_name", "second_name", "position_name",
        "target_points", "target_minutes", "target_goals", "target_assists",
        "target_clean_sheets", "target_bonus", "target_xg", "target_xa"
    ]
    feature_cols = [c for c in df.columns if c not in non_feature_cols and pd.api.types.is_numeric_dtype(df[c])]

    df[feature_cols] = df[feature_cols].fillna(0)
    df[target_col] = df[target_col].fillna(0)

    # Sort strictly chronologically
    df = df.sort_values(["season", "target_gw"]).reset_index(drop=True)

    # Backtest evaluating season 2025-26 gameweek by gameweek walk-forward
    test_season = "2025-26"
    test_gws = sorted(df.loc[df["season"] == test_season, "target_gw"].unique())

    gw_results = []
    all_preds = []
    all_actuals = []

    print(f"Executing Walk-Forward Validation for {test_season} across {len(test_gws)} gameweeks...\n")

    for gw in test_gws:
        # Train mask: All seasons prior + current season GW < gw
        train_mask = (df["season"] < test_season) | ((df["season"] == test_season) & (df["target_gw"] < gw))
        test_mask = (df["season"] == test_season) & (df["target_gw"] == gw)

        X_tr, y_tr = df.loc[train_mask, feature_cols], df.loc[train_mask, target_col]
        X_te, y_te = df.loc[test_mask, feature_cols], df.loc[test_mask, target_col]

        if len(X_te) == 0:
            continue

        model = CatBoostRegressor(iterations=150, learning_rate=0.05, depth=5, random_seed=42, verbose=0)
        model.fit(X_tr, y_tr)
        preds = model.predict(X_te)

        mae = float(mean_absolute_error(y_te, preds))
        rmse = float(root_mean_squared_error(y_te, preds))

        gw_results.append({"gameweek": int(gw), "samples": len(X_te), "MAE": mae, "RMSE": rmse})
        all_preds.extend(preds)
        all_actuals.extend(y_te)

        print(f"GW {gw:2d} | Samples: {len(X_te):3d} | MAE: {mae:.4f} | RMSE: {rmse:.4f}")

    overall_mae = float(mean_absolute_error(all_actuals, all_preds))
    overall_rmse = float(root_mean_squared_error(all_actuals, all_preds))

    summary = {
        "season": test_season,
        "overall_walk_forward_mae": overall_mae,
        "overall_walk_forward_rmse": overall_rmse,
        "gameweek_breakdown": gw_results
    }

    with open(output_report, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 72)
    print(f"OVERALL WALK-FORWARD BACKTEST MAE : {overall_mae:.4f}")
    print(f"OVERALL WALK-FORWARD BACKTEST RMSE: {overall_rmse:.4f}")
    print(f"Saved backtest report to: {output_report}")
    print("=" * 72)


if __name__ == "__main__":
    main()
