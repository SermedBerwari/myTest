"""Canonical, validated weekly FPL automation command (Phase 15)."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def _sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat()

def _lineage(root: Path) -> dict[str,Any]:
    paths=[root/"data/processed/training_dataset_v1_manifest.json",root/"data/processed/model_registry.json",root/"data/processed/canonical_feature_path_report.json"]
    files=[]
    for path in paths:
        if path.exists(): files.append({"path":str(path.relative_to(root)),"sha256":_sha256(path)})
    model_version="unknown"
    registry=root/"data/processed/model_registry.json"
    if registry.exists():
        data=json.loads(registry.read_text(encoding="utf-8"))
        model_version=str(data.get("production_model",data.get("official_model",data.get("version","unknown"))))
    feature_version="unknown"
    manifest=root/"data/processed/training_dataset_v1_manifest.json"
    if manifest.exists(): feature_version=str(json.loads(manifest.read_text(encoding="utf-8")).get("version","unknown"))
    return {"model_version":model_version,"feature_version":feature_version,"input_files":files}

def _validate_summary(summary: dict[str,Any]) -> None:
    required={"target_season","target_gameweek","real_squad_player_ids","optimal_squad","manager_recommendations","ai_report"}
    missing=required-set(summary)
    if missing: raise ValueError(f"Weekly output missing required fields: {sorted(missing)}")
    squad=summary["optimal_squad"]
    if len(squad.get("starting_xi",[]))+len(squad.get("bench",[])) != 15: raise ValueError("Invalid weekly output: optimal squad is not exactly 15 players.")
    manager=summary["manager_recommendations"]
    gross=float(manager.get("gross_expected_gain",0.0) or 0.0)
    hit=float(manager.get("hit_penalty_incurred",0.0) or 0.0)
    net=float(manager.get("net_expected_gain",0.0) or 0.0)
    if abs((gross-hit)-net)>1e-9: raise ValueError("Invalid weekly output: net-of-hit arithmetic failed.")
    if len(set(summary["real_squad_player_ids"])) != 15: raise ValueError("Invalid weekly output: current squad must contain 15 unique players.")

def run_canonical_weekly(season: str="2026-27", target_gw: int=1, squad_path: Path|None=None, root: Path|None=None) -> dict[str,Any]:
    root=Path(root or Path(__file__).resolve().parents[1])
    processed=root/"data/processed"
    sys.path.insert(0,str(root))
    processed.mkdir(parents=True,exist_ok=True)
    run_id=f"weekly-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}-{uuid.uuid4().hex[:8]}"
    started=_stamp(); lineage=_lineage(root); stages=[]
    try:
        stages.append({"stage":"input_lineage","status":"PASS"})
        from scripts.weekly_pipeline import run_weekly_pipeline
        stages.append({"stage":"pipeline_execution","status":"RUNNING"})
        summary=run_weekly_pipeline(season=season,target_gw=target_gw,squad_path=squad_path)
        stages[-1]["status"]="PASS"
        stages.append({"stage":"output_validation","status":"RUNNING"})
        _validate_summary(summary)
        stages[-1]["status"]="PASS"
        summary["pipeline_metadata"]={"run_id":run_id,"started_at_utc":started,"completed_at_utc":_stamp(),"model_version":lineage["model_version"],"feature_version":lineage["feature_version"],"protocol":"canonical_weekly_v1"}
        out=root/"data/processed/weekly_automation_summary_canonical.json"
        out.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        manifest={"run_id":run_id,"status":"PASS","started_at_utc":started,"completed_at_utc":_stamp(),"season":season,"target_gw":target_gw,"model_version":lineage["model_version"],"feature_version":lineage["feature_version"],"stages":stages,"inputs":lineage["input_files"],"outputs":[{"path":str(out.relative_to(root)),"sha256":_sha256(out)}]}
        (root/"data/processed/weekly_automation_output_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
        return manifest
    except Exception as exc:
        stages.append({"stage":"failure","status":"FAIL","error":f"{type(exc).__name__}: {exc}"})
        fail={"run_id":run_id,"status":"FAIL","started_at_utc":started,"failed_at_utc":_stamp(),"season":season,"target_gw":target_gw,"stages":stages,"inputs":lineage["input_files"]}
        (root/"data/processed/weekly_automation_output_manifest.json").write_text(json.dumps(fail,indent=2)+"\n",encoding="utf-8")
        raise

def main() -> int:
    parser=argparse.ArgumentParser(description="Run the canonical validated FPL weekly pipeline.")
    parser.add_argument("--season",default="2026-27")
    parser.add_argument("--gw",type=int,default=1)
    parser.add_argument("--squad",type=Path,default=None)
    args=parser.parse_args()
    run_canonical_weekly(args.season,args.gw,args.squad)
    return 0

if __name__=="__main__": sys.exit(main())
