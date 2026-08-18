import json
from pathlib import Path
import pandas as pd
import pytest

from scripts.decision.official_xp import compute_official_xp, rank_players
from scripts.optimizer.squad_optimizer import optimize_squad, select_starting_xi
from scripts.optimizer.manager_engine import recommend_transfers

def make_pool():
    rows=[]; pid=1
    for pos,n in [(1,2),(2,5),(3,5),(4,3)]:
        for _ in range(n):
            rows.append({"player_id":pid,"web_name":f"P{pid}","position_id":pos,"team_id":(pid-1)%5+1,"cost":5.0,"expected_points":10.0,"raw_points":10.0,"expected_minutes":90.0,"start_probability":1.0,"fixture_difficulty":3,"availability":"available"}); pid+=1
    for pos in [1,2,3,4]:
        rows.append({"player_id":pid,"web_name":f"P{pid}","position_id":pos,"team_id":6,"cost":5.0,"expected_points":12.0,"raw_points":12.0,"expected_minutes":90.0,"start_probability":1.0,"fixture_difficulty":3,"availability":"available"}); pid+=1
    return pd.DataFrame(rows)

def test_official_xp_adjustments_and_determinism():
    d=make_pool().iloc[:4].copy()
    out1=rank_players(compute_official_xp(d))
    out2=rank_players(compute_official_xp(d))
    pd.testing.assert_frame_equal(out1,out2)
    assert out1.iloc[0].official_xp >= out1.iloc[-1].official_xp
    injured=d.copy(); injured.loc[injured.index[0],"availability"]="injured"
    assert compute_official_xp(injured).iloc[0].official_xp == 0

def test_optimizer_legal_squad_and_captain():
    d=make_pool().iloc[:15].copy()
    picked=optimize_squad(d,budget=100.0)
    assert len(picked["starting_xi"])+len(picked["bench"]) == 15
    assert picked["captain"] in [x["web_name"] for x in picked["starting_xi"]]
    xi=select_starting_xi(d)
    assert len(xi["starting_ids"]) == 11
    assert xi["captain_id"] in xi["starting_ids"]

def test_manager_net_hit_free_transfers_and_unavailability():
    d=make_pool(); current=d.player_id.iloc[:15].astype(int).tolist()
    r=recommend_transfers(current,d,free_transfers=2,bank=0.0)
    assert r["free_transfers_used"] <= 2
    assert r["hit_penalty_incurred"] == 0
    unavailable=d.copy(); unavailable.loc[unavailable.player_id==16,"availability"]="injured"
    r2=recommend_transfers(current,unavailable,free_transfers=2,bank=0.0)
    assert 16 not in r2["transfers_in_ids"]
    bad=d.copy(); bad.loc[bad.player_id==1,"availability"]="suspended"
    with pytest.raises(ValueError,match="unavailable"):
        recommend_transfers(current,bad)
    with pytest.raises(ValueError,match="Unsupported"):
        recommend_transfers(current,d,manager_mode="wildcard")

def test_leakage_report_passes():
    p=Path("data/processed/feature_leakage_report.json")
    if not p.exists(): pytest.skip("feature leakage artifact not generated")
    d=json.loads(p.read_text(encoding="utf-8"))
    assert d.get("status") == "PASS"


