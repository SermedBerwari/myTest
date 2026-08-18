from fastapi.testclient import TestClient
import app

client=TestClient(app.app)

def test_health_contract():
    r=client.get("/api/health")
    assert r.status_code==200
    d=r.json()
    assert d["status"]=="ok"
    assert "timestamp_utc" in d

def test_status_contract():
    r=client.get("/api/status")
    assert r.status_code==200
    d=r.json()
    assert "pipeline_status" in d
    assert "warning_status" in d

def test_summary_contains_phase22_metadata():
    r=client.get("/api/summary")
    assert r.status_code==200
    d=r.json()
    for key in ["target_season","target_gameweek","data_timestamp","model_version","warning_status","last_successful_run","pipeline_status"]: assert key in d

def test_players_contract():
    r=client.get("/api/players")
    assert r.status_code==200
    d=r.json()
    assert isinstance(d["players"],list)
    assert "target_gameweek" in d

def test_dashboard_served():
    r=client.get("/")
    assert r.status_code==200
    assert "FPL" in r.text

def test_pipeline_request_validation():
    r=client.post("/api/run-pipeline",json={"season":"bad","target_gameweek":0})
    assert r.status_code==422

def test_pipeline_api_key_enforcement(monkeypatch):
    monkeypatch.setenv("FPL_API_KEY","test-secret")
    denied=client.post("/api/run-pipeline",json={"season":"2026-27","target_gameweek":1})
    assert denied.status_code==401
