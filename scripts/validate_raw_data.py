#!/usr/bin/env python3
"""
validate_raw_data.py

Production-ready validator for the FPL AI Weekly Squad Prediction project.

This validator is designed for the project's SNAPSHOT-BASED raw data
architecture:

data/
└── raw/
    └── <season>/
        ├── bootstrap/
        │   ├── <timestamp>.json
        │   └── ...
        │
        ├── fixtures/
        │   ├── <timestamp>.json
        │   └── ...
        │
        └── players/
            ├── <player_id>/
            │   ├── <timestamp>.json
            │   └── ...
            ├── <player_id>/
            │   └── ...
            └── ...

Important:
    Raw files are NEVER modified by this script.

Default behavior:
    Validate the LATEST snapshot of bootstrap, fixtures, and every player.

Optional:
    --all-snapshots
        Validate every historical JSON snapshot as well.

Output:
    data/validation/<season>/
        validation_report_<season>.json
        validation_report_<season>.txt

Exit codes:
    0 = PASSED
    1 = PASSED_WITH_WARNINGS
    2 = FAILED
    3 = EXECUTION_ERROR

Usage:
    python scripts/validate_raw_data.py

    python scripts/validate_raw_data.py --season 2026-27

    python scripts/validate_raw_data.py --all-snapshots

    python scripts/validate_raw_data.py --strict

    python scripts/validate_raw_data.py --quiet

    python scripts/validate_raw_data.py --project-root "E:/Python/FPL Fantasy Predictiom"
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_VERSION = "2.0.0"

DEFAULT_SEASON = "2026-27"

EXPECTED_TEAM_COUNT = 20
EXPECTED_GAMEWEEK_COUNT = 38

MIN_REASONABLE_PLAYER_COUNT = 400
MAX_REASONABLE_PLAYER_COUNT = 800

EXPECTED_POSITION_TYPES = {
    1: "Goalkeeper",
    2: "Defender",
    3: "Midfielder",
    4: "Forward",
}

BOOTSTRAP_REQUIRED_KEYS = {
    "elements",
    "teams",
    "events",
}

PLAYER_REQUIRED_FIELDS = {
    "id",
    "first_name",
    "second_name",
    "team",
    "element_type",
    "now_cost",
    "total_points",
}

TEAM_REQUIRED_FIELDS = {
    "id",
    "name",
    "short_name",
}

EVENT_REQUIRED_FIELDS = {
    "id",
    "name",
}

FIXTURE_REQUIRED_FIELDS = {
    "id",
    "event",
    "team_h",
    "team_a",
}

HISTORY_REQUIRED_FIELDS = {
    "element",
    "fixture",
    "opponent_team",
    "total_points",
    "minutes",
    "goals_scored",
    "assists",
}

HISTORY_NUMERIC_FIELDS = {
    "element",
    "fixture",
    "opponent_team",
    "total_points",
    "minutes",
    "goals_scored",
    "assists",
    "clean_sheets",
    "goals_conceded",
    "own_goals",
    "penalties_saved",
    "penalties_missed",
    "yellow_cards",
    "red_cards",
    "saves",
    "bonus",
    "bps",
    "influence",
    "creativity",
    "threat",
    "ict_index",
    "starts",
    "expected_goals",
    "expected_assists",
    "expected_goal_involvements",
    "expected_goals_conceded",
    "value",
    "transfers_balance",
    "selected",
    "transfers_in",
    "transfers_out",
}

# ============================================================================
# LOGGING
# ============================================================================

LOGGER = logging.getLogger("fpl_raw_validator")


class ConsoleFormatter(logging.Formatter):
    """Readable console logging."""

    def format(self, record: logging.LogRecord) -> str:
        return f"[{record.levelname:<8}] {record.getMessage()}"


def configure_logging(quiet: bool = False) -> None:
    """Configure application logging."""

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ConsoleFormatter())

    LOGGER.handlers.clear()
    LOGGER.addHandler(handler)

    LOGGER.setLevel(
        logging.WARNING if quiet else logging.INFO
    )


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ValidationIssue:
    severity: str
    category: str
    message: str
    file: str | None = None
    player_id: int | None = None
    record: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationStats:
    json_files_checked: int = 0

    bootstrap_snapshots_found: int = 0
    fixtures_snapshots_found: int = 0

    latest_bootstrap_snapshot: str | None = None
    latest_fixtures_snapshot: str | None = None

    player_directories_found: int = 0
    player_snapshots_found: int = 0

    bootstrap_players: int = 0
    bootstrap_teams: int = 0
    bootstrap_gameweeks: int = 0

    latest_player_snapshots_validated: int = 0
    latest_player_snapshots_invalid: int = 0

    historical_snapshots_validated: int = 0
    historical_snapshots_invalid: int = 0

    fixture_records: int = 0
    player_history_records: int = 0
    player_fixture_records: int = 0

    unique_player_ids_in_bootstrap: int = 0
    unique_player_ids_with_history: int = 0

    duplicate_player_ids: int = 0
    duplicate_fixture_ids: int = 0

    missing_player_directories: int = 0
    extra_player_directories: int = 0

    total_errors: int = 0
    total_warnings: int = 0
    total_info: int = 0


@dataclass
class ValidationReport:
    validator_version: str
    season: str

    started_at: str
    completed_at: str | None = None

    project_root: str | None = None
    raw_directory: str | None = None

    status: str = "NOT_RUN"

    statistics: ValidationStats = field(
        default_factory=ValidationStats
    )

    issues: list[ValidationIssue] = field(
        default_factory=list
    )

    discovered_snapshots: dict[str, Any] = field(
        default_factory=dict
    )

    recommendations: list[str] = field(
        default_factory=list
    )


# ============================================================================
# GENERAL HELPERS
# ============================================================================

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_int(value: Any) -> int | None:
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def to_float(value: Any) -> float | None:
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_id(value: Any) -> int | None:
    value = to_int(value)

    if value is None or value <= 0:
        return None

    return value


def read_json(path: Path) -> Any:
    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        return json.load(handle)


def is_json_file(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix.lower() == ".json"
    )


def relative_path(
    path: Path,
    root: Path,
) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def parse_timestamp_from_filename(
    path: Path,
) -> datetime | None:
    """
    Try to parse timestamps such as:

        2026-08-14_09-27-26.json
        2026-08-14_09-27-26
        2026-08-14-09-27-26.json

    Returns None if no recognized timestamp is found.
    """

    stem = path.stem

    patterns = [
        "%Y-%m-%d_%H-%M-%S",
        "%Y-%m-%d-%H-%M-%S",
        "%Y%m%d_%H%M%S",
        "%Y%m%d-%H%M%S",
    ]

    for pattern in patterns:
        try:
            return datetime.strptime(
                stem,
                pattern,
            )
        except ValueError:
            continue

    # Search inside filenames that contain additional prefixes/suffixes.
    match = re.search(
        r"(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})",
        stem,
    )

    if match:
        try:
            return datetime.strptime(
                match.group(1),
                "%Y-%m-%d_%H-%M-%S",
            )
        except ValueError:
            pass

    return None


def latest_json_file(
    directory: Path,
) -> Path | None:
    """
    Select latest JSON snapshot.

    Priority:
        1. Parsed timestamp in filename
        2. File modification time
    """

    if not directory.exists():
        return None

    files = [
        path
        for path in directory.iterdir()
        if is_json_file(path)
    ]

    if not files:
        return None

    def sort_key(path: Path) -> tuple[int, float]:
        timestamp = parse_timestamp_from_filename(path)

        if timestamp is not None:
            return (
                1,
                timestamp.timestamp(),
            )

        return (
            0,
            path.stat().st_mtime,
        )

    return max(
        files,
        key=sort_key,
    )


def all_json_files(
    directory: Path,
) -> list[Path]:
    if not directory.exists():
        return []

    return sorted(
        [
            path
            for path in directory.iterdir()
            if is_json_file(path)
        ],
        key=lambda path: (
            parse_timestamp_from_filename(path)
            or datetime.fromtimestamp(
                path.stat().st_mtime
            )
        ),
    )


def player_id_from_directory(
    path: Path,
) -> int | None:
    """
    Player directories must be numeric:

        players/1/
        players/2/
        ...
    """

    if not path.is_dir():
        return None

    if not path.name.isdigit():
        return None

    player_id = int(path.name)

    if player_id <= 0:
        return None

    return player_id


# ============================================================================
# VALIDATOR
# ============================================================================

class FPLRawDataValidator:
    """
    Validator for snapshot-based FPL raw data.
    """

    def __init__(
        self,
        project_root: Path,
        season: str,
        strict: bool = False,
        all_snapshots: bool = False,
    ) -> None:

        self.project_root = project_root.resolve()
        self.season = season

        self.strict = strict
        self.all_snapshots = all_snapshots

        self.raw_dir = (
            self.project_root
            / "data"
            / "raw"
            / season
        )

        self.bootstrap_dir = self.raw_dir / "bootstrap"
        self.fixtures_dir = self.raw_dir / "fixtures"
        self.players_dir = self.raw_dir / "players"

        self.validation_dir = (
            self.project_root
            / "data"
            / "validation"
            / season
        )

        self.report = ValidationReport(
            validator_version=SCRIPT_VERSION,
            season=season,
            started_at=utc_now_iso(),
            project_root=str(
                self.project_root
            ),
            raw_directory=str(
                self.raw_dir
            ),
        )

        # Canonical latest datasets.
        self.bootstrap: dict[str, Any] = {}
        self.fixtures: list[dict[str, Any]] = []

        # Canonical IDs.
        self.bootstrap_player_ids: set[int] = set()
        self.bootstrap_team_ids: set[int] = set()
        self.bootstrap_gameweek_ids: set[int] = set()
        self.fixture_ids: set[int] = set()

        self.history_player_ids: set[int] = set()

        # Player history statistics.
        self.player_history_counts: dict[
            int,
            int,
        ] = defaultdict(int)

    # ------------------------------------------------------------------------
    # ISSUE MANAGEMENT
    # ------------------------------------------------------------------------

    def add_issue(
        self,
        severity: str,
        category: str,
        message: str,
        file: Path | None = None,
        player_id: int | None = None,
        record: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:

        severity = severity.upper()

        issue = ValidationIssue(
            severity=severity,
            category=category,
            message=message,
            file=(
                relative_path(
                    file,
                    self.project_root,
                )
                if file
                else None
            ),
            player_id=player_id,
            record=record,
            details=details or {},
        )

        self.report.issues.append(issue)

        if severity == "ERROR":
            self.report.statistics.total_errors += 1
            LOGGER.error(message)

        elif severity == "WARNING":
            self.report.statistics.total_warnings += 1
            LOGGER.warning(message)

        else:
            self.report.statistics.total_info += 1
            LOGGER.info(message)

    # ------------------------------------------------------------------------
    # DIRECTORY DISCOVERY
    # ------------------------------------------------------------------------

    def validate_directory_structure(self) -> bool:
        """
        Validate the exact snapshot directory structure.
        """

        LOGGER.info(
            "Checking snapshot directory structure..."
        )

        if not self.raw_dir.exists():
            self.add_issue(
                "ERROR",
                "filesystem",
                f"Raw directory does not exist: {self.raw_dir}",
            )
            return False

        if not self.raw_dir.is_dir():
            self.add_issue(
                "ERROR",
                "filesystem",
                f"Raw path is not a directory: {self.raw_dir}",
            )
            return False

        required_dirs = [
            self.bootstrap_dir,
            self.fixtures_dir,
            self.players_dir,
        ]

        for directory in required_dirs:
            if not directory.exists():
                self.add_issue(
                    "ERROR",
                    "filesystem",
                    f"Required directory is missing: {directory}",
                )

            elif not directory.is_dir():
                self.add_issue(
                    "ERROR",
                    "filesystem",
                    f"Expected directory but found non-directory: {directory}",
                )

        return all(
            directory.exists()
            and directory.is_dir()
            for directory in required_dirs
        )

    # ------------------------------------------------------------------------
    # SNAPSHOT DISCOVERY
    # ------------------------------------------------------------------------

    def discover_snapshots(self) -> bool:
        """
        Discover bootstrap, fixtures, and player snapshots.
        """

        LOGGER.info(
            "Discovering raw snapshots..."
        )

        bootstrap_snapshots = all_json_files(
            self.bootstrap_dir
        )

        fixtures_snapshots = all_json_files(
            self.fixtures_dir
        )

        player_directories = [
            path
            for path in self.players_dir.iterdir()
            if path.is_dir()
            and player_id_from_directory(path) is not None
        ] if self.players_dir.exists() else []

        player_json_count = 0

        player_snapshot_map: dict[
            str,
            list[str],
        ] = {}

        for directory in sorted(
            player_directories,
            key=lambda p: int(p.name),
        ):
            snapshots = all_json_files(directory)

            player_json_count += len(snapshots)

            player_snapshot_map[
                directory.name
            ] = [
                relative_path(
                    path,
                    self.project_root,
                )
                for path in snapshots
            ]

            if not snapshots:
                self.add_issue(
                    "ERROR",
                    "player_snapshot",
                    (
                        f"Player directory {directory.name} "
                        "contains no JSON snapshots."
                    ),
                    directory,
                    player_id=int(directory.name),
                )

        self.report.statistics.bootstrap_snapshots_found = (
            len(bootstrap_snapshots)
        )

        self.report.statistics.fixtures_snapshots_found = (
            len(fixtures_snapshots)
        )

        self.report.statistics.player_directories_found = (
            len(player_directories)
        )

        self.report.statistics.player_snapshots_found = (
            player_json_count
        )

        latest_bootstrap = (
            latest_json_file(
                self.bootstrap_dir
            )
        )

        latest_fixtures = (
            latest_json_file(
                self.fixtures_dir
            )
        )

        self.report.statistics.latest_bootstrap_snapshot = (
            relative_path(
                latest_bootstrap,
                self.project_root,
            )
            if latest_bootstrap
            else None
        )

        self.report.statistics.latest_fixtures_snapshot = (
            relative_path(
                latest_fixtures,
                self.project_root,
            )
            if latest_fixtures
            else None
        )

        self.report.discovered_snapshots = {
            "bootstrap": [
                relative_path(
                    path,
                    self.project_root,
                )
                for path in bootstrap_snapshots
            ],
            "latest_bootstrap": (
                relative_path(
                    latest_bootstrap,
                    self.project_root,
                )
                if latest_bootstrap
                else None
            ),
            "fixtures": [
                relative_path(
                    path,
                    self.project_root,
                )
                for path in fixtures_snapshots
            ],
            "latest_fixtures": (
                relative_path(
                    latest_fixtures,
                    self.project_root,
                )
                if latest_fixtures
                else None
            ),
            "player_directories": len(
                player_directories
            ),
            "player_snapshots": player_snapshot_map,
        }

        if not bootstrap_snapshots:
            self.add_issue(
                "ERROR",
                "bootstrap_snapshot",
                "No bootstrap JSON snapshots were found.",
                self.bootstrap_dir,
            )

        if not fixtures_snapshots:
            self.add_issue(
                "ERROR",
                "fixtures_snapshot",
                "No fixtures JSON snapshots were found.",
                self.fixtures_dir,
            )

        if not player_directories:
            self.add_issue(
                "ERROR",
                "player_snapshot",
                "No numeric player directories were found.",
                self.players_dir,
            )

        # Warn about non-numeric player directories.
        if self.players_dir.exists():
            for path in self.players_dir.iterdir():
                if path.is_dir():
                    if player_id_from_directory(path) is None:
                        self.add_issue(
                            "WARNING",
                            "player_directory_name",
                            (
                                f"Unexpected player directory name: "
                                f"{path.name}"
                            ),
                            path,
                        )

        return (
            bool(bootstrap_snapshots)
            and bool(fixtures_snapshots)
            and bool(player_directories)
        )

    # ------------------------------------------------------------------------
    # BOOTSTRAP
    # ------------------------------------------------------------------------

    def validate_latest_bootstrap(self) -> None:
        """
        Validate the latest bootstrap snapshot.
        """

        path = latest_json_file(
            self.bootstrap_dir
        )

        if path is None:
            return

        LOGGER.info(
            "Latest bootstrap snapshot: %s",
            path.name,
        )

        data = self.load_json(
            path,
            "bootstrap",
        )

        if not isinstance(data, dict):
            self.add_issue(
                "ERROR",
                "bootstrap_structure",
                "Bootstrap root must be a JSON object.",
                path,
            )
            return

        self.bootstrap = data

        missing = (
            BOOTSTRAP_REQUIRED_KEYS
            - set(data.keys())
        )

        if missing:
            self.add_issue(
                "ERROR",
                "bootstrap_structure",
                (
                    "Bootstrap is missing required keys: "
                    f"{sorted(missing)}"
                ),
                path,
            )

        elements = data.get(
            "elements",
            [],
        )

        teams = data.get(
            "teams",
            [],
        )

        events = data.get(
            "events",
            [],
        )

        if not isinstance(elements, list):
            self.add_issue(
                "ERROR",
                "bootstrap_structure",
                "'elements' must be a list.",
                path,
            )
            elements = []

        if not isinstance(teams, list):
            self.add_issue(
                "ERROR",
                "bootstrap_structure",
                "'teams' must be a list.",
                path,
            )
            teams = []

        if not isinstance(events, list):
            self.add_issue(
                "ERROR",
                "bootstrap_structure",
                "'events' must be a list.",
                path,
            )
            events = []

        self.report.statistics.bootstrap_players = (
            len(elements)
        )

        self.report.statistics.bootstrap_teams = (
            len(teams)
        )

        self.report.statistics.bootstrap_gameweeks = (
            len(events)
        )

        self.validate_bootstrap_teams(
            teams,
            path,
        )

        # Teams must be loaded before player team references.
        self.validate_bootstrap_players(
            elements,
            path,
        )

        self.validate_bootstrap_gameweeks(
            events,
            path,
        )

        self.report.statistics.unique_player_ids_in_bootstrap = (
            len(self.bootstrap_player_ids)
        )

    def validate_bootstrap_players(
        self,
        players: list[Any],
        path: Path,
    ) -> None:

        LOGGER.info(
            "Validating %d bootstrap players...",
            len(players),
        )

        seen_ids: Counter[int] = Counter()

        for index, player in enumerate(players):

            if not isinstance(player, dict):
                self.add_issue(
                    "ERROR",
                    "player_structure",
                    (
                        f"Bootstrap player record #{index} "
                        "is not an object."
                    ),
                    path,
                    record=str(index),
                )
                continue

            missing = (
                PLAYER_REQUIRED_FIELDS
                - set(player.keys())
            )

            if missing:
                self.add_issue(
                    "ERROR",
                    "player_structure",
                    (
                        f"Player record #{index} is missing "
                        f"fields: {sorted(missing)}"
                    ),
                    path,
                    record=str(index),
                )

            player_id = normalize_id(
                player.get("id")
            )

            if player_id is None:
                self.add_issue(
                    "ERROR",
                    "player_id",
                    (
                        f"Invalid player ID in bootstrap "
                        f"record #{index}."
                    ),
                    path,
                    record=str(index),
                )
                continue

            seen_ids[player_id] += 1
            self.bootstrap_player_ids.add(
                player_id
            )

            team_id = normalize_id(
                player.get("team")
            )

            if team_id is None:
                self.add_issue(
                    "ERROR",
                    "player_team",
                    (
                        f"Player {player_id} has invalid "
                        "team reference."
                    ),
                    path,
                    player_id=player_id,
                )

            elif (
                self.bootstrap_team_ids
                and team_id
                not in self.bootstrap_team_ids
            ):
                self.add_issue(
                    "ERROR",
                    "player_team",
                    (
                        f"Player {player_id} references "
                        f"unknown team {team_id}."
                    ),
                    path,
                    player_id=player_id,
                )

            position = normalize_id(
                player.get("element_type")
            )

            if position not in EXPECTED_POSITION_TYPES:
                self.add_issue(
                    "WARNING",
                    "player_position",
                    (
                        f"Player {player_id} has unexpected "
                        f"position ID {player.get('element_type')}."
                    ),
                    path,
                    player_id=player_id,
                )

            price = to_int(
                player.get("now_cost")
            )

            if price is not None and price <= 0:
                self.add_issue(
                    "WARNING",
                    "player_price",
                    (
                        f"Player {player_id} has non-positive "
                        f"now_cost: {price}."
                    ),
                    path,
                    player_id=player_id,
                )

        duplicates = {
            player_id: count
            for player_id, count in seen_ids.items()
            if count > 1
        }

        self.report.statistics.duplicate_player_ids = (
            len(duplicates)
        )

        for player_id, count in duplicates.items():
            self.add_issue(
                "ERROR",
                "duplicate_player_id",
                (
                    f"Player ID {player_id} appears "
                    f"{count} times in bootstrap."
                ),
                path,
                player_id=player_id,
            )

        if (
            len(players)
            < MIN_REASONABLE_PLAYER_COUNT
        ):
            self.add_issue(
                "WARNING",
                "player_count",
                (
                    f"Bootstrap contains only {len(players)} "
                    "players. This is lower than the expected "
                    f"minimum of {MIN_REASONABLE_PLAYER_COUNT}."
                ),
                path,
            )

        elif (
            len(players)
            > MAX_REASONABLE_PLAYER_COUNT
        ):
            self.add_issue(
                "WARNING",
                "player_count",
                (
                    f"Bootstrap contains {len(players)} players, "
                    "which is above the configured expected range."
                ),
                path,
            )

    def validate_bootstrap_teams(
        self,
        teams: list[Any],
        path: Path,
    ) -> None:

        LOGGER.info(
            "Validating %d teams...",
            len(teams),
        )

        seen_ids: Counter[int] = Counter()

        for index, team in enumerate(teams):

            if not isinstance(team, dict):
                self.add_issue(
                    "ERROR",
                    "team_structure",
                    (
                        f"Team record #{index} is not an object."
                    ),
                    path,
                    record=str(index),
                )
                continue

            missing = (
                TEAM_REQUIRED_FIELDS
                - set(team.keys())
            )

            if missing:
                self.add_issue(
                    "ERROR",
                    "team_structure",
                    (
                        f"Team record #{index} is missing "
                        f"fields: {sorted(missing)}"
                    ),
                    path,
                    record=str(index),
                )

            team_id = normalize_id(
                team.get("id")
            )

            if team_id is None:
                self.add_issue(
                    "ERROR",
                    "team_id",
                    (
                        f"Invalid team ID in record #{index}."
                    ),
                    path,
                    record=str(index),
                )
                continue

            seen_ids[team_id] += 1
            self.bootstrap_team_ids.add(
                team_id
            )

        duplicates = {
            team_id: count
            for team_id, count in seen_ids.items()
            if count > 1
        }

        for team_id, count in duplicates.items():
            self.add_issue(
                "ERROR",
                "duplicate_team_id",
                (
                    f"Team ID {team_id} appears "
                    f"{count} times in bootstrap."
                ),
                path,
            )

        if len(teams) != EXPECTED_TEAM_COUNT:
            self.add_issue(
                "WARNING",
                "team_count",
                (
                    f"Bootstrap contains {len(teams)} teams. "
                    f"Expected {EXPECTED_TEAM_COUNT}."
                ),
                path,
            )

    def validate_bootstrap_gameweeks(
        self,
        events: list[Any],
        path: Path,
    ) -> None:

        LOGGER.info(
            "Validating %d gameweeks...",
            len(events),
        )

        seen_ids: Counter[int] = Counter()

        for index, event in enumerate(events):

            if not isinstance(event, dict):
                self.add_issue(
                    "ERROR",
                    "gameweek_structure",
                    (
                        f"Gameweek record #{index} "
                        "is not an object."
                    ),
                    path,
                    record=str(index),
                )
                continue

            missing = (
                EVENT_REQUIRED_FIELDS
                - set(event.keys())
            )

            if missing:
                self.add_issue(
                    "ERROR",
                    "gameweek_structure",
                    (
                        f"Gameweek record #{index} "
                        f"is missing fields: {sorted(missing)}"
                    ),
                    path,
                    record=str(index),
                )

            event_id = normalize_id(
                event.get("id")
            )

            if event_id is None:
                self.add_issue(
                    "ERROR",
                    "gameweek_id",
                    (
                        f"Invalid gameweek ID in record #{index}."
                    ),
                    path,
                    record=str(index),
                )
                continue

            seen_ids[event_id] += 1
            self.bootstrap_gameweek_ids.add(
                event_id
            )

        duplicates = {
            event_id: count
            for event_id, count in seen_ids.items()
            if count > 1
        }

        for event_id, count in duplicates.items():
            self.add_issue(
                "ERROR",
                "duplicate_gameweek_id",
                (
                    f"Gameweek {event_id} appears "
                    f"{count} times in bootstrap."
                ),
                path,
            )

        if len(events) != EXPECTED_GAMEWEEK_COUNT:
            self.add_issue(
                "INFO",
                "gameweek_count",
                (
                    f"Bootstrap currently contains {len(events)} "
                    f"gameweeks. A complete FPL season normally "
                    f"contains {EXPECTED_GAMEWEEK_COUNT}."
                ),
                path,
            )

    # ------------------------------------------------------------------------
    # FIXTURES
    # ------------------------------------------------------------------------

    def validate_latest_fixtures(self) -> None:

        path = latest_json_file(
            self.fixtures_dir
        )

        if path is None:
            return

        LOGGER.info(
            "Latest fixtures snapshot: %s",
            path.name,
        )

        data = self.load_json(
            path,
            "fixtures",
        )

        if isinstance(data, dict):

            # Defensive support for wrappers.
            for key in (
                "fixtures",
                "data",
                "results",
            ):
                if isinstance(
                    data.get(key),
                    list,
                ):
                    data = data[key]
                    break

        if not isinstance(data, list):
            self.add_issue(
                "ERROR",
                "fixtures_structure",
                "Fixtures snapshot root must be a JSON list.",
                path,
            )
            return

        self.fixtures = [
            item
            for item in data
            if isinstance(item, dict)
        ]

        self.report.statistics.fixture_records = (
            len(data)
        )

        seen_ids: Counter[int] = Counter()
        fixtures_by_gameweek: Counter[int] = Counter()

        for index, fixture in enumerate(data):

            if not isinstance(fixture, dict):
                self.add_issue(
                    "ERROR",
                    "fixture_structure",
                    (
                        f"Fixture record #{index} "
                        "is not an object."
                    ),
                    path,
                    record=str(index),
                )
                continue

            missing = (
                FIXTURE_REQUIRED_FIELDS
                - set(fixture.keys())
            )

            if missing:
                self.add_issue(
                    "ERROR",
                    "fixture_structure",
                    (
                        f"Fixture #{index} is missing "
                        f"fields: {sorted(missing)}"
                    ),
                    path,
                    record=str(index),
                )

            fixture_id = normalize_id(
                fixture.get("id")
            )

            if fixture_id is None:
                self.add_issue(
                    "ERROR",
                    "fixture_id",
                    (
                        f"Invalid fixture ID "
                        f"in record #{index}."
                    ),
                    path,
                    record=str(index),
                )
                continue

            seen_ids[fixture_id] += 1
            self.fixture_ids.add(
                fixture_id
            )

            event_id = normalize_id(
                fixture.get("event")
            )

            if event_id is not None:

                fixtures_by_gameweek[event_id] += 1

                if (
                    self.bootstrap_gameweek_ids
                    and event_id
                    not in self.bootstrap_gameweek_ids
                ):
                    self.add_issue(
                        "WARNING",
                        "fixture_gameweek",
                        (
                            f"Fixture {fixture_id} references "
                            f"unknown gameweek {event_id}."
                        ),
                        path,
                    )

            team_h = normalize_id(
                fixture.get("team_h")
            )

            team_a = normalize_id(
                fixture.get("team_a")
            )

            if team_h is None or team_a is None:
                continue

            if team_h == team_a:
                self.add_issue(
                    "ERROR",
                    "fixture_teams",
                    (
                        f"Fixture {fixture_id} has identical "
                        f"home and away team {team_h}."
                    ),
                    path,
                )

            if (
                self.bootstrap_team_ids
                and team_h
                not in self.bootstrap_team_ids
            ):
                self.add_issue(
                    "ERROR",
                    "fixture_team",
                    (
                        f"Fixture {fixture_id} references "
                        f"unknown home team {team_h}."
                    ),
                    path,
                )

            if (
                self.bootstrap_team_ids
                and team_a
                not in self.bootstrap_team_ids
            ):
                self.add_issue(
                    "ERROR",
                    "fixture_team",
                    (
                        f"Fixture {fixture_id} references "
                        f"unknown away team {team_a}."
                    ),
                    path,
                )

        duplicates = {
            fixture_id: count
            for fixture_id, count in seen_ids.items()
            if count > 1
        }

        self.report.statistics.duplicate_fixture_ids = (
            len(duplicates)
        )

        for fixture_id, count in duplicates.items():
            self.add_issue(
                "ERROR",
                "duplicate_fixture_id",
                (
                    f"Fixture ID {fixture_id} occurs "
                    f"{count} times in the latest fixture snapshot."
                ),
                path,
            )

    # ------------------------------------------------------------------------
    # PLAYER SNAPSHOTS
    # ------------------------------------------------------------------------

    def validate_latest_player_snapshots(
        self,
    ) -> None:

        LOGGER.info(
            "Validating latest snapshot for each player..."
        )

        if not self.players_dir.exists():
            return

        player_directories = sorted(
            [
                path
                for path in self.players_dir.iterdir()
                if path.is_dir()
                and player_id_from_directory(path)
                is not None
            ],
            key=lambda path: int(path.name),
        )

        for directory in player_directories:

            player_id = int(
                directory.name
            )

            latest = latest_json_file(
                directory
            )

            if latest is None:
                continue

            valid = self.validate_player_snapshot(
                latest,
                expected_player_id=player_id,
                latest_snapshot=True,
            )

            if valid:
                self.report.statistics.latest_player_snapshots_validated += 1
            else:
                self.report.statistics.latest_player_snapshots_invalid += 1

    def validate_all_player_snapshots(
        self,
    ) -> None:

        LOGGER.info(
            "Validating ALL historical player snapshots..."
        )

        if not self.players_dir.exists():
            return

        player_directories = sorted(
            [
                path
                for path in self.players_dir.iterdir()
                if path.is_dir()
                and player_id_from_directory(path)
                is not None
            ],
            key=lambda path: int(path.name),
        )

        for directory in player_directories:

            player_id = int(
                directory.name
            )

            snapshots = all_json_files(
                directory
            )

            for snapshot in snapshots:

                valid = self.validate_player_snapshot(
                    snapshot,
                    expected_player_id=player_id,
                    latest_snapshot=False,
                )

                if valid:
                    self.report.statistics.historical_snapshots_validated += 1
                else:
                    self.report.statistics.historical_snapshots_invalid += 1

    def validate_player_snapshot(
        self,
        path: Path,
        expected_player_id: int,
        latest_snapshot: bool,
    ) -> bool:

        data = self.load_json(
            path,
            "player_history",
        )

        if not isinstance(data, dict):
            self.add_issue(
                "ERROR",
                "player_history_structure",
                (
                    f"Player {expected_player_id} snapshot "
                    "root must be a JSON object."
                ),
                path,
                player_id=expected_player_id,
            )
            return False

        history = data.get(
            "history",
            []
        )

        fixtures = data.get(
            "fixtures",
            []
        )

        if not isinstance(history, list):
            self.add_issue(
                "ERROR",
                "player_history_structure",
                (
                    f"Player {expected_player_id} 'history' "
                    "must be a list."
                ),
                path,
                player_id=expected_player_id,
            )
            return False

        if not isinstance(fixtures, list):
            self.add_issue(
                "ERROR",
                "player_fixture_structure",
                (
                    f"Player {expected_player_id} 'fixtures' "
                    "must be a list."
                ),
                path,
                player_id=expected_player_id,
            )
            fixtures = []

        self.report.statistics.player_history_records += (
            len(history)
        )

        self.report.statistics.player_fixture_records += (
            len(fixtures)
        )

        self.player_history_counts[
            expected_player_id
        ] += len(history)

        if latest_snapshot:
            self.history_player_ids.add(
                expected_player_id
            )

        valid_history = self.validate_history_records(
            history,
            path,
            expected_player_id,
        )

        self.validate_player_fixture_records(
            fixtures,
            path,
            expected_player_id,
        )

        # A valid element-summary response normally contains these keys.
        if "history" not in data:
            self.add_issue(
                "ERROR",
                "player_history_structure",
                (
                    f"Player {expected_player_id} snapshot "
                    "does not contain 'history'."
                ),
                path,
                player_id=expected_player_id,
            )
            valid_history = False

        if "fixtures" not in data:
            self.add_issue(
                "WARNING",
                "player_history_structure",
                (
                    f"Player {expected_player_id} snapshot "
                    "does not contain 'fixtures'."
                ),
                path,
                player_id=expected_player_id,
            )

        return valid_history

    # ------------------------------------------------------------------------
    # PLAYER HISTORY RECORDS
    # ------------------------------------------------------------------------

    def validate_history_records(
        self,
        history: list[Any],
        path: Path,
        player_id: int,
    ) -> bool:

        valid = True

        seen_fixture_ids: set[int] = set()
        seen_events: set[int] = set()

        previous_event: int | None = None

        for index, record in enumerate(history):

            if not isinstance(record, dict):
                self.add_issue(
                    "ERROR",
                    "history_record_structure",
                    (
                        f"Player {player_id} history "
                        f"record #{index} is not an object."
                    ),
                    path,
                    player_id=player_id,
                    record=str(index),
                )

                valid = False
                continue

            missing = (
                HISTORY_REQUIRED_FIELDS
                - set(record.keys())
            )

            if missing:
                self.add_issue(
                    "WARNING",
                    "history_record_fields",
                    (
                        f"Player {player_id} history record "
                        f"#{index} is missing fields: "
                        f"{sorted(missing)}"
                    ),
                    path,
                    player_id=player_id,
                    record=str(index),
                )

            element = normalize_id(
                record.get("element")
            )

            if (
                element is not None
                and element != player_id
            ):
                self.add_issue(
                    "ERROR",
                    "history_player_id",
                    (
                        f"Player {player_id} snapshot contains "
                        f"history record for player {element}."
                    ),
                    path,
                    player_id=player_id,
                    record=str(index),
                )

                valid = False

            fixture_id = normalize_id(
                record.get("fixture")
            )

            if fixture_id is not None:

                if fixture_id in seen_fixture_ids:
                    self.add_issue(
                        "ERROR",
                        "duplicate_player_fixture",
                        (
                            f"Player {player_id} has duplicate "
                            f"fixture {fixture_id} in one snapshot."
                        ),
                        path,
                        player_id=player_id,
                        record=str(fixture_id),
                    )

                    valid = False

                seen_fixture_ids.add(
                    fixture_id
                )

            event_id = normalize_id(
                record.get("round")
                or record.get("event")
            )

            if event_id is not None:

                if event_id in seen_events:
                    self.add_issue(
                        "WARNING",
                        "duplicate_player_gameweek",
                        (
                            f"Player {player_id} has multiple "
                            f"history records for gameweek "
                            f"{event_id}."
                        ),
                        path,
                        player_id=player_id,
                        record=str(event_id),
                    )

                seen_events.add(
                    event_id
                )

                if (
                    previous_event is not None
                    and event_id < previous_event
                ):
                    self.add_issue(
                        "WARNING",
                        "history_order",
                        (
                            f"Player {player_id} history is not "
                            f"chronologically ordered around "
                            f"gameweek {event_id}."
                        ),
                        path,
                        player_id=player_id,
                        record=str(event_id),
                    )

                previous_event = event_id

            self.validate_history_numeric_fields(
                record,
                path,
                player_id,
                index,
            )

            if (
                fixture_id is not None
                and self.fixture_ids
                and fixture_id not in self.fixture_ids
            ):
                # Historical snapshots can legitimately reference
                # fixtures not present in the latest fixture snapshot.
                #
                # Therefore this is a WARNING rather than an ERROR.
                self.add_issue(
                    "WARNING",
                    "history_fixture_reference",
                    (
                        f"Player {player_id} history references "
                        f"fixture {fixture_id}, which is not present "
                        "in the latest global fixtures snapshot."
                    ),
                    path,
                    player_id=player_id,
                    record=str(fixture_id),
                )

        return valid

    def validate_history_numeric_fields(
        self,
        record: dict[str, Any],
        path: Path,
        player_id: int,
        index: int,
    ) -> None:

        for field_name in HISTORY_NUMERIC_FIELDS:

            if field_name not in record:
                continue

            value = record.get(
                field_name
            )

            if value is None:
                continue

            if to_float(value) is None:
                self.add_issue(
                    "WARNING",
                    "history_numeric_type",
                    (
                        f"Player {player_id} record {index} "
                        f"has non-numeric value in "
                        f"'{field_name}'."
                    ),
                    path,
                    player_id=player_id,
                    record=str(index),
                    details={
                        "field": field_name,
                        "value": value,
                    },
                )

        minutes = to_float(
            record.get("minutes")
        )

        if (
            minutes is not None
            and (
                minutes < 0
                or minutes > 120
            )
        ):
            self.add_issue(
                "WARNING",
                "history_minutes",
                (
                    f"Player {player_id} has unusual minutes "
                    f"value {minutes}."
                ),
                path,
                player_id=player_id,
                record=str(index),
            )

    # ------------------------------------------------------------------------
    # PLAYER FIXTURES
    # ------------------------------------------------------------------------

    def validate_player_fixture_records(
        self,
        fixtures: list[Any],
        path: Path,
        player_id: int,
    ) -> None:

        for index, fixture in enumerate(fixtures):

            if not isinstance(fixture, dict):
                self.add_issue(
                    "WARNING",
                    "player_fixture_structure",
                    (
                        f"Player {player_id} fixture record "
                        f"#{index} is not an object."
                    ),
                    path,
                    player_id=player_id,
                    record=str(index),
                )
                continue

            fixture_id = normalize_id(
                fixture.get("id")
            )

            if (
                fixture_id is not None
                and self.fixture_ids
                and fixture_id not in self.fixture_ids
            ):
                self.add_issue(
                    "WARNING",
                    "player_fixture_reference",
                    (
                        f"Player {player_id} references fixture "
                        f"{fixture_id}, which is not present in "
                        "the latest global fixtures snapshot."
                    ),
                    path,
                    player_id=player_id,
                    record=str(fixture_id),
                )

    # ------------------------------------------------------------------------
    # CROSS-DATA PLAYER VALIDATION
    # ------------------------------------------------------------------------

    def validate_player_directory_consistency(
        self,
    ) -> None:

        LOGGER.info(
            "Checking player directory consistency..."
        )

        if not self.players_dir.exists():
            return

        directory_ids: set[int] = set()

        for directory in self.players_dir.iterdir():

            if not directory.is_dir():
                continue

            player_id = player_id_from_directory(
                directory
            )

            if player_id is None:
                continue

            directory_ids.add(
                player_id
            )

        missing = (
            self.bootstrap_player_ids
            - directory_ids
        )

        extra = (
            directory_ids
            - self.bootstrap_player_ids
        )

        self.report.statistics.missing_player_directories = (
            len(missing)
        )

        self.report.statistics.extra_player_directories = (
            len(extra)
        )

        if missing:

            preview = sorted(
                missing
            )[:50]

            self.add_issue(
                "ERROR",
                "missing_player_directory",
                (
                    f"{len(missing)} bootstrap players do not "
                    f"have player directories. Sample: {preview}"
                ),
                self.players_dir,
                details={
                    "count": len(missing),
                    "player_ids": sorted(missing),
                },
            )

        if extra:

            preview = sorted(
                extra
            )[:50]

            self.add_issue(
                "WARNING",
                "extra_player_directory",
                (
                    f"{len(extra)} player directories are not "
                    f"present in bootstrap. Sample: {preview}"
                ),
                self.players_dir,
                details={
                    "count": len(extra),
                    "player_ids": sorted(extra),
                },
            )

    # ------------------------------------------------------------------------
    # SNAPSHOT CONSISTENCY
    # ------------------------------------------------------------------------

    def validate_snapshot_metadata(self) -> None:
        """
        Validate snapshot availability.

        We intentionally do NOT require every player to have the exact
        same number of snapshots. A collection can legitimately fail
        for one player during a particular run.
        """

        LOGGER.info(
            "Checking snapshot coverage..."
        )

        if not self.players_dir.exists():
            return

        snapshot_counts: dict[int, int] = {}

        for directory in self.players_dir.iterdir():

            player_id = player_id_from_directory(
                directory
            )

            if player_id is None:
                continue

            count = len(
                all_json_files(directory)
            )

            snapshot_counts[
                player_id
            ] = count

        if not snapshot_counts:
            return

        distribution = Counter(
            snapshot_counts.values()
        )

        minimum = min(
            snapshot_counts.values()
        )

        maximum = max(
            snapshot_counts.values()
        )

        self.add_issue(
            "INFO",
            "snapshot_coverage",
            (
                f"Player snapshot coverage: "
                f"{len(snapshot_counts)} players; "
                f"minimum snapshots={minimum}; "
                f"maximum snapshots={maximum}."
            ),
        )

        if minimum != maximum:

            sparse_players = [
                player_id
                for player_id, count
                in snapshot_counts.items()
                if count == minimum
            ]

            self.add_issue(
                "WARNING",
                "snapshot_coverage",
                (
                    "Players do not all have the same number of "
                    f"snapshots. Lowest count={minimum}, "
                    f"highest count={maximum}. "
                    f"Sample of lowest-coverage players: "
                    f"{sorted(sparse_players)[:20]}"
                ),
            )

    # ------------------------------------------------------------------------
    # JSON LOADING
    # ------------------------------------------------------------------------

    def load_json(
        self,
        path: Path,
        category: str,
    ) -> Any:

        try:

            data = read_json(
                path
            )

            self.report.statistics.json_files_checked += 1

            return data

        except json.JSONDecodeError as exc:

            self.add_issue(
                "ERROR",
                f"{category}_json",
                (
                    f"Invalid JSON in {path.name}: "
                    f"{exc}"
                ),
                path,
            )

        except OSError as exc:

            self.add_issue(
                "ERROR",
                f"{category}_file",
                (
                    f"Could not read {path.name}: "
                    f"{exc}"
                ),
                path,
            )

        return None

    # ------------------------------------------------------------------------
    # QUALITY RULES
    # ------------------------------------------------------------------------

    def run_quality_checks(self) -> None:

        LOGGER.info(
            "Running final quality checks..."
        )

        stats = self.report.statistics

        if stats.bootstrap_players == 0:
            self.add_issue(
                "ERROR",
                "quality",
                "No bootstrap players loaded.",
            )

        if stats.bootstrap_teams == 0:
            self.add_issue(
                "ERROR",
                "quality",
                "No bootstrap teams loaded.",
            )

        if stats.fixture_records == 0:
            self.add_issue(
                "ERROR",
                "quality",
                "No fixtures loaded.",
            )

        if (
            stats.player_directories_found
            == 0
        ):
            self.add_issue(
                "ERROR",
                "quality",
                "No player directories found.",
            )

        if (
            stats.bootstrap_players > 0
            and stats.player_directories_found > 0
        ):

            coverage = (
                stats.unique_player_ids_with_history
                / stats.bootstrap_players
                * 100
                if stats.bootstrap_players
                else 0
            )

            self.add_issue(
                "INFO",
                "quality",
                (
                    f"Latest player-history coverage: "
                    f"{stats.unique_player_ids_with_history}/"
                    f"{stats.bootstrap_players} "
                    f"({coverage:.2f}%)."
                ),
            )

            if coverage < 100:
                self.add_issue(
                    "WARNING",
                    "quality",
                    (
                        f"Latest player-history coverage is "
                        f"{coverage:.2f}%, below 100%."
                    ),
                )

    # ------------------------------------------------------------------------
    # RECOMMENDATIONS
    # ------------------------------------------------------------------------

    def generate_recommendations(self) -> None:

        stats = self.report.statistics

        recommendations: list[str] = []

        if stats.total_errors > 0:
            recommendations.append(
                "STOP the processing pipeline until all critical "
                "validation errors are resolved."
            )

        if (
            stats.missing_player_directories > 0
        ):
            recommendations.append(
                "Re-run player-history collection for missing player IDs."
            )

        if (
            stats.extra_player_directories > 0
        ):
            recommendations.append(
                "Review player directories not present in the latest "
                "bootstrap snapshot."
            )

        if (
            stats.latest_player_snapshots_invalid > 0
        ):
            recommendations.append(
                "Repair or recollect invalid latest player snapshots "
                "before building the processed dataset."
            )

        if stats.total_warnings > 0:
            recommendations.append(
                "Review warnings before using the dataset for ML training."
            )

        if stats.total_errors == 0:
            recommendations.append(
                "Raw data passed all critical validation checks."
            )

        recommendations.append(
            "Keep data/raw immutable. All normalization should write "
            "to data/processed/."
        )

        recommendations.append(
            "Run this validator after every scheduled FPL data collection."
        )

        recommendations.append(
            "Use --all-snapshots periodically to audit historical "
            "snapshot integrity."
        )

        self.report.recommendations = (
            recommendations
        )

    # ------------------------------------------------------------------------
    # RUN
    # ------------------------------------------------------------------------

    def run(self) -> ValidationReport:

        LOGGER.info("=" * 72)
        LOGGER.info(
            "FPL RAW DATA VALIDATOR"
        )
        LOGGER.info("=" * 72)

        LOGGER.info(
            "Version       : %s",
            SCRIPT_VERSION,
        )

        LOGGER.info(
            "Season        : %s",
            self.season,
        )

        LOGGER.info(
            "Project root  : %s",
            self.project_root,
        )

        LOGGER.info(
            "Raw directory : %s",
            self.raw_dir,
        )

        LOGGER.info(
            "Mode          : %s",
            (
                "ALL SNAPSHOTS"
                if self.all_snapshots
                else "LATEST SNAPSHOTS"
            ),
        )

        LOGGER.info("")

        structure_ok = (
            self.validate_directory_structure()
        )

        if not structure_ok:
            self.report.status = "FAILED"
            self.report.completed_at = utc_now_iso()
            self.generate_recommendations()
            return self.report

        discovered = (
            self.discover_snapshots()
        )

        if not discovered:
            self.report.status = "FAILED"
            self.report.completed_at = utc_now_iso()
            self.generate_recommendations()
            return self.report

        # --------------------------------------------------------------
        # Latest canonical data
        # --------------------------------------------------------------

        self.validate_latest_bootstrap()

        self.validate_latest_fixtures()

        # --------------------------------------------------------------
        # Player snapshots
        # --------------------------------------------------------------

        self.validate_latest_player_snapshots()

        if self.all_snapshots:
            self.validate_all_player_snapshots()

        # --------------------------------------------------------------
        # Cross validation
        # --------------------------------------------------------------

        self.validate_player_directory_consistency()

        self.report.statistics.unique_player_ids_with_history = (
            len(
                self.history_player_ids
            )
        )

        self.validate_snapshot_metadata()

        self.run_quality_checks()

        self.generate_recommendations()

        self.report.completed_at = utc_now_iso()

        if self.report.statistics.total_errors > 0:
            self.report.status = "FAILED"

        elif self.report.statistics.total_warnings > 0:
            self.report.status = (
                "PASSED_WITH_WARNINGS"
            )

        else:
            self.report.status = "PASSED"

        return self.report

    # ------------------------------------------------------------------------
    # REPORTS
    # ------------------------------------------------------------------------

    def write_reports(
        self,
    ) -> tuple[Path, Path]:

        self.validation_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        json_path = (
            self.validation_dir
            / f"validation_report_{self.season}.json"
        )

        txt_path = (
            self.validation_dir
            / f"validation_report_{self.season}.txt"
        )

        with json_path.open(
            "w",
            encoding="utf-8",
        ) as handle:

            json.dump(
                asdict(self.report),
                handle,
                indent=2,
                ensure_ascii=False,
            )

        with txt_path.open(
            "w",
            encoding="utf-8",
        ) as handle:

            handle.write(
                self.build_text_report()
            )

        return (
            json_path,
            txt_path,
        )

    def build_text_report(self) -> str:

        stats = self.report.statistics

        lines: list[str] = []

        lines.append("=" * 72)
        lines.append(
            "FPL RAW DATA VALIDATION REPORT"
        )
        lines.append("=" * 72)
        lines.append("")

        lines.append(
            f"Validator version : "
            f"{self.report.validator_version}"
        )

        lines.append(
            f"Season            : "
            f"{self.report.season}"
        )

        lines.append(
            f"Status            : "
            f"{self.report.status}"
        )

        lines.append(
            f"Started           : "
            f"{self.report.started_at}"
        )

        lines.append(
            f"Completed         : "
            f"{self.report.completed_at}"
        )

        lines.append("")

        lines.append("-" * 72)
        lines.append("SNAPSHOT STRUCTURE")
        lines.append("-" * 72)

        lines.append(
            f"Bootstrap snapshots       : "
            f"{stats.bootstrap_snapshots_found}"
        )

        lines.append(
            f"Latest bootstrap          : "
            f"{stats.latest_bootstrap_snapshot}"
        )

        lines.append(
            f"Fixtures snapshots        : "
            f"{stats.fixtures_snapshots_found}"
        )

        lines.append(
            f"Latest fixtures           : "
            f"{stats.latest_fixtures_snapshot}"
        )

        lines.append(
            f"Player directories        : "
            f"{stats.player_directories_found}"
        )

        lines.append(
            f"Player snapshots          : "
            f"{stats.player_snapshots_found}"
        )

        lines.append("")

        lines.append("-" * 72)
        lines.append("DATA")
        lines.append("-" * 72)

        lines.append(
            f"Bootstrap players         : "
            f"{stats.bootstrap_players}"
        )

        lines.append(
            f"Bootstrap teams           : "
            f"{stats.bootstrap_teams}"
        )

        lines.append(
            f"Bootstrap gameweeks       : "
            f"{stats.bootstrap_gameweeks}"
        )

        lines.append(
            f"Fixture records            : "
            f"{stats.fixture_records}"
        )

        lines.append(
            f"Player history records     : "
            f"{stats.player_history_records}"
        )

        lines.append(
            f"Player fixture records     : "
            f"{stats.player_fixture_records}"
        )

        lines.append("")

        lines.append("-" * 72)
        lines.append("PLAYER COVERAGE")
        lines.append("-" * 72)

        lines.append(
            f"Bootstrap player IDs       : "
            f"{stats.unique_player_ids_in_bootstrap}"
        )

        lines.append(
            f"Latest history player IDs  : "
            f"{stats.unique_player_ids_with_history}"
        )

        lines.append(
            f"Missing player directories  : "
            f"{stats.missing_player_directories}"
        )

        lines.append(
            f"Extra player directories    : "
            f"{stats.extra_player_directories}"
        )

        lines.append("")

        lines.append("-" * 72)
        lines.append("SNAPSHOT VALIDATION")
        lines.append("-" * 72)

        lines.append(
            f"Latest snapshots validated : "
            f"{stats.latest_player_snapshots_validated}"
        )

        lines.append(
            f"Latest snapshots invalid    : "
            f"{stats.latest_player_snapshots_invalid}"
        )

        lines.append(
            f"Historical snapshots valid  : "
            f"{stats.historical_snapshots_validated}"
        )

        lines.append(
            f"Historical snapshots invalid: "
            f"{stats.historical_snapshots_invalid}"
        )

        lines.append("")

        lines.append("-" * 72)
        lines.append("DUPLICATES")
        lines.append("-" * 72)

        lines.append(
            f"Duplicate player IDs        : "
            f"{stats.duplicate_player_ids}"
        )

        lines.append(
            f"Duplicate fixture IDs       : "
            f"{stats.duplicate_fixture_ids}"
        )

        lines.append("")

        lines.append("-" * 72)
        lines.append("ISSUES")
        lines.append("-" * 72)

        lines.append(
            f"Errors                      : "
            f"{stats.total_errors}"
        )

        lines.append(
            f"Warnings                    : "
            f"{stats.total_warnings}"
        )

        lines.append(
            f"Info                        : "
            f"{stats.total_info}"
        )

        lines.append("")

        if self.report.issues:

            lines.append("-" * 72)
            lines.append("ISSUE DETAILS")
            lines.append("-" * 72)

            for number, issue in enumerate(
                self.report.issues,
                start=1,
            ):

                lines.append(
                    f"{number:04d}. "
                    f"[{issue.severity}] "
                    f"[{issue.category}] "
                    f"{issue.message}"
                )

                if issue.file:
                    lines.append(
                        f"      File: {issue.file}"
                    )

                if issue.player_id is not None:
                    lines.append(
                        f"      Player ID: "
                        f"{issue.player_id}"
                    )

                if issue.record:
                    lines.append(
                        f"      Record: "
                        f"{issue.record}"
                    )

                if issue.details:
                    lines.append(
                        "      Details: "
                        + json.dumps(
                            issue.details,
                            ensure_ascii=False,
                        )
                    )

                lines.append("")

        lines.append("-" * 72)
        lines.append("RECOMMENDATIONS")
        lines.append("-" * 72)

        for recommendation in (
            self.report.recommendations
        ):
            lines.append(
                f"- {recommendation}"
            )

        lines.append("")

        lines.append("=" * 72)
        lines.append(
            f"FINAL STATUS: "
            f"{self.report.status}"
        )
        lines.append("=" * 72)
        lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------------
    # CONSOLE SUMMARY
    # ------------------------------------------------------------------------

    def print_summary(
        self,
        json_path: Path,
        txt_path: Path,
    ) -> None:

        stats = self.report.statistics

        print()
        print("=" * 72)
        print(
            "FPL RAW DATA VALIDATION COMPLETE"
        )
        print("=" * 72)
        print()

        print(
            f"Season                     : "
            f"{self.season}"
        )

        print(
            f"Status                     : "
            f"{self.report.status}"
        )

        print()

        print(
            f"Bootstrap snapshots        : "
            f"{stats.bootstrap_snapshots_found}"
        )

        print(
            f"Latest bootstrap           : "
            f"{stats.latest_bootstrap_snapshot}"
        )

        print(
            f"Fixtures snapshots         : "
            f"{stats.fixtures_snapshots_found}"
        )

        print(
            f"Latest fixtures            : "
            f"{stats.latest_fixtures_snapshot}"
        )

        print()

        print(
            f"Bootstrap players          : "
            f"{stats.bootstrap_players}"
        )

        print(
            f"Bootstrap teams            : "
            f"{stats.bootstrap_teams}"
        )

        print(
            f"Gameweeks                  : "
            f"{stats.bootstrap_gameweeks}"
        )

        print(
            f"Fixtures                   : "
            f"{stats.fixture_records}"
        )

        print(
            f"Player directories         : "
            f"{stats.player_directories_found}"
        )

        print(
            f"Player snapshots           : "
            f"{stats.player_snapshots_found}"
        )

        print()

        print(
            f"Missing player directories : "
            f"{stats.missing_player_directories}"
        )

        print(
            f"Extra player directories   : "
            f"{stats.extra_player_directories}"
        )

        print(
            f"Duplicate fixture IDs     : "
            f"{stats.duplicate_fixture_ids}"
        )

        print()

        print(
            f"Errors                     : "
            f"{stats.total_errors}"
        )

        print(
            f"Warnings                   : "
            f"{stats.total_warnings}"
        )

        print()

        print(
            f"JSON report                : "
            f"{json_path}"
        )

        print(
            f"Text report                : "
            f"{txt_path}"
        )

        print()

        print("=" * 72)

        if self.report.status == "FAILED":

            print(
                "RESULT: FAILED"
            )

            print(
                "Do NOT continue to dataset building."
            )

        elif (
            self.report.status
            == "PASSED_WITH_WARNINGS"
        ):

            print(
                "RESULT: PASSED WITH WARNINGS"
            )

            print(
                "Review the warnings before continuing."
            )

        else:

            print(
                "RESULT: PASSED"
            )

            print(
                "Raw data is ready for normalization."
            )

        print("=" * 72)
        print()


# ============================================================================
# ARGUMENTS
# ============================================================================

def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Validate snapshot-based FPL raw data."
        )
    )

    parser.add_argument(
        "--season",
        default=DEFAULT_SEASON,
        help=(
            "FPL season to validate. "
            f"Default: {DEFAULT_SEASON}"
        ),
    )

    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help=(
            "Project root containing data/raw/<season>. "
            "Defaults to the directory above scripts/."
        ),
    )

    parser.add_argument(
        "--all-snapshots",
        action="store_true",
        help=(
            "Validate every historical player snapshot, "
            "not only the latest snapshot."
        ),
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Treat warnings as failures. "
            "Recommended for automated pipelines."
        ),
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only display warnings and errors.",
    )

    return parser.parse_args()


# ============================================================================
# PROJECT ROOT
# ============================================================================

def discover_project_root() -> Path:

    script_path = Path(
        __file__
    ).resolve()

    return (
        script_path.parent.parent
    )


# ============================================================================
# MAIN
# ============================================================================

def main() -> int:

    args = parse_args()

    configure_logging(
        quiet=args.quiet
    )

    try:

        project_root = (
            args.project_root.resolve()
            if args.project_root
            else discover_project_root()
        )

        validator = FPLRawDataValidator(
            project_root=project_root,
            season=args.season,
            strict=args.strict,
            all_snapshots=args.all_snapshots,
        )

        report = validator.run()

        json_path, txt_path = (
            validator.write_reports()
        )

        validator.print_summary(
            json_path=json_path,
            txt_path=txt_path,
        )

        if report.status == "FAILED":
            return 2

        if (
            report.status
            == "PASSED_WITH_WARNINGS"
        ):

            if args.strict:
                return 2

            return 1

        return 0

    except KeyboardInterrupt:

        LOGGER.error(
            "Validation interrupted by user."
        )

        return 3

    except Exception as exc:

        LOGGER.exception(
            "Unexpected validator failure: %s",
            exc,
        )

        return 3


if __name__ == "__main__":
    sys.exit(main())