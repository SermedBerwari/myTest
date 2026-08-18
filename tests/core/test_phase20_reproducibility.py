import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def test_reproducibility_manifest_has_required_metadata():
    p=ROOT/"data/processed/reproducibility_manifest.json"
    d=json.loads(p.read_text(encoding="utf-8"))
    assert d["manifest_version"]=="reproducibility-1.0.0"
    assert d["runtime"]["python"]
    assert d["runtime"]["git_commit"]
    assert d["dependencies"]["pip_check"]=="PASS"
    assert d["dataset"]["feature_version"]
    assert d["dataset"]["data_cutoff_policy"]
    assert d["models"]["production_model"]

def test_reproducibility_validator_passes():
    r=subprocess.run([sys.executable,"scripts/evaluation/validate_reproducibility.py"],cwd=ROOT,text=True,capture_output=True)
    assert r.returncode==0,r.stdout+r.stderr
    assert "PASS reproducibility manifest" in r.stdout
