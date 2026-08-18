"""Authoritative decision-ready FPL expected-points and ranking layer."""
from __future__ import annotations
from pathlib import Path
import json
import pandas as pd

FORMULA_VERSION="xp-v1.0.0"
FDR_MIN=1
FDR_MAX=5

def availability_multiplier(value):
    s=str(value or "available").lower().strip()
    if s in {"unavailable","injured","suspended","out"}: return 0.0
    if s in {"doubtful","questionable","late fitness"}: return 0.5
    return 1.0

def fixture_multiplier(fdr):
    x=pd.to_numeric(fdr,errors="coerce").fillna(3).clip(FDR_MIN,FDR_MAX)
    return (1.0+0.04*(3.0-x)).clip(0.85,1.15)

def compute_official_xp(pool: pd.DataFrame) -> pd.DataFrame:
    d=pool.copy()
    raw=pd.to_numeric(d["raw_points"] if "raw_points" in d else (d["model_xp"] if "model_xp" in d else pd.Series(0,index=d.index)),errors="coerce").fillna(0.0).clip(lower=0.0)
    recent=pd.to_numeric(d["minutes_per_appearance_last_5"] if "minutes_per_appearance_last_5" in d else pd.Series(90,index=d.index),errors="coerce").fillna(90).clip(lower=1.0,upper=90.0)
    implied90=raw/(recent/90.0)
    mins=pd.to_numeric(d.get("expected_minutes",recent),errors="coerce").fillna(recent).clip(0,90)
    start=pd.to_numeric(d.get("start_probability",(mins>=60).astype(float)),errors="coerce").fillna(0.0).clip(0,1)
    effective=(0.7*mins+0.3*90.0*start).clip(0,90)
    avail=d.get("availability",pd.Series("available",index=d.index)).map(availability_multiplier)
    fdr=fixture_multiplier(d.get("fixture_difficulty",pd.Series(3,index=d.index)))
    d["xp_formula_version"]=FORMULA_VERSION
    d["implied_points_per_90"]=implied90
    d["effective_minutes"]=effective
    d["availability_multiplier"]=avail
    d["fixture_multiplier"]=fdr
    d["official_xp"]=(implied90*(effective/90.0)*avail*fdr).clip(lower=0.0)
    d["expected_points"]=d["official_xp"]
    return d

def rank_players(pool: pd.DataFrame) -> pd.DataFrame:
    d=compute_official_xp(pool)
    keys=["official_xp","player_id"] if "player_id" in d else ["official_xp"]
    d=d.sort_values(keys,ascending=[False]*len(keys),kind="mergesort").reset_index(drop=True)
    d["overall_rank"]=d.index+1
    if "position_id" in d: d["position_rank"]=d.groupby("position_id",sort=False)["official_xp"].rank(method="first",ascending=False).astype(int)
    return d

def validate_ranking(d: pd.DataFrame):
    required={"official_xp","overall_rank","xp_formula_version"}
    missing=required-set(d.columns)
    errors=[]
    if missing: errors.append(f"missing columns: {sorted(missing)}")
    if not d.empty and (d["official_xp"].isna() | (d["official_xp"]<0)).any(): errors.append("invalid official_xp values")
    if not d.empty and d["overall_rank"].tolist()!=list(range(1,len(d)+1)): errors.append("overall ranks are not contiguous")
    return errors

def write_formula_document(path: Path):
    payload={"formula_version":FORMULA_VERSION,"formula":"official_xp = (raw_points / (recent_minutes_per_appearance / 90)) * (0.7*expected_minutes + 0.3*90*start_probability) / 90 * availability_multiplier * fixture_multiplier","fixture_multiplier":"clip(1 + 0.04*(3 - fixture_difficulty), 0.85, 1.15)","availability":{"available":1.0,"doubtful":0.5,"injured":0.0,"suspended":0.0},"ranking":"descending official_xp; stable player_id tie-break; overall and position ranks"}; path.write_text(json.dumps(payload,indent=2),encoding="utf-8")
