import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
d=json.loads((ROOT/"data/processed/phase16_manager_comparison.json").read_text(encoding="utf-8"))
required={"historical_average_xp","ridge_xp","ml_plus_minutes","ml_plus_availability"}
assert required.issubset(set(d["strategies"]))
assert len(d["seasons"])==3
assert len(d["gameweek_results"])>0
for r in d["season_results"]:
    assert r["captain_points"] is not None and r["vice_captain_points"] is not None
    assert r["net_points_after_hits"] == r["total_points"] - 4.0*r["hits"]
    assert r["transfers"] >= r["hits"]
for s in d["strategy_summary"]:
    assert s["seasons"]==3
print("PASS Phase 16 full-loop variants and captain/vice persistence")
