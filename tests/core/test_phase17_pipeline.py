import json
import subprocess
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"scripts"))
import weekly_pipeline

def test_pipeline_missing_feature_rows_fails_clearly():
    with pytest.raises(ValueError,match="No feature rows found"):
        weekly_pipeline.run_weekly_pipeline(season="2025-26",target_gw=1,squad_path=ROOT/"config/my_squad.json")

def test_phase16_comparison_output_schema_and_repeated_run_determinism():
    script=ROOT/"scripts/evaluation/phase16_manager_comparison.py"
    out=ROOT/"data/processed/phase16_manager_comparison.json"
    subprocess.run([sys.executable,str(script)],cwd=ROOT,check=True,capture_output=True,text=True)
    first=out.read_bytes()
    subprocess.run([sys.executable,str(script)],cwd=ROOT,check=True,capture_output=True,text=True)
    second=out.read_bytes()
    assert first == second
    data=json.loads(second.decode("utf-8"))
    assert {"seasons","strategies","season_results","gameweek_results","strategy_summary"}.issubset(data)
    assert len(data["seasons"]) >= 3
    assert data["gameweek_results"]

def test_weekly_summary_schema_if_present():
    p=ROOT/"data/processed/weekly_automation_summary.json"
    if not p.exists(): pytest.skip("weekly summary not generated")
    data=json.loads(p.read_text(encoding="utf-8"))
    assert {"target_season","target_gameweek","real_squad_player_ids"}.issubset(data)
    assert len(data["real_squad_player_ids"]) == 15


def test_current_pipeline_smoke_success():
    summary=weekly_pipeline.run_weekly_pipeline(season="2026-27",target_gw=1,squad_path=ROOT/"config/my_squad.json")
    assert summary["target_season"] == "2026-27"
    assert summary["target_gameweek"] == 1
    assert len(summary["real_squad_player_ids"]) == 15
    assert {"optimal_squad","manager_recommendations","ai_report"}.issubset(summary)
