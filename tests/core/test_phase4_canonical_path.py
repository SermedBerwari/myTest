import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def test_canonical_feature_path_validator_passes():
    r=subprocess.run([sys.executable,str(ROOT/"scripts/evaluation/validate_canonical_feature_path.py"),"--project-root",str(ROOT)],cwd=ROOT,capture_output=True,text=True)
    assert r.returncode==0, r.stdout+r.stderr
    report=json.loads((ROOT/"data/processed/canonical_feature_path_report.json").read_text(encoding="utf-8"))
    assert report["canonical"]=="scripts/features/build_features_v1_3.py"
    assert report["pass"] is True

def test_canonical_wrapper_help_is_side_effect_free():
    r=subprocess.run([sys.executable,str(ROOT/"scripts/build_features.py"),"--help"],cwd=ROOT,capture_output=True,text=True)
    assert r.returncode==0
    assert "Canonical leakage-safe feature build" in r.stdout
