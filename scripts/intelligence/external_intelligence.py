"""
external_intelligence.py
========================
Pipeline to aggregate live external intelligence signals (Phase 12):
  - Injury & suspension status updates from FPL API
  - Press conference flags & chance of playing
  - News risk signals

Outputs:
  - Cleaned availability matrix for expected-minutes & squad optimizer

FIX 4 (see FPL_PROJECT_COMPLETION_AND_FIX_PLAN.md):
  Previously these signals were only surfaced as post-hoc warning text in
  the AI report, AFTER the optimizer had already run -- they never actually
  affected which players got selected, captained, or recommended as
  transfers. `apply_availability_adjustment` below closes that gap by
  discounting each player's decision-ready expected_points/expected_minutes
  BEFORE optimization, so an injured/suspended/doubtful player is
  naturally deprioritized by the ILP optimizer, the manager engine's
  transfer-gain calculation, and captaincy selection -- rather than being
  flagged only after the fact.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd


def fetch_availability_signals(project_root: Path) -> pd.DataFrame:
    """
    Extracts injury, suspension, and news availability flags from live FPL bootstrap data.
    """
    bootstrap_dir = project_root / "data" / "raw" / "2026-27" / "bootstrap"
    snapshots = sorted(bootstrap_dir.glob("*.json"))

    if not snapshots:
        # Fallback dummy availability matrix if snapshot missing
        return pd.DataFrame(columns=["player_id", "chance_of_playing_next_round", "status", "news", "news_added"])

    latest = snapshots[-1]
    with open(latest, encoding="utf-8") as f:
        data = json.load(f)

    elements = data.get("elements", [])
    records = []

    for el in elements:
        records.append({
            "player_id": el.get("id"),
            "web_name": el.get("web_name"),
            "status": el.get("status"),  # 'a' = available, 'd' = doubtful, 'i' = injured, 's' = suspended
            "chance_of_playing_next_round": el.get("chance_of_playing_next_round"),  # 0, 25, 50, 75, 100, or None
            "news": el.get("news", ""),
            "news_added": el.get("news_added"),
        })

    return pd.DataFrame(records)


def apply_availability_adjustment(pool: pd.DataFrame, signals: pd.DataFrame) -> pd.DataFrame:
    """
    Merge external intelligence signals onto the scored player pool and
    discount expected_points / expected_minutes to reflect real
    availability risk, BEFORE the optimizer/manager engine run.

    Rule:
      - chance_of_playing_next_round, when present, is used directly as a
        [0, 1] multiplier (e.g. 75 -> 0.75).
      - status 'i' (injured) or 's' (suspended) with no chance figure is
        treated as chance=0 (unavailable) -- NOT dropped from the pool,
        since the manager engine still needs to value the actual current
        squad accurately, including an injured player already owned.
      - status 'd' (doubtful) with no chance figure defaults to a
        conservative 0.5 multiplier.
      - status 'a' (available) with no flag: no discount (multiplier 1.0).

    Adds columns: availability_multiplier, availability_status,
    availability_news, and overwrites expected_points / expected_minutes
    with the discounted values so every downstream consumer (optimizer,
    manager engine, captaincy selection) sees the adjusted figures.
    """
    if signals is None or signals.empty:
        pool = pool.copy()
        pool["availability_multiplier"] = 1.0
        pool["availability_status"] = "a"
        pool["availability_news"] = ""
        return pool

    pool = pool.merge(
        signals[["player_id", "status", "chance_of_playing_next_round", "news"]],
        on="player_id",
        how="left",
        suffixes=("", "_signal"),
    )

    def _multiplier(row) -> float:
        chance = row.get("chance_of_playing_next_round")
        status = row.get("status")
        if pd.notna(chance):
            return max(0.0, min(1.0, float(chance) / 100.0))
        if status in ("i", "s", "u"):
            return 0.0
        if status == "d":
            return 0.5
        return 1.0

    pool["availability_multiplier"] = pool.apply(_multiplier, axis=1)
    pool["availability_status"] = pool["status"].fillna("a")
    pool["availability_news"] = pool["news"].fillna("")

    pool["expected_points"] = pool["expected_points"] * pool["availability_multiplier"]
    if "expected_minutes" in pool.columns:
        pool["expected_minutes"] = pool["expected_minutes"] * pool["availability_multiplier"]

    return pool


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    print("=" * 72)
    print("EXTERNAL INTELLIGENCE PIPELINE (PHASE 12)")
    print("=" * 72)

    df_signals = fetch_availability_signals(project_root)

    print(f"Loaded availability signals for {len(df_signals)} players.")

    if not df_signals.empty and "status" in df_signals.columns:
        status_counts = df_signals["status"].value_counts().to_dict()
        print(f"Status distribution: {status_counts}")

        flagged = df_signals[df_signals["status"] != "a"]
        print(f"Flagged players (injured/suspended/doubtful): {len(flagged)}")

    output_path = project_root / "data" / "processed" / "external_intelligence_signals.json"
    df_signals.to_json(output_path, orient="records", indent=2)

    print(f"\nSaved external intelligence signals to: {output_path}")
    print("=" * 72)


if __name__ == "__main__":
    main()
