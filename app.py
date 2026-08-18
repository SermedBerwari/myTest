from __future__ import annotations
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT=Path(__file__).resolve().parent
SCRIPTS=ROOT/"scripts"
if str(SCRIPTS) not in sys.path: sys.path.insert(0,str(SCRIPTS))
PROCESSED=ROOT/"data/processed"
SUMMARY_PATH=PROCESSED/"weekly_automation_summary.json"
REGISTRY_PATH=PROCESSED/"model_registry.json"
WEB_PATH=ROOT/"web/index.html"
LOG=logging.getLogger("fpl.api")
PIPELINE_LOCK=Lock()
app=FastAPI(title="FPL AI Prediction System",version="2.0.0")

class PipelineRequest(BaseModel):
    season: str = Field(default="2026-27", pattern=r"^20\d{2}-\d{2}$")
    target_gameweek: int = Field(default=1, ge=1, le=38)
    squad_path: str | None = None

def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists(): raise HTTPException(status_code=404,detail=f"Required artifact not found: {path.name}")
    try: return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc: raise HTTPException(status_code=500,detail=f"Invalid JSON artifact: {path.name}") from exc

def _metadata(summary: dict[str, Any]) -> dict[str, Any]:
    registry=_load_json(REGISTRY_PATH) if REGISTRY_PATH.exists() else {}
    return {"target_season":summary.get("target_season"),"target_gameweek":summary.get("target_gameweek"),"data_timestamp":summary.get("timestamp_utc"),"model_version":registry.get("production_model"),"registry_version":registry.get("registry_version"),"warning_status":"none","last_successful_run":summary.get("timestamp_utc"),"pipeline_status":"success"}

def _summary() -> dict[str, Any]:
    summary=_load_json(SUMMARY_PATH)
    return {**_metadata(summary),**summary}

@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status":"ok","service":"fpl-api","timestamp_utc":datetime.now(timezone.utc).isoformat(),"summary_available":SUMMARY_PATH.exists(),"registry_available":REGISTRY_PATH.exists()}

@app.get("/api/status")
def status() -> dict[str, Any]:
    if not SUMMARY_PATH.exists(): return {"pipeline_status":"never_run","last_successful_run":None,"warning_status":"summary unavailable",**_metadata({})}
    return _metadata(_load_json(SUMMARY_PATH))

@app.get("/api/summary")
def get_summary() -> dict[str, Any]:
    return _summary()

@app.get("/api/players")
def get_players() -> dict[str, Any]:
    summary=_load_json(SUMMARY_PATH)
    optimal=summary.get("optimal_squad",{})
    players=[]
    if isinstance(optimal,dict):
        for key in ("starting_xi","starting_ids","squad","players"):
            if isinstance(optimal.get(key),list): players=optimal[key]; break
    elif isinstance(optimal,list): players=optimal
    return {"players":players,**_metadata(summary)}

@app.post("/api/run-pipeline")
def run_pipeline(request: PipelineRequest, api_key: str | None = Header(default=None, alias="X-API-Key")) -> dict[str, Any]:
    configured_key = os.getenv("FPL_API_KEY")
    if configured_key and api_key != configured_key:
        raise HTTPException(status_code=401, detail="Valid X-API-Key required")
    if not PIPELINE_LOCK.acquire(blocking=False): raise HTTPException(status_code=409,detail="Pipeline already running")
    try:
        from weekly_pipeline import run_weekly_pipeline
        squad=Path(request.squad_path) if request.squad_path else None
        result=run_weekly_pipeline(season=request.season,target_gw=request.target_gameweek,squad_path=squad)
        return {"pipeline_status":"success","warning_status":"none","result":result,**_metadata(result)}
    except HTTPException: raise
    except Exception as exc:
        LOG.exception("Pipeline failed")
        raise HTTPException(status_code=500,detail={"pipeline_status":"failed","warning_status":str(exc)}) from exc
    finally: PIPELINE_LOCK.release()

@app.get("/",response_class=HTMLResponse)
def dashboard() -> str:
    if not WEB_PATH.exists(): raise HTTPException(status_code=404,detail="Dashboard not found")
    return WEB_PATH.read_text(encoding="utf-8")

if __name__=="__main__":
    import uvicorn
    uvicorn.run("app:app",host="127.0.0.1",port=8000,reload=False)



