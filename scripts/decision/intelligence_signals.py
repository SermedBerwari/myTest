"""Leakage-safe availability and external-intelligence signal normalization."""
from __future__ import annotations

from datetime import datetime, timezone
import pandas as pd

STATUS_PRIORITY={"suspended":4,"injured":3,"doubtful":2,"available":1,"unknown":0}
STATUS_ALIASES={"out":"injured","injury":"injured","injured":"injured","suspended":"suspended","suspension":"suspended","doubtful":"doubtful","flagged":"doubtful","available":"available","fit":"available","ok":"available"}

def normalize_signals(signals: pd.DataFrame, deadline: datetime, max_age_hours: float=72.0) -> pd.DataFrame:
    required={"player_id","status","signal_timestamp","source"}
    missing=required-set(signals.columns)
    if missing: raise ValueError(f"Missing signal columns: {sorted(missing)}")
    if deadline.tzinfo is None: deadline=deadline.replace(tzinfo=timezone.utc)
    out=signals.copy()
    out["signal_timestamp"]=pd.to_datetime(out["signal_timestamp"],utc=True,errors="coerce")
    if out["signal_timestamp"].isna().any(): raise ValueError("Invalid signal_timestamp values.")
    out["status_normalized"]=out["status"].fillna("").astype(str).str.strip().str.lower().map(STATUS_ALIASES).fillna("unknown")
    out["is_post_deadline"]=out["signal_timestamp"]>deadline
    out["signal_age_hours"]=(pd.Timestamp(deadline)-out["signal_timestamp"]).dt.total_seconds()/3600.0
    out["is_stale"]=(out["signal_age_hours"]>float(max_age_hours)) | (out["signal_age_hours"]<0)
    if out["is_post_deadline"].any(): raise ValueError("Post-deadline intelligence signal detected.")
    if out["is_stale"].any(): raise ValueError("Stale intelligence signal detected.")
    out["priority"]=out["status_normalized"].map(STATUS_PRIORITY).fillna(0).astype(int)
    out=out.sort_values(["player_id","priority","signal_timestamp","source"],ascending=[True,False,False,True],kind="mergesort")
    grouped=[]
    for player_id, group in out.groupby("player_id",sort=True):
        top=group.iloc[0].copy()
        statuses=set(group["status_normalized"])
        top["signal_count"]=len(group)
        top["source_count"]=group["source"].nunique()
        top["signal_conflict"]=len(statuses)>1
        grouped.append(top)
    result=pd.DataFrame(grouped).reset_index(drop=True)
    result["availability"]=result["status_normalized"]
    result["signal_policy"]="priority_then_latest"
    return result
