"""
Fetch and save official FPL player history.

For every player in the selected bootstrap snapshot:

    /api/element-summary/{player_id}/

The complete API response is saved unchanged.

Structure:

data/raw/2026-27/players/
    1/
        2026-08-14_10-00-00.json
    2/
        2026-08-14_10-00-01.json
    ...

A collection manifest is also created so we know which players
were successfully collected and which failed.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ============================================================
# PROJECT PATH
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from src.collectors.fpl_client import FPLClient


# ============================================================
# CONFIGURATION
# ============================================================

SEASON = "2026-27"

RAW_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / SEASON
)

BOOTSTRAP_DIR = RAW_DIR / "bootstrap"
PLAYERS_DIR = RAW_DIR / "players"

# Small delay between successful player requests.
# This is intentionally conservative.
REQUEST_DELAY = 0.25


# ============================================================
# BOOTSTRAP
# ============================================================

def get_latest_bootstrap_file() -> Path:
    """Return the newest bootstrap snapshot."""

    files = sorted(
        BOOTSTRAP_DIR.glob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not files:
        raise FileNotFoundError(
            f"No bootstrap snapshot found in: {BOOTSTRAP_DIR}"
        )

    return files[0]


def load_player_ids(
    bootstrap_file: Path,
) -> list[int]:
    """Load all player IDs from a bootstrap snapshot."""

    print()
    print(f"Using bootstrap snapshot:")
    print(f"  {bootstrap_file}")

    with bootstrap_file.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(
            "Bootstrap snapshot must contain a JSON object."
        )

    elements = data.get("elements")

    if not isinstance(elements, list):
        raise ValueError(
            "Bootstrap snapshot does not contain a valid "
            "'elements' list."
        )

    player_ids: list[int] = []

    for player in elements:
        if not isinstance(player, dict):
            continue

        player_id = player.get("id")

        if isinstance(player_id, int) and player_id > 0:
            player_ids.append(player_id)

    player_ids = sorted(set(player_ids))

    if not player_ids:
        raise ValueError(
            "No valid player IDs found in bootstrap snapshot."
        )

    return player_ids


# ============================================================
# PLAYER HISTORY VALIDATION
# ============================================================

def validate_player_history(
    player_id: int,
    data: Any,
) -> None:
    """Validate the basic structure of a player history response."""

    if not isinstance(data, dict):
        raise ValueError(
            f"Player {player_id}: response must be a JSON object."
        )

    # element-summary normally provides these sections.
    # We require them here because they are central to the
    # historical data pipeline.
    expected_sections = [
        "history",
        "fixtures",
    ]

    missing = [
        section
        for section in expected_sections
        if section not in data
    ]

    if missing:
        raise ValueError(
            f"Player {player_id}: missing sections: "
            + ", ".join(missing)
        )

    if not isinstance(data["history"], list):
        raise ValueError(
            f"Player {player_id}: 'history' must be a list."
        )

    if not isinstance(data["fixtures"], list):
        raise ValueError(
            f"Player {player_id}: 'fixtures' must be a list."
        )


# ============================================================
# SAVE PLAYER HISTORY
# ============================================================

def save_player_history(
    player_id: int,
    data: dict[str, Any],
    timestamp: str,
) -> Path:
    """
    Save the raw player-history response.

    The API response itself is not modified.
    """

    player_dir = PLAYERS_DIR / str(player_id)

    player_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = (
        player_dir
        / f"{timestamp}.json"
    )

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


# ============================================================
# MANIFEST
# ============================================================

def save_manifest(
    manifest: dict[str, Any],
    timestamp: str,
) -> Path:
    """Save collection metadata."""

    PLAYERS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = (
        PLAYERS_DIR
        / f"collection_manifest_{timestamp}.json"
    )

    with output_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            manifest,
            file,
            ensure_ascii=False,
            indent=2,
        )

    return output_file


# ============================================================
# MAIN COLLECTION
# ============================================================

def main() -> None:

    print("=" * 60)
    print("FPL PLAYER HISTORY COLLECTOR")
    print("=" * 60)

    try:

        # ----------------------------------------------------
        # 1. Find bootstrap
        # ----------------------------------------------------

        bootstrap_file = get_latest_bootstrap_file()

        player_ids = load_player_ids(
            bootstrap_file
        )

        total_players = len(player_ids)

        print()
        print(f"Players found: {total_players}")

        # ----------------------------------------------------
        # 2. Prepare collection timestamp
        # ----------------------------------------------------

        collection_timestamp = datetime.now(
            timezone.utc
        ).strftime("%Y-%m-%d_%H-%M-%S")

        started_at = datetime.now(
            timezone.utc
        ).isoformat()

        # ----------------------------------------------------
        # 3. Statistics
        # ----------------------------------------------------

        successful: list[int] = []
        failed: list[dict[str, Any]] = []

        # ----------------------------------------------------
        # 4. Connect to FPL
        # ----------------------------------------------------

        print()
        print("Connecting to official FPL API...")

        with FPLClient(
            timeout=30,
            max_retries=3,
            retry_delay=2,
        ) as client:

            # ------------------------------------------------
            # 5. Download every player
            # ------------------------------------------------

            for index, player_id in enumerate(
                player_ids,
                start=1,
            ):

                print(
                    f"[{index}/{total_players}] "
                    f"Player ID {player_id}...",
                    end=" ",
                    flush=True,
                )

                try:

                    data = client.get_player_summary(
                        player_id
                    )

                    validate_player_history(
                        player_id,
                        data,
                    )

                    output_file = save_player_history(
                        player_id,
                        data,
                        collection_timestamp,
                    )

                    successful.append(
                        player_id
                    )

                    history_count = len(
                        data.get("history", [])
                    )

                    fixture_count = len(
                        data.get("fixtures", [])
                    )

                    print(
                        f"OK "
                        f"(history={history_count}, "
                        f"fixtures={fixture_count})"
                    )

                except Exception as exc:

                    failed.append(
                        {
                            "player_id": player_id,
                            "error": str(exc),
                        }
                    )

                    print(
                        f"FAILED: {exc}"
                    )

                # --------------------------------------------
                # Small delay between requests
                # --------------------------------------------

                if index < total_players:
                    time.sleep(REQUEST_DELAY)

        # ----------------------------------------------------
        # 6. Manifest
        # ----------------------------------------------------

        finished_at = datetime.now(
            timezone.utc
        ).isoformat()

        manifest = {
            "season": SEASON,
            "collection_timestamp": collection_timestamp,
            "started_at": started_at,
            "finished_at": finished_at,
            "bootstrap_snapshot": str(
                bootstrap_file.relative_to(PROJECT_ROOT)
            ),
            "total_players": total_players,
            "successful": len(successful),
            "failed": len(failed),
            "successful_player_ids": successful,
            "failed_players": failed,
        }

        manifest_file = save_manifest(
            manifest,
            collection_timestamp,
        )

        # ----------------------------------------------------
        # 7. Final summary
        # ----------------------------------------------------

        print()
        print("=" * 60)
        print("PLAYER HISTORY COLLECTION COMPLETE")
        print("=" * 60)

        print()
        print(f"Season              : {SEASON}")
        print(f"Players requested   : {total_players}")
        print(f"Successful          : {len(successful)}")
        print(f"Failed              : {len(failed)}")

        print()
        print(f"Player data saved to:")
        print(f"  {PLAYERS_DIR}")

        print()
        print(f"Manifest saved to:")
        print(f"  {manifest_file}")

        if failed:
            print()
            print("Failed player IDs:")

            for item in failed:
                print(
                    f"  {item['player_id']}: "
                    f"{item['error']}"
                )

        print()
        print("=" * 60)

    except Exception as exc:

        print()
        print("=" * 60)
        print("PLAYER HISTORY COLLECTION FAILED")
        print("=" * 60)

        print()
        print(f"Error: {exc}")
        print()

        raise SystemExit(1)


if __name__ == "__main__":
    main()