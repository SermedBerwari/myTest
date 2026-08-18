import pytest
from scripts.agent.decision_explanation_layer import explain_decision

def decision():
    return {"optimal_squad_ids":list(range(1,16)),"optimal_starting_xi":[{"player_id":1,"web_name":"Captain Candidate"}],"recommended_captain":"Captain Candidate","transfers_count":1,"transfers_in_ids":[20],"transfers_out_ids":[15],"gross_expected_gain":5.0,"hit_penalty_incurred":4.0,"net_expected_gain":1.0}

def test_explanation_is_read_only_and_preserves_evidence():
    d=decision(); evidence={"warnings":["Signal is doubtful."],"uncertainty":["Starting probability is calibrated with limited recent data."],"source":"phase13"}
    out=explain_decision(d,evidence)
    assert out["optimal_squad_ids"]==d["optimal_squad_ids"]
    assert out["net_expected_gain"]==1.0
    assert out["warnings"]==evidence["warnings"]
    assert out["uncertainty"]==evidence["uncertainty"]
    assert out["evidence"]["source"]=="phase13"
    assert "1.00" in out["transfer_recommendation"]

def test_explanation_handles_no_transfer_without_inventing_statistics():
    d=decision(); d.update({"transfers_count":0,"transfers_in_ids":[],"transfers_out_ids":[],"gross_expected_gain":0.0,"hit_penalty_incurred":0.0,"net_expected_gain":0.0})
    out=explain_decision(d,{})
    assert "No transfer" in out["transfer_recommendation"]
    assert "statistics" not in out["transfer_recommendation"].lower()

def test_invalid_captain_and_net_arithmetic_are_rejected():
    d=decision(); d["recommended_captain"]="Not in XI"
    with pytest.raises(ValueError,match="Captain"):
        explain_decision(d)
    d=decision(); d["net_expected_gain"]=99.0
    with pytest.raises(ValueError,match="arithmetic"):
        explain_decision(d)

def test_invalid_transfer_shape_is_rejected():
    d=decision(); d["transfers_count"]=2
    with pytest.raises(ValueError,match="structurally"):
        explain_decision(d)
