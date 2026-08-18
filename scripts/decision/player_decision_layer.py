"""Authoritative xP ranking and player-decision layer for Phase 10."""
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd

AVAILABILITY_FACTORS={"available":1.0,"":1.0,"doubtful":0.5,"injured":0.0,"suspended":0.0,"out":0.0}

def _fixture_factor(series: pd.Series) -> pd.Series:
    difficulty=pd.to_numeric(series,errors="coerce").fillna(3.0).clip(1.0,5.0)
    return (1.0+(3.0-difficulty)*0.03).clip(0.90,1.06)

def rank_players(pool: pd.DataFrame) -> pd.DataFrame:
    required={"player_id","expected_points","expected_minutes","start_probability"}
    missing=required-set(pool.columns)
    if missing: raise ValueError(f"Missing decision-layer columns: {sorted(missing)}")
    out=pool.copy()
    out["expected_points"]=pd.to_numeric(out["expected_points"],errors="coerce").fillna(0.0).clip(lower=0.0)
    out["expected_minutes"]=pd.to_numeric(out["expected_minutes"],errors="coerce").fillna(0.0).clip(0.0,90.0)
    out["start_probability"]=pd.to_numeric(out["start_probability"],errors="coerce").fillna(0.0).clip(0.0,1.0)
    if "fixture_difficulty" in out: out["fixture_factor"]=_fixture_factor(out["fixture_difficulty"])
    else: out["fixture_factor"]=1.0
    if "status" in out: out["availability_factor"]=out["status"].fillna("").astype(str).str.lower().map(AVAILABILITY_FACTORS).fillna(0.0)
    else: out["availability_factor"]=1.0
    out["decision_score"]=out["expected_points"]*out["fixture_factor"]*out["availability_factor"]
    out["captain_score"]=out["decision_score"]*out["start_probability"]
    out=out.sort_values(["decision_score","player_id"],ascending=[False,True],kind="mergesort").reset_index(drop=True)
    out["decision_rank"]=out.index+1
    out["position_rank"]=out.groupby("position_name",dropna=False)["decision_score"].rank(method="first",ascending=False).astype("Int64") if "position_name" in out else pd.Series(range(1,len(out)+1),index=out.index,dtype="Int64")
    out["captain_rank"]=out["captain_score"].rank(method="first",ascending=False).astype("Int64")
    return out

def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    ranked=rank_players(pd.read_csv(args.input))
    ranked.to_csv(args.output,index=False)
    print(args.output)

if __name__=="__main__": main()
