import json
from pathlib import Path

p=Path("data/processed/phase16_manager_comparison.json")
d=json.loads(p.read_text(encoding="utf-8"))
required={"no_transfer","previous_gw","rolling_average","simple_highest_xp","ai_manager"}
assert required.issubset(set(d["strategies"]))
assert len(d["seasons"])>=3
assert d["gameweek_results"]
for r in d["season_results"]:
    assert r["net_points_after_hits"] == r["total_points"] - 4.0*r["hits"]
    assert r["transfers"] >= r["hits"]
for s in d["strategy_summary"]:
    assert s["seasons"] >= 3
print("PASS Phase 16 strategy coverage, net points, season, and GW metrics")
