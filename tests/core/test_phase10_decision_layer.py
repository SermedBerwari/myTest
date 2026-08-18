import pandas as pd
import pytest
from scripts.decision.player_decision_layer import rank_players

def _pool():
    return pd.DataFrame({"player_id":[3,1,2,4],"position_name":["MID","MID","FWD","DEF"],"expected_points":[10.0,10.0,8.0,12.0],"expected_minutes":[90,90,45,90],"start_probability":[0.9,0.8,0.9,0.9],"fixture_difficulty":[3,5,1,3],"status":["available","available","doubtful","injured"]})

def test_decision_layer_applies_fixture_and_availability_adjustments():
    out=rank_players(_pool())
    row=out.set_index("player_id")
    assert row.loc[3,"decision_score"]==10.0
    assert row.loc[1,"decision_score"]<10.0
    assert 0.0 < row.loc[2,"decision_score"] < 8.0
    assert row.loc[4,"decision_score"]==0.0
    assert row.loc[4,"captain_score"]==0.0

def test_ranking_is_stable_and_position_specific():
    out=rank_players(_pool())
    assert out["player_id"].tolist()==[3,1,2,4]
    assert out.loc[out["player_id"]==3,"position_rank"].iloc[0]==1
    assert out.loc[out["player_id"]==1,"position_rank"].iloc[0]==2
    assert out["decision_rank"].is_unique
    assert out["captain_rank"].is_unique

def test_missing_contract_columns_fail_loudly():
    with pytest.raises(ValueError,match="Missing decision-layer columns"):
        rank_players(pd.DataFrame({"player_id":[1],"expected_points":[1.0]}))

