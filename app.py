"""
app.py
======
FastAPI Web Backend & Dashboard Server for FPL AI Prediction System.

Endpoints:
  - GET /                : Serves the Web Dashboard UI
  - GET /api/summary     : Returns the latest weekly automation summary JSON
  - POST /api/run-pipeline: Triggers the weekly pipeline re-run
  - GET /api/players     : Returns top projected players
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

project_root = Path(__file__).resolve().parent
scripts_dir = project_root / "scripts"
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

app = FastAPI(title="FPL AI Prediction System", version="1.0.0")

PROCESSED_DIR = project_root / "data" / "processed"


@app.get("/api/summary")
def get_summary():
    summary_file = PROCESSED_DIR / "weekly_automation_summary.json"
    if not summary_file.exists():
        raise HTTPException(status_code=404, detail="Weekly automation summary not found. Run pipeline first.")
    with open(summary_file, encoding="utf-8") as f:
        data = json.load(f)
    return data


@app.post("/api/run-pipeline")
def trigger_pipeline():
    try:
        from weekly_pipeline import run_weekly_pipeline
        summary = run_weekly_pipeline()
        return {"status": "success", "summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    html_file = project_root / "web" / "index.html"
    if not html_file.exists():
        return "<h1>Dashboard template missing. Please check web/index.html</h1>"
    return html_file.read_text(encoding="utf-8")


if __name__ == "__main__":
    import uvicorn
    print("Starting FPL AI Web Dashboard at http://localhost:8000 ...")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
