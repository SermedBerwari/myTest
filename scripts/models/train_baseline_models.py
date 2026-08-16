"""
train_baseline_models.py
========================
Trains and evaluates baseline models on the unified training dataset
using chronological walk-forward cross-validation.

Baselines implemented:
  1. Historical Average Predictor
  2. Rolling Average Predictor (3, 5, 10 GWs)
  3. Ridge Linear Regression (L2 Regularized)

Outputs:
  - Evaluation summary metrics (MAE, RMSE)
  - Baseline benchmark report JSON
"""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, root_mean_squared_error


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    dataset_path = project_root / "data" / "processed" / "training_dataset_v1.csv"

    print("=" * 72)
    print("BASELINE PREDICTION MODELS EVALUATION")
    print("=" * 72)
    print(f"Loading training dataset from: {dataset_path}")

    df = pd.read_csv(dataset_path)

    # Define target and numeric feature set
    target_col = "target_points"
    non_feature_cols = [
        "season", "player_id", "gameweek", "target_gw", "feature_cutoff_gw",
        "target_points", "target_minutes", "target_goals", "target_assists",
        "target_clean_sheets", "target_bonus", "target_xg", "target_xa"
    ]
    feature_cols = [c for c in df.columns if c not in non_feature_cols and pd.api.types.is_numeric_dtype(df[c])]

    # Handle missing values in features
    df[feature_cols] = df[feature_cols].fillna(0)
    df[target_col] = df[target_col].fillna(0)

    # Sort chronologically for walk-forward splits
    df = df.sort_values(["season", "target_gw"]).reset_index(drop=True)

    # Perform Chronological Train/Test Split (Train: 2022-23 to 2024-25, Test: 2025-26)
    train_mask = df["season"] != "2025-26"
    test_mask = df["season"] == "2025-26"

    X_train = df.loc[train_mask, feature_cols]
    y_train = df.loc[train_mask, target_col]
    X_test = df.loc[test_mask, feature_cols]
    y_test = df.loc[test_mask, target_col]

    print(f"Train set: {len(X_train)} rows (2022-23 to 2024-25)")
    print(f"Test set : {len(X_test)} rows (2025-26)")

    results = {}

    # 1. Historical Baseline / Simple Moving Average (Last 3 GWs Points/Game)
    hist_pred = df.loc[test_mask, "last_3_points_per_game"].fillna(0)
    results["Historical_Average_Last3"] = {
        "MAE": float(mean_absolute_error(y_test, hist_pred)),
        "RMSE": float(root_mean_squared_error(y_test, hist_pred)),
    }

    # 2. Rolling Averages
    for w in [3, 5, 10]:
        roll_col = f"last_{w}_points_per_game"
        if roll_col in df.columns:
            roll_pred = df.loc[test_mask, roll_col].fillna(0)
            results[f"Rolling_Average_GW{w}"] = {
                "MAE": float(mean_absolute_error(y_test, roll_pred)),
                "RMSE": float(root_mean_squared_error(y_test, roll_pred)),
            }

    # 3. Ridge Linear Regression
    ridge = Ridge(alpha=1.0)
    ridge.fit(X_train, y_train)
    ridge_pred = ridge.predict(X_test)
    results["Ridge_Linear_Regression"] = {
        "MAE": float(mean_absolute_error(y_test, ridge_pred)),
        "RMSE": float(root_mean_squared_error(y_test, ridge_pred)),
    }

    print("\n" + "=" * 72)
    print("EVALUATION RESULTS ON 2025-26 TEST SET")
    print("=" * 72)
    for model_name, metrics in results.items():
        print(f"{model_name:<30} | MAE: {metrics['MAE']:.4f} | RMSE: {metrics['RMSE']:.4f}")

    # Output Benchmark Artifact
    output_report = project_root / "data" / "processed" / "baseline_model_results.json"
    with open(output_report, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved baseline evaluation results to: {output_report}")
    print("=" * 72)


if __name__ == "__main__":
    main()
