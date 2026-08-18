"""
train_advanced_models.py
========================
Trains and evaluates advanced Gradient Boosting models (XGBoost, LightGBM, CatBoost)
on the unified FPL dataset using chronological validation (Train: 2022-23 to 2024-25, Test: 2025-26).

Outputs:
  - Model metrics comparison (MAE, RMSE) vs Baselines
  - Saved model artifacts (.json / .cbm / .pkl)
  - Advanced models evaluation report
"""

from __future__ import annotations
import argparse
import argparse

import argparse
import json
from pathlib import Path
import argparse
import joblib
import argparse
import pandas as pd
from catboost import CatBoostRegressor
from lightgbm import LGBMRegressor
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from xgboost import XGBRegressor


def main() -> None:
    parser = argparse.ArgumentParser(description='Run train_advanced_models.py.')
    parser.parse_args()
    project_root = Path(__file__).resolve().parents[2]
    dataset_path = project_root / "data" / "processed" / "training_dataset_v1.csv"
    models_dir = project_root / "data" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("ADVANCED PREDICTION MODELS TRAINING & EVALUATION")
    print("=" * 72)

    df = pd.read_csv(dataset_path, low_memory=False)

    target_col = "target_points"
    non_feature_cols = [
        "season", "player_id", "gameweek", "target_gw", "feature_cutoff_gw",
        "web_name", "first_name", "second_name", "position_name",
        "target_points", "target_minutes", "target_goals", "target_assists",
        "target_clean_sheets", "target_bonus", "target_xg", "target_xa"
    ]
    feature_cols = [c for c in df.columns if c not in non_feature_cols and not c.startswith("target_") and c != "fixture_id" and pd.api.types.is_numeric_dtype(df[c])]

    df[feature_cols] = df[feature_cols].fillna(0)
    df[target_col] = df[target_col].fillna(0)

    train_mask = df["season"] != "2025-26"
    test_mask = df["season"] == "2025-26"

    X_train = df.loc[train_mask, feature_cols]
    y_train = df.loc[train_mask, target_col]
    X_test = df.loc[test_mask, feature_cols]
    y_test = df.loc[test_mask, target_col]

    print(f"Train samples: {len(X_train)} | Test samples: {len(X_test)} | Features: {len(feature_cols)}")

    models = {
        "XGBoost": XGBRegressor(n_estimators=300, learning_rate=0.03, max_depth=6, random_state=42, n_jobs=-1),
        "LightGBM": LGBMRegressor(n_estimators=300, learning_rate=0.03, max_depth=6, random_state=42, verbose=-1, n_jobs=-1),
        "CatBoost": CatBoostRegressor(iterations=300, learning_rate=0.03, depth=6, random_seed=42, verbose=0)
    }

    results = {}

    for name, model in models.items():
        print(f"\nTraining {name}...")
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        mae = float(mean_absolute_error(y_test, preds))
        rmse = float(root_mean_squared_error(y_test, preds))
        results[name] = {"MAE": mae, "RMSE": rmse}
        print(f"{name} -> MAE: {mae:.4f} | RMSE: {rmse:.4f}")

        # Save model
        if name == "XGBoost":
            model.save_model(models_dir / "xgboost_model.json")
        elif name == "LightGBM":
            joblib.dump(model, models_dir / "lightgbm_model.pkl")
        elif name == "CatBoost":
            model.save_model(models_dir / "catboost_model.cbm")

    # Load baseline results for direct comparison
    baseline_path = project_root / "data" / "processed" / "baseline_model_results.json"
    if baseline_path.exists():
        with open(baseline_path, encoding="utf-8") as f:
            baseline_results = json.load(f)
        results["_baselines"] = baseline_results

    # Output report
    report_path = project_root / "data" / "processed" / "advanced_model_results.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 72)
    print("SUMMARY OF ADVANCED MODEL LIFT OVER BASELINE (RIDGE MAE: 0.9601)")
    print("=" * 72)
    for name, m in results.items():
        if not name.startswith("_"):
            lift = ((0.9601 - m["MAE"]) / 0.9601) * 100
            print(f"{name:<15} | MAE: {m['MAE']:.4f} | RMSE: {m['RMSE']:.4f} | Lift over Ridge: +{lift:.2f}%")

    print(f"\nSaved advanced model results to: {report_path}")
    print("=" * 72)


if __name__ == "__main__":
    main()



