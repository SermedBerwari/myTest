"""Read-only, evidence-grounded explanation layer for mathematical FPL decisions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

def _validate_decision(decision: Mapping[str, Any]) -> None:
    if "recommended_captain" in decision and decision.get("recommended_captain") is not None:
        xi=decision.get("optimal_starting_xi",[])
        names={x.get("web_name") for x in xi if isinstance(x,dict)}
        if names and decision["recommended_captain"] not in names: raise ValueError("Captain recommendation is not in the starting XI.")
    count=int(decision.get("transfers_count",0) or 0)
    ins=decision.get("transfers_in_ids",[]) or []
    outs=decision.get("transfers_out_ids",[]) or []
    if count != len(ins) or count != len(outs): raise ValueError("Transfer recommendation is structurally invalid.")
    if float(decision.get("net_expected_gain",0.0) or 0.0) != float(decision.get("gross_expected_gain",0.0) or 0.0)-float(decision.get("hit_penalty_incurred",0.0) or 0.0): raise ValueError("Net-of-hit decision arithmetic is inconsistent.")

def explain_decision(decision: Mapping[str, Any], evidence: Mapping[str, Any] | None=None) -> dict[str, Any]:
    _validate_decision(decision)
    evidence=dict(evidence or {})
    output=deepcopy(dict(decision))
    warnings=list(evidence.get("warnings",[]) or [])
    uncertainty=list(evidence.get("uncertainty",[]) or [])
    output["explanation_contract"]="structured_facts_read_only_v1"
    output["warnings"]=warnings
    output["uncertainty"]=uncertainty
    captain=decision.get("recommended_captain")
    net=float(decision.get("net_expected_gain",0.0) or 0.0)
    count=int(decision.get("transfers_count",0) or 0)
    if count==0: transfer_text="No transfer is recommended because the evaluated net gain does not justify a move."
    elif net>0: transfer_text=f"{count} transfer(s) are recommended because the evaluated net expected gain is {net:.2f} points after hits."
    else: transfer_text=f"No positive net transfer case is established; the evaluated plan would return {net:.2f} points after hits."
    output["squad_summary"]=f"The mathematical optimizer selected {len(decision.get("optimal_squad_ids",[]) or [])} players and {len(decision.get("optimal_starting_xi",[]) or [])} starters."
    output["captain_rationale"]=f"{captain} is the captain because the structured decision output selected that player; the explanation layer does not recompute or alter the ranking." if captain else "No captain was supplied by the mathematical decision layer."
    output["transfer_recommendation"]=transfer_text
    output["evidence"]={k:deepcopy(v) for k,v in evidence.items() if k not in {"warnings","uncertainty"}}
    return output
