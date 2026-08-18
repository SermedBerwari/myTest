import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def test_live_integration_validator_passes():
    r=subprocess.run([sys.executable,"scripts/evaluation/validate_live_integration.py","--season","2026-27","--gameweek","1"],cwd=ROOT,text=True,capture_output=True)
    assert r.returncode==0,r.stdout+r.stderr
    assert "PASS official_gw1_recommendation" in r.stdout
    assert "PASS recommendation_legality" in r.stdout

def test_live_integration_report_has_all_checks():
    p=ROOT/"data/processed/phase23_live_integration_report.json"
    d=json.loads(p.read_text(encoding="utf-8"))
    assert d["status"]=="PASS"
    assert d["season"]=="2026-27"
    assert d["gameweek"]==1
    assert all(v["status"]=="PASS" for v in d["checks"].values())
