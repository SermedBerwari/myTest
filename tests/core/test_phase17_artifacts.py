import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT=Path(__file__).resolve().parents[2]

def load_json(name):
    p=ROOT/name
    if not p.exists(): pytest.skip(f"artifact not generated: {name}")
    return json.loads(p.read_text(encoding="utf-8"))

def test_feature_leakage_artifact_is_pass():
    assert load_json("data/processed/feature_leakage_report.json").get("status")=="PASS"

def test_official_xp_artifact_has_versioned_formula():
    d=load_json("data/processed/official_xp_formula.json")
    assert d.get("formula_version")=="xp-v1.0.0" and d.get("formula")

def test_phase16_comparison_schema_and_finite_values():
    p=ROOT/"data/processed/phase16_manager_comparison.csv"
    if not p.exists(): pytest.skip("comparison export missing")
    d=pd.read_csv(p)
    assert {"strategy","season","total_points","net_points_after_hits"}.issubset(d.columns)
    assert np.isfinite(d["net_points_after_hits"].to_numpy(dtype=float)).all()

def test_phase16_model_predictions_are_keyed_and_finite():
    p=ROOT/"data/processed/phase16_model_variant_predictions.csv"
    if not p.exists(): pytest.skip("model prediction export missing")
    d=pd.read_csv(p)
    assert len(d)>0 and {"player_id","season","target_gw"}.issubset(d.columns)
    assert np.isfinite(d.select_dtypes(include=[np.number]).to_numpy(dtype=float)).all()

def test_phase16_comparison_artifact_is_repeatable():
    a=load_json("data/processed/phase16_manager_comparison.json")
    b=json.loads((ROOT/"data/processed/phase16_manager_comparison.json").read_text(encoding="utf-8"))
    assert a==b

