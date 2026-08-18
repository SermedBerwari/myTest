import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def test_registry_schema_and_active_model():
    d=json.loads((ROOT/"data/processed/model_registry.json").read_text(encoding="utf-8"))
    assert d["registry_version"]=="model-registry-1.0.0"
    assert d["production_model"]
    assert d["production_feature_version"]
    assert d["production_dataset_version"]
    assert d["xP_formula_version"]=="xp-v1.0.0"
    assert any(m["model_name"]==d["production_model"] and m["status"]=="active" for m in d["models"])

def test_registry_validator_passes():
    result=subprocess.run([sys.executable,"scripts/evaluation/validate_model_registry.py"],cwd=ROOT,text=True,capture_output=True)
    assert result.returncode==0, result.stdout+result.stderr
    assert "PASS model registry" in result.stdout
