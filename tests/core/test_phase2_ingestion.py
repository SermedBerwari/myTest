import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SEASON="2026-27"
RAW=ROOT/"data/raw"/SEASON

def test_raw_snapshot_layout_and_counts():
    assert len(list((RAW/"bootstrap").glob("*.json"))) >= 1
    assert len(list((RAW/"fixtures").glob("*.json"))) >= 1
    dirs=[p for p in (RAW/"players").iterdir() if p.is_dir()]
    assert len(dirs) >= 590
    assert all(list(p.glob("*.json")) for p in dirs)

def test_latest_bootstrap_schema_and_unique_ids():
    latest=max((RAW/"bootstrap").glob("*.json"),key=lambda p:p.name)
    data=json.loads(latest.read_text(encoding="utf-8"))
    assert {"elements","teams","events"}.issubset(data)
    ids=[x["id"] for x in data["elements"]]
    assert len(ids)==len(set(ids))
    assert all({"id","first_name","second_name","team","element_type","now_cost","total_points"}.issubset(x) for x in data["elements"])

def test_snapshot_names_are_parseable_and_ordered():
    for kind in ["bootstrap","fixtures"]:
        files=sorted((RAW/kind).glob("*.json"),key=lambda p:p.name)
        stamps=[datetime.strptime(p.stem,"%Y-%m-%d_%H-%M-%S") for p in files]
        assert all(x<y for x,y in zip(stamps,stamps[1:]))

def test_freshness_validator_passes_current_snapshot():
    cmd=[sys.executable,str(ROOT/"scripts/evaluation/validate_snapshot_freshness.py"),"--project-root",str(ROOT),"--season",SEASON,"--as-of-utc","2026-08-18T12:00:00+00:00"]
    result=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==0, result.stdout+result.stderr
    assert json.loads((ROOT/"data/processed/phase2_freshness_report.json").read_text(encoding="utf-8"))["pass"] is True

def test_freshness_validator_rejects_stale_as_of_time():
    cmd=[sys.executable,str(ROOT/"scripts/evaluation/validate_snapshot_freshness.py"),"--project-root",str(ROOT),"--season",SEASON,"--as-of-utc","2026-08-25T12:00:00+00:00"]
    result=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==2
