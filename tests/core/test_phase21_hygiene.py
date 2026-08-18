import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def test_repository_hygiene_required_controls_exist():
    for rel in [".gitignore","requirements.txt","FPL_Fantasy_MASTER_PLAN.md","data/processed/model_registry.json","data/processed/reproducibility_manifest.json"]:
        assert (ROOT/rel).exists(), rel
    assert (ROOT/"old documents/phase21_archived_experiments").exists()

def test_repository_hygiene_validator_passes():
    r=subprocess.run([sys.executable,"scripts/evaluation/validate_repository_hygiene.py"],cwd=ROOT,text=True,capture_output=True)
    assert r.returncode==0,r.stdout+r.stderr
    assert "PASS repository hygiene" in r.stdout
