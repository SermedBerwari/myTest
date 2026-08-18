import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def test_catboost_is_registered_as_official_production_model():
    registry=json.loads((ROOT/"data/processed/model_registry.json").read_text(encoding="utf-8"))
    selection=json.loads((ROOT/"data/processed/phase7_model_selection.json").read_text(encoding="utf-8"))
    assert registry["production_model"]=="catboost_model"
    assert registry["production_evaluation_protocol"]=="chronological_train_2022-23_to_2024-25_test_2025-26"
    assert selection["official_model"]=="catboost_model"
    assert selection["production_consumption_verified"] is True
    assert selection["verified_consumer"]=="scripts/decision/expected_points.py"

def test_catboost_beats_advanced_candidates_and_ridge_on_mae():
    selection=json.loads((ROOT/"data/processed/phase7_model_selection.json").read_text(encoding="utf-8"))
    candidates=selection["advanced_candidates"]
    baselines=selection["baselines"]
    cat_mae=candidates["CatBoost"]["MAE"]
    assert cat_mae < candidates["XGBoost"]["MAE"]
    assert cat_mae < candidates["LightGBM"]["MAE"]
    assert cat_mae < baselines["Ridge_Linear_Regression"]["MAE"]

def test_selected_artifact_exists():
    assert (ROOT/"data/models/catboost_model.cbm").exists()
