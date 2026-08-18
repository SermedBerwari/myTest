"""
ai_decision_agent.py
====================
AI Decision Agent & Explanation Layer (Phase 13).

Consumes structured predictions, optimizer outputs, and injury intelligence
to generate transparent, natural language rationale for squad decisions.

Guardrails:
  - Never overrides ILP budget or team rules
  - Distinguishes factual historical data from model predictions
"""

from __future__ import annotations
import argparse
import argparse

import argparse
import json
from pathlib import Path


def generate_weekly_report(
    optimizer_output: dict,
    manager_output: dict,
    intelligence_signals: list[dict]
) -> dict:
    """
    Generates structured AI explanation report for weekly squad selection and transfers.
    """
    starting_xi = optimizer_output.get("starting_xi", [])
    bench = optimizer_output.get("bench", [])
    captain = optimizer_output.get("captain")
    total_cost = optimizer_output.get("total_cost", 0.0)
    expected_pts = optimizer_output.get("expected_points", 0.0)

    # Flagged players in starting XI check
    flagged_ids = {p["player_id"]: p for p in intelligence_signals if p.get("status") != "a"}
    flagged_starters = [p for p in starting_xi if p["player_id"] in flagged_ids]

    # Transfer rationale
    net_xp = manager_output.get("net_expected_gain", 0.0)
    transfers_cnt = manager_output.get("transfers_count", 0)
    transfers_summary = (
        f"Recommend making {transfers_cnt} transfer(s) for a net expected gain of +{net_xp:.2f} pts."
        if net_xp > 0 else
        f"Recommend rolling transfer (0 transfers). Net gain (+{net_xp:.2f} pts) does not justify hit cost."
    )

    # Captain rationale
    captain_xp = next((p["expected_points"] for p in starting_xi if p["web_name"] == captain), 0.0)
    captain_rationale = f"Captain {captain} selected due to highest projected points ({captain_xp:.2f} xP)."

    narrative = {
        "title": "FPL AI Weekly Decision Report",
        "squad_summary": f"Targeting optimal 15-player squad costing £{total_cost:.1f}M with {expected_pts:.2f} expected points.",
        "captain_rationale": captain_rationale,
        "transfer_recommendation": transfers_summary,
        "availability_warnings": [
            f"WARNING: {p['web_name']} is flagged ({flagged_ids[p['player_id']].get('news', 'Unknown status')})"
            for p in flagged_starters
        ]
    }

    return narrative


def main() -> None:
    parser = argparse.ArgumentParser(description='Run ai_decision_agent.py.')
    parser.parse_args()
    project_root = Path(__file__).resolve().parents[2]

    print("=" * 72)
    print("AI DECISION AGENT REPORT GENERATION (PHASE 13)")
    print("=" * 72)

    optimizer_path = project_root / "data" / "processed" / "optimal_squad_sample.json"
    manager_path = project_root / "data" / "processed" / "manager_engine_sample.json"
    intelligence_path = project_root / "data" / "processed" / "external_intelligence_signals.json"

    with open(optimizer_path, encoding="utf-8") as f:
        opt_data = json.load(f)
    with open(manager_path, encoding="utf-8") as f:
        mgr_data = json.load(f)
    with open(intelligence_path, encoding="utf-8") as f:
        intel_data = json.load(f)

    report = generate_weekly_report(opt_data, mgr_data, intel_data)

    print(f"\n{report['title']}")
    print("-" * 72)
    print(f"Squad Summary          : {report['squad_summary']}")
    print(f"Captain Rationale      : {report['captain_rationale']}")
    print(f"Transfer Recommendation: {report['transfer_recommendation']}")
    if report["availability_warnings"]:
        print("Availability Warnings  :")
        for w in report["availability_warnings"]:
            print(f"  - {w}")
    else:
        print("Availability Warnings  : None in Starting XI.")

    output_path = project_root / "data" / "processed" / "ai_decision_report.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\nSaved decision report to: {output_path}")
    print("=" * 72)


if __name__ == "__main__":
    main()


