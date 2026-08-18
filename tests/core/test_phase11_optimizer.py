import pandas as pd
import pytest
from scripts.optimizer.squad_optimizer import optimize_squad

def pool():
    rows=[]
    specs=[(1,2),(2,5),(3,5),(4,3)]
    pid=1
    for pos,count in specs:
        for j in range(count):
            rows.append({"player_id":pid,"web_name":f"P{pid}","position_id":pos,"team_id":((pid-1)%6)+1,"cost":5.0,"expected_points":float(20-pid)})
            pid+=1
    return pd.DataFrame(rows)

def test_optimizer_returns_legal_squad_and_starting_xi():
    result=optimize_squad(pool(),budget=100.0,max_per_team=3)
    squad=pd.concat([pd.DataFrame(result["starting_xi"]),pd.DataFrame(result["bench"])],ignore_index=True)
    assert len(squad)==15
    assert squad["position_id"].value_counts().to_dict()=={1:2,2:5,3:5,4:3}
    assert squad["team_id"].value_counts().max()<=3
    assert result["total_cost"]<=100.0
    assert len(result["starting_xi"])==11
    assert result["captain"] in {p["web_name"] for p in result["starting_xi"]}
    assert result["vice_captain"] in {p["web_name"] for p in result["starting_xi"]}
    assert result["captain"] != result["vice_captain"]

def test_optimizer_is_deterministic_on_equal_expected_points():
    p=pool(); p["expected_points"]=10.0
    a=optimize_squad(p); b=optimize_squad(p)
    assert a["starting_ids"]+a["bench_ids"]==b["starting_ids"]+b["bench_ids"]
    assert [x["player_id"] for x in a["starting_xi"]]==[x["player_id"] for x in b["starting_xi"]]
    assert a["captain"]==b["captain"]
    assert a["vice_captain"]==b["vice_captain"]

@pytest.mark.parametrize("mutator",[
    lambda df: df.iloc[:14].copy(),
    lambda df: df.assign(player_id=lambda x: x["player_id"].mask(x.index==1,1)),
    lambda df: df.assign(position_id=lambda x: x["position_id"].mask(x.index==0,9)),
    lambda df: df.assign(team_id=lambda x: x["team_id"].mask(x.index==0,0)),
    lambda df: df.assign(cost=lambda x: x["cost"].mask(x.index==0,-1)),
])
def test_optimizer_rejects_invalid_pools(mutator):
    with pytest.raises(ValueError):
        optimize_squad(mutator(pool()))

def test_optimizer_rejects_infeasible_budget():
    with pytest.raises((RuntimeError,ValueError)):
        optimize_squad(pool(),budget=10.0)




def test_double_and_blank_gameweek_metadata_do_not_break_selection():
    p=pool().assign(target_gw=[2,2,2,2,2,2,2,2,2,2,2,2,2,2,2],fixture_id=list(range(15)))
    p.loc[0,"target_gw"]=3
    result=optimize_squad(p)
    assert len(result["starting_xi"])+len(result["bench"])==15

def test_unavailable_player_with_zero_xp_is_not_captain():
    p=pool(); p.loc[0,"expected_points"]=0.0
    result=optimize_squad(p)
    assert result["captain"] != "P1"
    assert result["vice_captain"] != "P1"

def test_budget_boundary_at_exact_total_cost_is_feasible():
    result=optimize_squad(pool(),budget=75.0)
    assert result["total_cost"]==75.0
