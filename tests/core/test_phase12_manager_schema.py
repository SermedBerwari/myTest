import pandas as pd
from scripts.optimizer.manager_engine import recommend_transfers

def make_pool():
    rows=[]
    pid=1
    for pos,n in [(1,3),(2,6),(3,6),(4,4)]:
        for _ in range(n):
            rows.append({"player_id":pid,"web_name":f"P{pid}","position_id":pos,"team_id":pid,"cost":5.0,"expected_points":float(10+(pid-15 if pid>15 else 0)),"availability":"available"})
            pid+=1
    return pd.DataFrame(rows)

def legal_current(pool):
    indexes=[0,1,3,4,5,6,7,9,10,11,12,13,15,16,17]
    return pool.loc[indexes,"player_id"].astype(int).tolist()

def test_manager_returns_hardened_squad_schema():
    pool=make_pool(); current=legal_current(pool)
    result=recommend_transfers(current,pool,free_transfers=1,bank=0.0)
    assert len(result["optimal_squad_ids"])==15
    assert len(result["optimal_starting_xi"])==11
    assert len(result["optimal_bench_ids"])==4
    assert result["recommended_captain"] is not None
    assert result["recommended_vice_captain"] is not None
    assert result["recommended_captain"] != result["recommended_vice_captain"]
    assert sum(int(x["is_captain"]) for x in result["optimal_starting_xi"])==1
    assert sum(int(x["is_vice_captain"]) for x in result["optimal_starting_xi"])==1

def test_manager_net_of_hit_identity_and_transfer_limit():
    pool=make_pool(); current=legal_current(pool)
    result=recommend_transfers(current,pool,free_transfers=1,bank=0.0)
    assert result["free_transfers_used"] <= 1
    assert result["transfers_count"] == len(result["transfers_in_ids"]) == len(result["transfers_out_ids"])
    assert result["hit_penalty_incurred"] == max(0,result["transfers_count"]-result["free_transfers_used"])*4.0
    assert result["net_expected_gain"] == result["gross_expected_gain"]-result["hit_penalty_incurred"]

def test_free_transfer_only_never_exceeds_free_transfers():
    pool=make_pool(); current=legal_current(pool)
    result=recommend_transfers(current,pool,free_transfers=1,bank=0.0,manager_mode="free_transfer_only")
    assert result["transfers_count"] <= 1
    assert result["hit_penalty_incurred"] == 0.0

def test_unavailable_replacements_are_excluded():
    pool=make_pool(); pool.loc[pool.player_id==18,"availability"]="injured"; current=pool.loc[[0,1,3,4,5,6,7,9,10,11,12,13,15,16,18],"player_id"].astype(int).tolist()
    result=recommend_transfers(current,pool,free_transfers=2,bank=0.0)
    assert 18 not in result["transfers_in_ids"]

