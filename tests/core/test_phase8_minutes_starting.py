import json
from pathlib import Path
import numpy as np
import pandas as pd
import scripts.decision.expected_points as xp

ROOT=Path(__file__).resolve().parents[2]

def _pool():
    return pd.DataFrame({"player_id":[1,2],"last_5_points_per_game":[2.0,4.0],"minutes_per_appearance_last_5":[45.0,90.0],"status":["available","injured"],"fixture_difficulty":[3.0,4.0]})

def test_minutes_and_start_probability_enter_decision_ready_points(monkeypatch,tmp_path):
    (tmp_path/"data"/"models").mkdir(parents=True)
    (tmp_path/"data"/"models"/"catboost_model.cbm").write_text("")
    (tmp_path/"data"/"models"/"minutes_regressor.cbm").write_text("")
    (tmp_path/"data"/"models"/"starter_classifier.cbm").write_text("")
    class Points:
        def load_model(self,path): pass
        def predict(self,X): return np.array([9.0,12.0])
    class Minutes:
        def load_model(self,path): pass
        def predict(self,X): return np.array([45.0,90.0])
    class Starter:
        def load_model(self,path): pass
        def predict_proba(self,X): return np.array([[0.25,0.75],[0.05,0.95]])
    class RegressorFactory:
        calls=0
        def __new__(cls):
            cls.calls += 1
            return Points() if cls.calls == 1 else Minutes()
    monkeypatch.setattr(xp,"CatBoostRegressor",RegressorFactory)
    monkeypatch.setattr(xp,"CatBoostClassifier",lambda: Starter())
    out=xp.compute_decision_ready_points(_pool(),tmp_path)
    assert out["expected_minutes"].tolist()==[45.0,90.0]
    assert out["start_probability"].tolist()==[0.75,0.95]
    assert np.allclose(out["expected_points"],[9.0,12.0])
    assert np.isfinite(out["expected_points"]).all()

def test_missing_models_and_new_player_have_finite_safe_outputs(tmp_path):
    pool=pd.DataFrame({"player_id":[99],"last_5_points_per_game":[np.nan],"minutes_per_appearance_last_5":[np.nan],"status":["available"]})
    out=xp.compute_decision_ready_points(pool,tmp_path)
    assert out["expected_minutes"].iloc[0]==60.0
    assert out["start_probability"].iloc[0]==1.0
    assert out["expected_points"].iloc[0]==0.0
    assert np.isfinite(out["expected_points"]).all()

def test_phase8_calibration_metrics_are_recorded():
    metrics=json.loads((ROOT/"data/processed/minutes_model_results.json").read_text(encoding="utf-8"))
    assert metrics["minutes_regressor_mae"] < 15.0
    assert 0.0 <= metrics["starter_classifier_accuracy"] <= 1.0
    assert 0.0 <= metrics["starter_classifier_brier_score"] <= 1.0
    assert 0.0 <= metrics["starter_classifier_expected_calibration_error"] <= 1.0



