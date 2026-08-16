"""
external_intelligence.py
========================
Pipeline to aggregate live external intelligence signals (Phase 12):
  - Injury & suspension status updates from FPL API
  - Press conference flags & chance of playing
  - News risk signals

Outputs:
  - Cleaned availability matrix for expected-minutes & squad optimizer
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
