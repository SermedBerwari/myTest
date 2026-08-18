import json
from pathlib import Path
import statistics
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
INPUT=ROOT/"data/processed/historical_manager_simulation.json"
OUT=ROOT/"data/processed/phase16_manager_comparison.json"
CSV=ROOT/"data/processed/phase16_manager_comparison.csv"
HIT=4.0
REQUIRED={"no_transfer","previous_gw","rolling_average","historical_average_xp","ridge_xp","ml_plus_minutes","ml_plus_availability","simple_highest_xp","ai_manager"}

def summarize(name,season,x):
    points=[float(g["points"]) for g in (x.get("gw_log") or [])]
    hits=int(x.get("hits",0)); actual=float(x.get("season_actual_points",sum(points)))
    return {"season":season,"strategy":name,"weeks":int(x.get("weeks",len(points))),"total_points":actual,"net_points_after_hits":actual-HIT*hits,"average_gw_points":statistics.mean(points) if points else 0.0,"median_gw_points":statistics.median(points) if points else 0.0,"transfers":int(x.get("transfers",0)),"hits":hits,"hit_points_lost":HIT*hits,"bench_points_wasted":float(x.get("bench_points_wasted",0.0)),"forced_replacements":int(x.get("forced_replacements",0)),"captain_points":float(x.get("captain_points",0.0)),"vice_captain_points":float(x.get("vice_captain_points",0.0))}

def main():
    raw=json.loads(INPUT.read_text(encoding="utf-8"))
    rows=[]; missing={}
    for season, payload in raw.items():
        strategies=payload.get("strategies",{})
        missing[season]=sorted(REQUIRED-set(strategies))
        for name,x in strategies.items(): rows.append(summarize(name,season,x))
    if any(missing.values()): raise RuntimeError(f"Missing required baseline strategies: {missing}")
    frame=pd.DataFrame(rows).sort_values(["strategy","season"])
    agg=[]
    for name,g in frame.groupby("strategy",sort=True):
        agg.append({"strategy":name,"seasons":int(g.season.nunique()),"total_points":float(g.total_points.sum()),"total_net_points_after_hits":float(g.net_points_after_hits.sum()),"mean_season_net_points":float(g.net_points_after_hits.mean()),"median_season_net_points":float(g.net_points_after_hits.median()),"mean_gw_points":float(g.average_gw_points.mean()),"total_transfers":int(g.transfers.sum()),"total_hits":int(g.hits.sum()),"total_hit_points_lost":float(g.hit_points_lost.sum()),"total_bench_points_wasted":float(g.bench_points_wasted.sum()),"season_net_point_range":float(g.net_points_after_hits.max()-g.net_points_after_hits.min())})
    gw_rows=[]
    for season,payload in raw.items():
        for name,x in payload.get("strategies",{}).items():
            for g in x.get("gw_log",[]): gw_rows.append({"season":season,"strategy":name,"gameweek":int(g["gw"]),"actual_points":float(g["points"])})
    result={"schema_version":"phase16-v1.0.0","hit_penalty":HIT,"source":str(INPUT),"seasons":sorted(raw),"strategies":sorted(frame.strategy.unique()),"season_results":frame.to_dict(orient="records"),"strategy_summary":agg,"gameweek_results":gw_rows,"data_quality_notes":["Captain and vice-captain totals are persisted from the predicted starting XI and actual historical outcomes.","Actual points are sourced from historical target outcomes; decisions are sourced from the simulator predictions."]}
    OUT.write_text(json.dumps(result,indent=2),encoding="utf-8"); frame.to_csv(CSV,index=False); print(f"WROTE {OUT}"); print(frame[["season","strategy","net_points_after_hits","transfers","hits"]].to_string(index=False))
if __name__=="__main__": main()



