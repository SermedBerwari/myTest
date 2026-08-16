"""
train_minutes_model.py
======================
Trains an expected-minutes classifier/regressor (CatBoost/LightGBM) to predict
the probability of a player starting and their expected minutes played (0-90).

Integrates expected minutes with expected points:
  expected_value = expected_points_per_90 * (expected_minutes / 90.0)

Outputs:
  - Minutes model artifacts
  - Minutes prediction evaluation summary
"""

from __future__ import annotations

import json
from pathlib import Path
import joblib
import pandas as pd
from catboost import CatBoostClassifier, CatBoostRegressor
from sklearn.metrics import mean_absolute_error, accuracy_score


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    dataset_path = project_root / "data" / "processed" / "training_dataset_v1.csv"
    models_dir = project_root / "data" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("EXPECTED-MINUTES MODEL TRAINING & EVALUATION")
    print("=" * 72)

    df = pd.read_csv(dataset_path, low_memory=False)

    target_minutes_col = "target_minutes"
    non_feature_cols = [
        "season", "player_id", "gameweek", "target_gw", "feature_cutoff_gw",
        "web_name", "first_name", "second_name", "position_name",
        "target_points", "target_minutes", "target_goals", "target_assists",
        "target_clean_sheets", "target_bonus", "target_xg", "target_xa"
    ]
    feature_cols = [c for c in df.columns if c not in non_feature_cols and pd.api.types.is_numeric_dtype(df[c])]

    df[feature_cols] = df[feature_cols].fillna(0)
    df[target_minutes_col] = df[target_minutes_col].fillna(0)

    # Classification target: Started / Played >= 60 mins
    df["target_started"] = (df[target_minutes_col] >= 60).astype(int)

    train_mask = df["season"] != "2025-26"
    test_mask = df["season"] == "2025-26"

    X_train = df.loc[train_mask, feature_cols]
    y_train_mins = df.loc[train_mask, target_minutes_col]
    y_train_start = df.loc[train_mask, "target_started"]

    X_test = df.loc[test_mask, feature_cols]
    y_test_mins = df.loc[test_mask, target_minutes_col]
    y_test_start = df.loc[test_mask, "target_started"]

    print(f"Train samples: {len(X_train)} | Test samples: {len(X_test)}")

    # 1. Minutes Regressor
    print("\nTraining Minutes Regressor (CatBoost)...")
    mins_model = CatBoostRegressor(iterations=300, learning_rate=0.04, depth=6, random_seed=42, verbose=0)
    mins_model.fit(X_train, y_train_mins)
    mins_preds = mins_model.predict(X_test)
    mins_mae = float(mean_absolute_error(y_test_mins, mins_preds))

    # 2. Starting Classifier
    print("Training Starting Classifier (CatBoost)...")
    start_model = CatBoostClassifier(iterations=300, learning_rate=0.04, depth=6, random_seed=42, verbose=0)
    start_model.fit(X_train, y_train_start)
    start_preds = start_model.predict(X_test)
    start_acc = float(accuracy_score(y_test_start, start_preds))

    print(f"\nMinutes Regressor MAE  : {mins_mae:.2f} minutes")
    print(f"Starting Classifier ACC: {start_acc * 100:.2f}%")

    # Save models
    mins_model.save_model(models_dir / "minutes_regressor.cbm")
    start_model.save_model(models_dir / "starter_classifier.cbm")

    results = {
        "minutes_regressor_mae": mins_mae,
        "starter_classifier_accuracy": start_acc
    }
    report_path = project_root / "data" / "processed" / "minutes_model_results.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved minutes model results to: {report_path}")
    print("=" * 72)


if __name__ == "__main__":
    main()
