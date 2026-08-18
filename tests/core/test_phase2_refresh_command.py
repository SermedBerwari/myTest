import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def test_canonical_refresh_help_is_side_effect_free():
    r=subprocess.run([sys.executable,str(ROOT/"scripts/weekly_data_refresh.py"),"--help"],cwd=ROOT,capture_output=True,text=True)
    assert r.returncode==0
    assert "Canonical weekly FPL data refresh" in r.stdout

def test_canonical_refresh_dry_run_lists_policy_gate():
    r=subprocess.run([sys.executable,str(ROOT/"scripts/weekly_data_refresh.py"),"--project-root",str(ROOT),"--season","2026-27","--dry-run"],cwd=ROOT,capture_output=True,text=True)
    assert r.returncode==0
    assert "validate_release_data_policy.py" in r.stdout
    assert "fetch_bootstrap.py" in r.stdout
