import argparse, json
from pathlib import Path
import pandas as pd
TARGET={"target_gw","target_minutes","target_points","target_goals","target_assists","target_clean_sheets","target_bonus","target_xg","target_xa"}
REQUIRED={"target_gw","feature_cutoff_gw","player_id","gameweek"}
def validate(path):
    d=pd.read_csv(path); e=[]
    miss=REQUIRED-set(d.columns)
    if miss:
        e.append(f"missing required columns: {sorted(miss)}")
        return e
    leaked=[c for c in d.columns if c.startswith("target_") and c not in TARGET]
    if leaked: e.append(f"unexpected target columns: {leaked}")
    if not d.empty and (d["feature_cutoff_gw"]>=d["target_gw"]).any(): e.append("feature cutoff is not strictly before target GW")
    if d[["target_gw","feature_cutoff_gw","player_id"]].isna().any().any(): e.append("required metadata has nulls")
    return e
if __name__=="__main__":
    a=argparse.ArgumentParser(); a.add_argument("csv",type=Path); a.add_argument("--report",type=Path); x=a.parse_args(); e=validate(x.csv); r={"status":"PASS" if not e else "FAILED","errors":e}; print(json.dumps(r,indent=2)); x.report.write_text(json.dumps(r,indent=2)) if x.report else None; raise SystemExit(0 if not e else 2)



