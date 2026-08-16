#!/usr/bin/env python3
"""
Collect completed historical FPL seasons for the FPL AI Weekly Squad Prediction project.

This collector intentionally keeps the existing 2026-27 live raw dataset untouched.

Historical source:
    imadeddine-belkat/Premier-League-Stats
    https://github.com/imadeddine-belkat/Premier-League-Stats

The repository documents that its FPL gameweek data is scraped from the
official FPL API and provides season-level merged player/gameweek data,
fixtures, team indexes, and player indexes.

Why this collector uses an archive source instead of calling the current
FPL API for old seasons:
    The public FPL API is primarily a current-season API. It does not provide
    a stable "season=YYYY-YY" historical endpoint for arbitrary completed
    seasons. Reconstructing old seasons by repeatedly calling the current API
    is therefore not a reliable historical collection strategy.

Collected seasons by default:
    2021-22
    2022-23
    2023-24
    2024-25
    2025-26

Output:
    data/raw/<season>/historical_source/
        player_gameweek.csv
        fixtures.csv
        players_index.csv
        teams_index.csv
        collection_manifest.json

The files are downloaded as source/archive data and are NOT presented as
synthetic official API JSON. A later historical normalization step will map
these files into the project's canonical processed schema.

Design goals:
    - Never modify data/raw/2026-27
    - Never silently overwrite historical files
    - Retry transient HTTP failures
    - Validate downloaded CSVs
    - Write files atomically
    - Produce a machine-readable manifest
    - Support resume/re-run
    - Fail clearly on partial/corrupt downloads

Usage:
    python scripts/data/collect_historical_seasons.py

    python scripts/data/collect_historical_seasons.py --seasons 2024-25 2025-26

    python scripts/data/collect_historical_seasons.py --force

    python scripts/data/collect_historical_seasons.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


VERSION = "1.0.0"

DEFAULT_SEASONS = (
    "2021-22",
    "2022-23",
    "2023-24",
    "2024-25",
    "2025-26",
)

SEASON_RE = re.compile(r"^(20\d{2})-(\d{2})$")

# This archive contains FPL data scraped from the official API.
SOURCE_REPO = "https://github.com/imadeddine-belkat/Premier-League-Stats"
RAW_BASE = (
    "https://raw.githubusercontent.com/"
    "imadeddine-belkat/Premier-League-Stats/main/"
)

FILES = {
    "player_gameweek.csv": (
        "fpl_scraper/fpl_stats/_merged/players/{season}_all_players_gw.csv"
    ),
    "fixtures.csv": (
        "fpl_scraper/fpl_stats/fixtures/{season}_all_fixtures.csv"
    ),
    "players_index.json": (
        "fpl_scraper/fpl_stats/_index/_players_index.json"
    ),
    "teams_index.json": (
        "fpl_scraper/fpl_stats/_index/_teams_index.json"
    ),
}

LOG = logging.getLogger("historical_collector")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect completed historical FPL seasons."
    )
    parser.add_argument(
        "--seasons",
        nargs="+",
        default=list(DEFAULT_SEASONS),
        help="Seasons to collect, e.g. 2021-22 2022-23.",
    )
    parser.add_argument(
        "--project-root",
        default=None,
        help="Project root. Defaults to the parent of scripts/.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Redownload existing source files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned downloads without downloading.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=4,
        help="Retries per file after transient failures.",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=2.0,
        help="Initial retry delay in seconds; exponential backoff is used.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only warnings/errors.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args()


def configure_logging(args: argparse.Namespace) -> None:
    level = logging.DEBUG if args.verbose else logging.INFO
    if args.quiet:
        level = logging.WARNING

    logging.basicConfig(
        level=level,
        format="[%(levelname)-8s] %(message)s",
    )


def project_root_from_script() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_root(args: argparse.Namespace) -> Path:
    if args.project_root:
        return Path(args.project_root).expanduser().resolve()
    return project_root_from_script()


def validate_season(season: str) -> None:
    if not SEASON_RE.fullmatch(season):
        raise ValueError(
            f"Invalid season '{season}'. Expected YYYY-YY, e.g. 2024-25."
        )


def validate_seasons(seasons: Iterable[str]) -> list[str]:
    result = []
    seen = set()

    for season in seasons:
        validate_season(season)
        if season not in seen:
            result.append(season)
            seen.add(season)

    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_download(
    url: str,
    destination: Path,
    timeout: int,
    retries: int,
    retry_delay: float,
) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists():
        raise FileExistsError(destination)

    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        temp_path = destination.with_suffix(
            destination.suffix + f".part-{os.getpid()}"
        )

        try:
            LOG.info(
                "Downloading [%d/%d]: %s",
                attempt,
                retries,
                url,
            )

            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "FPL-AI-Weekly-Squad-Prediction/"
                        f"{VERSION}"
                    )
                },
            )

            started = time.monotonic()

            with urllib.request.urlopen(
                request,
                timeout=timeout,
            ) as response, temp_path.open("wb") as out:
                status = getattr(response, "status", 200)

                if status != 200:
                    raise RuntimeError(
                        f"HTTP status {status} for {url}"
                    )

                shutil.copyfileobj(response, out)

            size = temp_path.stat().st_size

            if size == 0:
                raise RuntimeError(
                    f"Downloaded file is empty: {url}"
                )

            temp_path.replace(destination)

            elapsed = time.monotonic() - started

            return {
                "url": url,
                "bytes": size,
                "sha256": sha256_file(destination),
                "download_seconds": round(elapsed, 3),
            }

        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            OSError,
            RuntimeError,
        ) as exc:
            last_error = exc

            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass

            if attempt < retries:
                delay = retry_delay * (2 ** (attempt - 1))
                LOG.warning(
                    "Download failed: %s; retrying in %.1fs",
                    exc,
                    delay,
                )
                time.sleep(delay)

    raise RuntimeError(
        f"Failed to download after {retries} attempts: "
        f"{url}; last error: {last_error}"
    )


def read_csv_profile(path: Path) -> dict:
    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration:
            raise RuntimeError(f"CSV is empty: {path}")

        if not header:
            raise RuntimeError(f"CSV has no columns: {path}")

        rows = 0
        gameweeks = set()

        normalized_header = {
            str(column).strip().lower(): index
            for index, column in enumerate(header)
        }

        gw_index = None
        for candidate in ("gw", "gameweek", "event"):
            if candidate in normalized_header:
                gw_index = normalized_header[candidate]
                break

        for row in reader:
            rows += 1
            if gw_index is not None and gw_index < len(row):
                value = row[gw_index].strip()
                if value:
                    gameweeks.add(value)

    return {
        "rows": rows,
        "columns": len(header),
        "header": header,
        "gameweeks": sorted(
            gameweeks,
            key=lambda x: int(x) if x.isdigit() else x,
        ),
    }


def read_json_profile(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    if isinstance(payload, dict):
        return {
            "type": "object",
            "keys": sorted(payload.keys()),
        }

    if isinstance(payload, list):
        return {
            "type": "array",
            "items": len(payload),
        }

    return {
        "type": type(payload).__name__,
    }


def validate_season_files(
    season: str,
    directory: Path,
) -> dict:
    required = list(FILES.keys())

    missing = [
        filename
        for filename in required
        if not (directory / filename).exists()
    ]

    if missing:
        raise RuntimeError(
            f"{season}: missing required files: {', '.join(missing)}"
        )

    player_profile = read_csv_profile(
        directory / "player_gameweek.csv"
    )
    fixture_profile = read_csv_profile(
        directory / "fixtures.csv"
    )
    players_profile = read_json_profile(
        directory / "players_index.json"
    )
    teams_profile = read_json_profile(
        directory / "teams_index.json"
    )

    if player_profile["rows"] == 0:
        raise RuntimeError(
            f"{season}: player_gameweek.csv contains zero rows."
        )

    if fixture_profile["rows"] == 0:
        raise RuntimeError(
            f"{season}: fixtures.csv contains zero rows."
        )

    return {
        "player_gameweek": player_profile,
        "fixtures": fixture_profile,
        "players_index": players_profile,
        "teams_index": teams_profile,
    }


def build_urls(season: str) -> dict[str, str]:
    return {
        filename: RAW_BASE + template.format(season=season)
        for filename, template in FILES.items()
    }


def collect_season(
    root: Path,
    season: str,
    args: argparse.Namespace,
) -> dict:
    # Explicit safety guard: this collector must never modify the live season.
    if season == "2026-27":
        raise RuntimeError(
            "2026-27 is the live season and is protected. "
            "This collector only handles completed historical seasons."
        )

    output_dir = (
        root
        / "data"
        / "raw"
        / season
        / "historical_source"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    urls = build_urls(season)

    LOG.info("")
    LOG.info("=" * 72)
    LOG.info("HISTORICAL SEASON: %s", season)
    LOG.info("=" * 72)
    LOG.info("Output: %s", output_dir)

    if args.dry_run:
        for filename, url in urls.items():
            status = "EXISTS" if (output_dir / filename).exists() else "DOWNLOAD"
            LOG.info("%-20s %-10s %s", filename, status, url)

        return {
            "season": season,
            "status": "DRY_RUN",
            "output_directory": str(output_dir),
            "files": urls,
        }

    downloaded = {}
    skipped = {}

    for filename, url in urls.items():
        destination = output_dir / filename

        if destination.exists() and not args.force:
            LOG.info("Exists; keeping: %s", destination)
            skipped[filename] = {
                "path": str(destination),
                "sha256": sha256_file(destination),
                "bytes": destination.stat().st_size,
            }
            continue

        if destination.exists() and args.force:
            destination.unlink()

        downloaded[filename] = atomic_download(
            url=url,
            destination=destination,
            timeout=args.timeout,
            retries=args.retries,
            retry_delay=args.retry_delay,
        )

    profiles = validate_season_files(
        season=season,
        directory=output_dir,
    )

    manifest = {
        "schema_version": "1.0.0",
        "collector_version": VERSION,
        "season": season,
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "repository": SOURCE_REPO,
            "raw_base": RAW_BASE,
            "description": (
                "Historical FPL gameweek data scraped from the "
                "official FPL API by the source repository."
            ),
        },
        "output_directory": str(output_dir),
        "downloaded": downloaded,
        "skipped_existing": skipped,
        "profiles": profiles,
        "notes": [
            "This is archive/source data, not a synthetic official API snapshot.",
            "The existing 2026-27 live raw dataset was not modified.",
            "xP should not be used as an unshifted predictor because archived "
            "post-gameweek values may contain lookahead information.",
            "Historical normalization into the project's canonical processed "
            "schema is a separate next-stage task.",
        ],
    }

    manifest_path = output_dir / "collection_manifest.json"
    temp_manifest = manifest_path.with_suffix(".json.part")

    temp_manifest.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )
    temp_manifest.replace(manifest_path)

    LOG.info("Validation PASSED: %s", season)
    LOG.info(
        "Player-GW rows : %s",
        profiles["player_gameweek"]["rows"],
    )
    LOG.info(
        "Fixtures       : %s",
        profiles["fixtures"]["rows"],
    )
    LOG.info(
        "Gameweeks      : %s",
        ", ".join(profiles["player_gameweek"]["gameweeks"]),
    )
    LOG.info("Manifest       : %s", manifest_path)

    return {
        "season": season,
        "status": "PASS",
        "output_directory": str(output_dir),
        "profiles": profiles,
        "manifest": str(manifest_path),
    }


def main() -> int:
    args = parse_args()
    configure_logging(args)

    seasons = validate_seasons(args.seasons)
    root = resolve_root(args)

    LOG.info("FPL HISTORICAL DATA COLLECTOR")
    LOG.info("=" * 72)
    LOG.info("Collector version : %s", VERSION)
    LOG.info("Project root      : %s", root)
    LOG.info("Seasons           : %s", ", ".join(seasons))
    LOG.info("Live season       : 2026-27 (PROTECTED)")
    LOG.info("Source            : %s", SOURCE_REPO)

    results = []
    failures = []

    for season in seasons:
        try:
            results.append(
                collect_season(
                    root=root,
                    season=season,
                    args=args,
                )
            )
        except Exception as exc:
            LOG.error(
                "FAILED: %s -> %s",
                season,
                exc,
            )
            failures.append(
                {
                    "season": season,
                    "error": str(exc),
                }
            )

    LOG.info("")
    LOG.info("=" * 72)
    LOG.info("HISTORICAL COLLECTION SUMMARY")
    LOG.info("=" * 72)

    for result in results:
        LOG.info(
            "%-10s %s",
            result["season"],
            result["status"],
        )

    for failure in failures:
        LOG.error(
            "%-10s FAIL: %s",
            failure["season"],
            failure["error"],
        )

    if failures:
        LOG.error(
            "Collection completed with %d failure(s).",
            len(failures),
        )
        return 1

    LOG.info("All requested historical seasons completed successfully.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        LOG.error("Interrupted by user.")
        raise SystemExit(130)
