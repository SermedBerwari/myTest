"""
Fetch and save the official FPL fixtures dataset.

This script:
1. Connects to the official FPL API.
2. Downloads all fixtures.
3. Validates the basic structure.
4. Saves the complete raw JSON response.
5. Prints a useful collection summary.

The raw response is preserved unchanged for future processing.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Project root
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
    / "fixtures"
)


def validate_fixtures(data: list) -> None:
    """Perform basic validation of the fixtures response."""

    if not isinstance(data, list):
        raise ValueError(
            "Fixtures data must be a list."
        )

    if not data:
        raise ValueError(
            "Fixtures endpoint returned an empty list."
        )

    required_fields = [
        "id",
        "team_h",
        "team_a",
        "event",
        "finished",
    ]

    first_fixture = data[0]

    missing = [
        field
        for field in required_fields
        if field not in first_fixture
    ]

    if missing:
        raise ValueError(
            "Fixture data is missing required fields: "
            + ", ".join(missing)
        )


def save_fixtures(data: list) -> Path:
    """Save the complete raw fixtures response."""

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


def print_summary(
    data: list,
    output_file: Path,
) -> None:
    """Print a useful fixture collection summary."""

    print()
    print("=" * 60)
    print("FPL FIXTURES COLLECTION")
    print("=" * 60)

    print()
    print(f"Season          : {SEASON}")
    print(f"Total fixtures  : {len(data)}")

    finished = sum(
        1
        for fixture in data
        if fixture.get("finished") is True
    )

    unfinished = sum(
        1
        for fixture in data
        if fixture.get("finished") is False
    )

    postponed = sum(
        1
        for fixture in data
        if fixture.get("started") is False
        and fixture.get("finished") is False
        and fixture.get("kickoff_time") is None
    )

    gameweeks = {
        fixture.get("event")
        for fixture in data
        if fixture.get("event") is not None
    }

    print(f"Finished        : {finished}")
    print(f"Unfinished      : {unfinished}")
    print(f"Gameweeks found : {len(gameweeks)}")
    print(f"Postponed/TBD   : {postponed}")

    print()
    print(f"Saved to        : {output_file}")
    print()
    print("Collection completed successfully.")
    print("=" * 60)


def main() -> None:
    print("=" * 60)
    print("FPL FIXTURES COLLECTOR")
    print("=" * 60)

    try:
        print()
        print("Connecting to official FPL API...")

        with FPLClient() as client:
            data = client.get_fixtures()

        print("Data received.")

        print("Validating response...")

        validate_fixtures(data)

        print("Validation successful.")

        output_file = save_fixtures(data)

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