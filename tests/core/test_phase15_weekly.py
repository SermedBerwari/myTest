import json
from pathlib import Path
import pytest
from scripts.run_weekly_canonical import run_canonical_weekly, _validate_summary

def summary():
    return {"target_season":"2026-27","target_gameweek":1,"real_squad_player_ids":list(range(1,16)),"optimal_squad":{"starting_xi":[{"player_id":1}],"bench":[{"player_id":2}] + [{"player_id":i} for i in range(3,16)]},"manager_recommendations":{"gross_expected_gain":5.0,"hit_penalty_incurred":4.0,"net_expected_gain":1.0},"ai_report":{}}

def test_output_validation_rejects_invalid_squad_and_net_arithmetic():
    with pytest.raises(ValueError,match="exactly 15"):
        _validate_summary({**summary(),"optimal_squad":{"starting_xi":[],"bench":[]}})
    bad=summary(); bad["manager_recommendations"]["net_expected_gain"]=99.0
    with pytest.raises(ValueError,match="net-of-hit"):
        _validate_summary(bad)

def test_canonical_wrapper_writes_metadata_and_manifests(tmp_path,monkeypatch):
    import scripts.weekly_pipeline as pipeline
    monkeypatch.setattr(pipeline,"run_weekly_pipeline",lambda **kwargs:summary())
    manifest=run_canonical_weekly(root=tmp_path)
    assert manifest["status"]=="PASS"
    assert manifest["run_id"].startswith("weekly-")
    assert manifest["model_version"]=="unknown"
    out=tmp_path/"data/processed/weekly_automation_summary_canonical.json"
    assert out.exists()
    payload=json.loads(out.read_text())
    assert payload["pipeline_metadata"]["run_id"]==manifest["run_id"]
    assert (tmp_path/"data/processed/weekly_automation_output_manifest.json").exists()

def test_canonical_wrapper_records_failure_manifest(tmp_path,monkeypatch):
    import scripts.weekly_pipeline as pipeline
    def fail(**kwargs): raise RuntimeError("simulated stage failure")
    monkeypatch.setattr(pipeline,"run_weekly_pipeline",fail)
    with pytest.raises(RuntimeError,match="simulated"):
        run_canonical_weekly(root=tmp_path)
    manifest=json.loads((tmp_path/"data/processed/weekly_automation_output_manifest.json").read_text())
    assert manifest["status"]=="FAIL"
    assert manifest["stages"][-1]["stage"]=="failure"
