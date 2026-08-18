import importlib.util
from pathlib import Path
import pandas as pd
import pytest

ROOT=Path(__file__).resolve().parents[2]
VALIDATOR_PATH=ROOT/"scripts/evaluation/validate_feature_leakage.py"

@pytest.fixture
def leakage_validator():
    spec=importlib.util.spec_from_file_location("phase4_leakage_validator",VALIDATOR_PATH)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

@pytest.fixture
def valid_rows():
    return pd.DataFrame([{'player_id':1,'gameweek':1,'target_gw':1,'feature_cutoff_gw':0,'target_points':0},{'player_id':1,'gameweek':4,'target_gw':4,'feature_cutoff_gw':3,'target_points':6}])

def test_target_gw_cutoff_is_strictly_prior(tmp_path, leakage_validator, valid_rows):
    path=tmp_path/"valid.csv"; valid_rows.to_csv(path,index=False)
    assert leakage_validator.validate(path)==[]
    invalid=valid_rows.copy(); invalid.loc[1,"feature_cutoff_gw"]=invalid.loc[1,"target_gw"]
    invalid_path=tmp_path/"equal_cutoff.csv"; invalid.to_csv(invalid_path,index=False)
    assert any("strictly before" in e for e in leakage_validator.validate(invalid_path))

def test_future_row_injection_is_rejected(tmp_path, leakage_validator, valid_rows):
    injected=pd.concat([valid_rows,pd.DataFrame([{'player_id':1,'gameweek':4,'target_gw':4,'feature_cutoff_gw':5,'target_points':6}])],ignore_index=True)
    path=tmp_path/"future_injection.csv"; injected.to_csv(path,index=False)
    errors=leakage_validator.validate(path)
    assert any("strictly before" in e for e in errors)
    assert len(errors)==1

def test_target_columns_are_explicitly_allowlisted(tmp_path, leakage_validator, valid_rows):
    invalid=valid_rows.copy(); invalid["target_secret_future_value"]=999
    path=tmp_path/"target_leak.csv"; invalid.to_csv(path,index=False)
    errors=leakage_validator.validate(path)
    assert any("unexpected target columns" in e for e in errors)
    assert "target_secret_future_value" in errors[0]

def test_missing_required_audit_columns_are_rejected(tmp_path, leakage_validator):
    path=tmp_path/"missing_contract.csv"; pd.DataFrame([{'player_id':1,'gameweek':2}]).to_csv(path,index=False)
    errors=leakage_validator.validate(path)
    assert any("missing required columns" in e for e in errors)

def test_real_v13_feature_artifact_passes(leakage_validator):
    artifacts=list((ROOT/"data/features").rglob("player_gameweek_features.csv"))
    assert artifacts, "No v1.3 feature artifact found"
    assert leakage_validator.validate(artifacts[0])==[]
