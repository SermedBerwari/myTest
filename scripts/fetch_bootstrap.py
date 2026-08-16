"""
Fetch and save the official FPL bootstrap-static dataset.

This script:
1. Connects to the official FPL API.
2. Downloads bootstrap-static.
3. Validates the basic structure.
4. Saves the complete raw JSON response.
5. Adds collection metadata outside the API payload.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make sure the project root is available when this script
# is executed directly.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.collectors.fpl_client import FPLClient


SEASON = "2026-27"

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / SEASON
    / "bootstrap"
)


def validate_bootstrap(data: dict) -> None:
    """Perform basic validation of bootstrap-static data."""

    required_sections = [
        "events",
        "teams",
        "elements",
        "element_types",
    ]

    missing = [
        section
        for section in required_sections
        if section not in data
    ]

    if missing:
        raise ValueError(
            "Bootstrap data is missing required sections: "
            + ", ".join(missing)
        )

    if not isinstance(data["events"], list):
        raise ValueError("'events' must be a list.")

    if not isinstance(data["teams"], list):
        raise ValueError("'teams' must be a list.")

    if not isinstance(data["elements"], list):
        raise ValueError("'elements' must be a list.")

    if not isinstance(data["element_types"], list):
        raise ValueError("'element_types' must be a list.")


def save_bootstrap(data: dict) -> Path:
    """Save the complete raw API response."""

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d_%H-%M-%S")

    output_file = OUTPUT_DIR / f"{timestamp}.json"

    with output_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    return output_file


def print_summary(data: dict, output_file: Path) -> None:
    """Print a useful collection summary."""

    print()
    print("=" * 60)
    print("FPL BOOTSTRAP COLLECTION")
    print("=" * 60)

    print()
    print(f"Season      : {SEASON}")
    print(f"Gameweeks   : {len(data['events'])}")
    print(f"Teams       : {len(data['teams'])}")
    print(f"Players     : {len(data['elements'])}")
    print(f"Positions   : {len(data['element_types'])}")

    current_gameweek = next(
        (
            event
            for event in data["events"]
            if event.get("is_current")
        ),
        None,
    )

    next_gameweek = next(
        (
            event
            for event in data["events"]
            if event.get("is_next")
        ),
        None,
    )

    print()

    if current_gameweek:
        print(
            f"Current GW  : "
            f"{current_gameweek.get('id')} "
            f"({current_gameweek.get('name')})"
        )
    else:
        print("Current GW  : None")

    if next_gameweek:
        print(
            f"Next GW     : "
            f"{next_gameweek.get('id')} "
            f"({next_gameweek.get('name')})"
        )
    else:
        print("Next GW     : None")

    print()
    print(f"Saved to    : {output_file}")
    print()
    print("Collection completed successfully.")
    print("=" * 60)


def main() -> None:
    print("=" * 60)
    print("FPL BOOTSTRAP COLLECTOR")
    print("=" * 60)

    try:
        print()
        print("Connecting to official FPL API...")

        with FPLClient() as client:
            data = client.get_bootstrap()

        print("Data received.")

        print("Validating response...")

        validate_bootstrap(data)

        print("Validation successful.")

        output_file = save_bootstrap(data)

        print_summary(
            data,
            output_file,
        )

    except Exception as exc:
        print()
        print("COLLECTION FAILED")
        print(f"Error: {exc}")
        print()

        raise SystemExit(1)


if __name__ == "__main__":
    main()