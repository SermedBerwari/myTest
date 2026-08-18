from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return "sha256:"+h.hexdigest()

def main()->int:
    parser=argparse.ArgumentParser(description="Validate the 2026-27 live-season GW1 integration.")
    parser.add_argument("--season",default="2026-27")
    parser.add_argument("--gameweek",type=int,default=1)
    parser.add_argument("--project-root",default=".")
    args=parser.parse_args()
    root=Path(args.project_root).resolve(); season=args.season; gw=args.gameweek
    processed=root/"data/processed"/season; features=root/"data/features"/season
    errors=[]; checks={}

    def check(name,ok,detail):
        checks[name]={"status":"PASS" if ok else "FAIL","detail":detail}
        if not ok: errors.append(f"{name}: {detail}")

    required=[processed/"players.csv",processed/"fixtures.csv",processed/"gameweeks.csv",processed/"player_gameweek.csv",processed/"player_season_history.csv",features/"player_gameweek_features.csv",features/"feature_manifest.json",root/"data/processed/weekly_automation_summary.json"]
    check("required_snapshots",all(p.exists() for p in required),[str(p.relative_to(root)) for p in required if not p.exists()])
    players=pd.read_csv(processed/"players.csv") if (processed/"players.csv").exists() else pd.DataFrame()
    fixtures=pd.read_csv(processed/"fixtures.csv") if (processed/"fixtures.csv").exists() else pd.DataFrame()
    feature_path=features/"player_gameweek_features.csv"
    feature=pd.read_csv(feature_path) if feature_path.exists() else pd.DataFrame()
    check("complete_player_pool",len(players)>=500 and players.player_id.nunique()==len(players),f"rows={len(players)}, unique_ids={players.player_id.nunique() if not players.empty else 0}")
    check("current_ids",not players.empty and players.player_id.notna().all() and (players.player_id.astype(int)>0).all(),"all player IDs are positive and non-null")
    check("current_prices",not players.empty and players.now_cost_m.notna().all() and (players.now_cost_m.astype(float)>0).all(),"all players have positive current prices")
    check("availability_data",not players.empty and ("status" in players.columns or "availability" in players.columns),"availability/status column exists")
    check("fixture_snapshot",len(fixtures)>=300 and ("event" in fixtures.columns or "gameweek" in fixtures.columns),"fixture rows and gameweek field present")
    cold=(not feature.empty and "gameweek" in feature.columns and "prior_gameweeks" in feature.columns and ((feature.gameweek==gw)&(feature.prior_gameweeks==0)).any())
    check("cold_start",cold,"GW1 contains explicit zero-history rows")
    leakage=(not feature.empty and "target_points" not in [c for c in feature.columns if c.startswith("prior_")])
    check("feature_target_separation",leakage,"target is not represented as a prior feature")
    summary_path=root/"data/processed/weekly_automation_summary.json"
    summary=json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    check("official_gw1_recommendation",summary.get("target_season")==season and summary.get("target_gameweek")==gw,"weekly summary targets 2026-27 GW1")
    optimal=summary.get("optimal_squad",{}); start=optimal.get("starting_xi",[]) if isinstance(optimal,dict) else [] ; bench=optimal.get("bench",[]) if isinstance(optimal,dict) else []
    ids=[int(x.get("player_id")) for x in start+bench if isinstance(x,dict) and x.get("player_id") is not None]
    check("recommendation_legality",len(start)==11 and len(bench)==4 and len(ids)==15 and len(set(ids))==15 and float(optimal.get("total_cost",101))<=100,"11 starters, 4 bench, unique IDs, budget <= 100")
    captain=optimal.get("captain") if isinstance(optimal,dict) else None
    check("captain_present",bool(captain) and any(x.get("web_name")==captain for x in start if isinstance(x,dict)),"captain is selected from starting XI")
    report={"status":"PASS" if not errors else "FAIL","validated_at_utc":datetime.now(timezone.utc).isoformat(),"season":season,"gameweek":gw,"checks":checks,"source_hashes":{str(p.relative_to(root)):sha256(p) for p in required if p.exists()}}
    out=root/"data/processed/phase23_live_integration_report.json"; out.write_text(json.dumps(report,indent=2),encoding="utf-8")
    for name,result in checks.items(): print(result["status"], name, ":", result["detail"])
    print(f"REPORT={out.relative_to(root)}")
    return 1 if errors else 0

if __name__=="__main__": raise SystemExit(main())


