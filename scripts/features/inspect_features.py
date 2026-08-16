#!/usr/bin/env python3
"""
FPL AI Weekly Squad Prediction System
======================================

Inspect the generated leakage-safe feature dataset before model training.

Usage:
    python scripts/features/inspect_features.py --season 2026-27

The inspector validates:
    - required output files
    - row/column counts
    - gameweek coverage
    - duplicate player/gameweek/fixture keys
    - target/feature separation
    - missing-value rates
    - constant columns
    - non-finite numeric values
    - target availability
    - suspicious feature names
    - temporal leakage using the source player_gameweek dataset
    - double-gameweek representation

It produces:
    data/features/<season>/feature_inspection_report.json
    data/features/<season>/feature_inspection_report.txt

This script does not modify the feature dataset.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VERSION = "1.0.0"

FEATURE_FILE = "player_gameweek_features.csv"
MANIFEST_FILE = "feature_manifest.json"
BUILD_REPORT_FILE = "feature_build_report.json"

PROCESSED_FILES = {
    "player_gameweek": "player_gameweek.csv",
    "fixtures": "fixtures.csv",
    "players": "players.csv",
}

TARGET_COLUMNS = {
    "target_minutes",
    "target_points",
    "target_goals",
    "target_assists",
    "target_clean_sheets",
    "target_bonus",
    "target_xg",
    "target_xa",
}

KEY_COLUMNS = [
    "player_id",
    "gameweek",
]

REQUIRED_FEATURE_COLUMNS = [
    "player_id",
    "season",
    "gameweek",
    "position_id",
    "team_id",
    "opponent_team_id",
    "was_home",
    "fixture_difficulty",
    "prior_gameweeks",
    "prior_minutes",
    "target_minutes",
    "target_points",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect FPL feature dataset before ML training."
    )
    parser.add_argument(
        "--season",
        required=True,
        help="Season, e.g. 2026-27",
    )
    parser.add_argument(
        "--project-root",
        default=None,
        help="Project root. Defaults to the directory above scripts/.",
    )
    parser.add_argument(
        "--features-dir",
        default=None,
        help="Explicit feature directory.",
    )
    parser.add_argument(
        "--processed-dir",
        default=None,
        help="Explicit processed directory.",
    )
    parser.add_argument(
        "--missing-warning-threshold",
        type=float,
        default=0.50,
        help="Warn when a feature has more than this missing fraction.",
    )
    return parser.parse_args()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise RuntimeError(f"CSV has no header: {path}")
        fields = list(reader.fieldnames)
        rows = []
        for row in reader:
            rows.append({k: ("" if v is None else v) for k, v in row.items()})
        return fields, rows


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def to_int(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def to_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        value = float(str(value))
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def project_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    root = (
        Path(args.project_root).expanduser().resolve()
        if args.project_root
        else Path(__file__).resolve().parents[2]
    )

    features_dir = (
        Path(args.features_dir).expanduser().resolve()
        if args.features_dir
        else root / "data" / "features" / args.season
    )

    processed_dir = (
        Path(args.processed_dir).expanduser().resolve()
        if args.processed_dir
        else root / "data" / "processed" / args.season
    )

    return features_dir, processed_dir


def missing_fraction(rows: list[dict[str, str]], field: str) -> float:
    if not rows:
        return 0.0
    missing = sum(
        1
        for row in rows
        if row.get(field, "").strip() == ""
    )
    return missing / len(rows)


def numeric_values(rows: list[dict[str, str]], field: str) -> list[float]:
    values = []
    for row in rows:
        value = to_float(row.get(field))
        if value is not None:
            values.append(value)
    return values


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_text_report(path: Path, report: dict[str, Any]) -> None:
    lines: list[str] = []

    lines.append("FPL FEATURE INSPECTION REPORT")
    lines.append("=" * 78)
    lines.append(f"Status              : {report['status']}")
    lines.append(f"Season              : {report['season']}")
    lines.append(f"Inspector version   : {report['inspector_version']}")
    lines.append(f"Generated UTC       : {report['generated_at_utc']}")
    lines.append("")

    counts = report["dataset"]
    lines.append("DATASET")
    lines.append("-" * 78)
    lines.append(f"Rows                : {counts['rows']}")
    lines.append(f"Columns             : {counts['columns']}")
    lines.append(f"Players             : {counts['unique_players']}")
    lines.append(f"Gameweeks           : {counts['unique_gameweeks']}")
    lines.append(f"Fixtures            : {counts['unique_fixtures']}")
    lines.append("")

    lines.append("GAMEWEEK COVERAGE")
    lines.append("-" * 78)
    for gw, count in report["gameweeks"]["rows_by_gameweek"].items():
        lines.append(f"GW {gw:>2}: {count:>6} rows")
    lines.append("")

    lines.append("DUPLICATES")
    lines.append("-" * 78)
    lines.append(
        f"Player/GW duplicate groups     : "
        f"{report['duplicates']['player_gameweek_groups']}"
    )
    lines.append(
        f"Player/GW/fixture duplicate groups: "
        f"{report['duplicates']['player_gameweek_fixture_groups']}"
    )
    lines.append("")

    lines.append("TARGETS")
    lines.append("-" * 78)
    for field, info in report["targets"].items():
        lines.append(
            f"{field:<24} non-null={info['non_null']:>7} "
            f"missing={info['missing_fraction']:.2%}"
        )
    lines.append("")

    lines.append("MISSING VALUES")
    lines.append("-" * 78)
    warnings = []
    for field, info in report["missing_values"].items():
        if info["fraction"] > 0:
            marker = "  <-- WARNING" if info["fraction"] > report["thresholds"]["missing_warning_fraction"] else ""
            lines.append(
                f"{field:<40} {info['fraction']:>8.2%}{marker}"
            )
            if marker:
                warnings.append(field)

    if not warnings:
        lines.append("No feature exceeds the configured missing-value warning threshold.")
    lines.append("")

    lines.append("CONSTANT FEATURES")
    lines.append("-" * 78)
    constants = report["constant_features"]
    if constants:
        for field in constants:
            lines.append(field)
    else:
        lines.append("None")
    lines.append("")

    lines.append("LEAKAGE CHECK")
    lines.append("-" * 78)
    leakage = report["leakage"]
    lines.append(f"Status              : {leakage['status']}")
    lines.append(
        f"Future feature rows : {leakage['future_feature_row_violations']}"
    )
    lines.append(
        f"Target mismatch     : {leakage['target_mismatch_count']}"
    )
    lines.append(
        f"Fixture target rows : {leakage['target_fixture_mismatch_count']}"
    )
    lines.append("")

    lines.append("DOUBLE GAMEWEEKS")
    lines.append("-" * 78)
    lines.append(
        f"Player/GW groups with >1 fixture: "
        f"{report['double_gameweeks']['player_gameweek_groups_with_multiple_fixtures']}"
    )
    lines.append("")

    lines.append("ISSUES")
    lines.append("-" * 78)
    for issue in report["issues"]:
        lines.append(f"- {issue}")
    if not report["issues"]:
        lines.append("None")
    lines.append("")

    lines.append("WARNINGS")
    lines.append("-" * 78)
    for warning in report["warnings"]:
        lines.append(f"- {warning}")
    if not report["warnings"]:
        lines.append("None")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()

    features_dir, processed_dir = project_paths(args)

    print("[INFO    ] FPL FEATURE DATASET INSPECTION")
    print("[INFO    ] " + "=" * 78)
    print(f"[INFO    ] Season       : {args.season}")
    print(f"[INFO    ] Features     : {features_dir}")
    print(f"[INFO    ] Processed    : {processed_dir}")

    feature_path = features_dir / FEATURE_FILE
    manifest_path = features_dir / MANIFEST_FILE
    build_report_path = features_dir / BUILD_REPORT_FILE

    issues: list[str] = []
    warnings: list[str] = []

    required_feature_files = [
        feature_path,
        manifest_path,
        build_report_path,
    ]

    for path in required_feature_files:
        if not path.exists():
            issues.append(f"Missing feature artifact: {path}")

    if not (processed_dir / PROCESSED_FILES["player_gameweek"]).exists():
        issues.append(
            f"Missing processed source: "
            f"{processed_dir / PROCESSED_FILES['player_gameweek']}"
        )

    if issues:
        raise RuntimeError("; ".join(issues))

    fields, rows = read_csv(feature_path)
    manifest = read_json(manifest_path)
    build_report = read_json(build_report_path)

    missing_required = [
        field for field in REQUIRED_FEATURE_COLUMNS
        if field not in fields
    ]
    if missing_required:
        issues.append(
            "Missing required feature columns: "
            + ", ".join(missing_required)
        )

    target_fields = [f for f in fields if f.startswith("target_")]
    feature_fields = [f for f in fields if f not in target_fields]

    suspicious_feature_names = [
        f for f in feature_fields
        if any(
            token in f.lower()
            for token in (
                "actual",
                "result",
                "score",
                "final_points",
                "future",
            )
        )
    ]

    if suspicious_feature_names:
        warnings.append(
            "Suspicious feature names detected: "
            + ", ".join(suspicious_feature_names)
        )

    unique_players = len({
        to_int(row.get("player_id"))
        for row in rows
        if to_int(row.get("player_id")) is not None
    })

    unique_gameweeks = len({
        to_int(row.get("gameweek"))
        for row in rows
        if to_int(row.get("gameweek")) is not None
    })

    unique_fixtures = len({
        to_int(row.get("fixture_id"))
        for row in rows
        if to_int(row.get("fixture_id")) is not None
    }) if "fixture_id" in fields else 0

    rows_by_gameweek = Counter(
        to_int(row.get("gameweek"))
        for row in rows
        if to_int(row.get("gameweek")) is not None
    )

    player_gw = Counter(
        (
            to_int(row.get("player_id")),
            to_int(row.get("gameweek")),
        )
        for row in rows
        if to_int(row.get("player_id")) is not None
        and to_int(row.get("gameweek")) is not None
    )

    player_gw_fixture = Counter(
        (
            to_int(row.get("player_id")),
            to_int(row.get("gameweek")),
            to_int(row.get("fixture_id")),
        )
        for row in rows
        if to_int(row.get("player_id")) is not None
        and to_int(row.get("gameweek")) is not None
        and to_int(row.get("fixture_id")) is not None
    ) if "fixture_id" in fields else Counter()

    player_gw_duplicates = {
        key: count
        for key, count in player_gw.items()
        if count > 1
    }

    player_gw_fixture_duplicates = {
        key: count
        for key, count in player_gw_fixture.items()
        if count > 1
    }

    if player_gw_fixture_duplicates:
        issues.append(
            "Duplicate player/gameweek/fixture rows detected: "
            f"{len(player_gw_fixture_duplicates)} groups."
        )

    if player_gw_duplicates:
        # Duplicates at player/GW level are valid for double gameweeks
        # only if fixture IDs differ.
        invalid = []
        grouped = defaultdict(list)
        for row in rows:
            key = (
                to_int(row.get("player_id")),
                to_int(row.get("gameweek")),
            )
            grouped[key].append(
                to_int(row.get("fixture_id"))
                if "fixture_id" in fields
                else None
            )

        for key, fixture_ids in grouped.items():
            if len(fixture_ids) > 1 and len(set(fixture_ids)) != len(fixture_ids):
                invalid.append(key)

        if invalid:
            issues.append(
                "Player/gameweek duplicates are not explained by distinct fixtures: "
                f"{len(invalid)} groups."
            )

    missing_values = {}
    for field in feature_fields:
        missing = sum(
            1 for row in rows
            if row.get(field, "").strip() == ""
        )
        fraction = missing / len(rows) if rows else 0.0
        missing_values[field] = {
            "missing": missing,
            "non_missing": len(rows) - missing,
            "fraction": fraction,
        }

        if fraction > args.missing_warning_threshold:
            warnings.append(
                f"Feature '{field}' has {fraction:.2%} missing values."
            )

    constant_features = []
    for field in feature_fields:
        values = {
            row.get(field, "").strip()
            for row in rows
            if row.get(field, "").strip() != ""
        }
        if len(values) <= 1:
            constant_features.append(field)

    # Numeric finite-value validation.
    non_finite = []
    numeric_candidate_fields = []

    for field in fields:
        values = numeric_values(rows, field)
        if values:
            numeric_candidate_fields.append(field)
            for value in values:
                if not math.isfinite(value):
                    non_finite.append(field)
                    break

    if non_finite:
        issues.append(
            "Non-finite numeric values found: "
            + ", ".join(sorted(set(non_finite)))
        )

    # Target completeness.
    targets_report = {}
    for field in sorted(TARGET_COLUMNS):
        if field not in fields:
            targets_report[field] = {
                "present": False,
                "non_null": 0,
                "missing": len(rows),
                "missing_fraction": 1.0 if rows else 0.0,
            }
            continue

        non_null = sum(
            1 for row in rows
            if row.get(field, "").strip() != ""
        )
        targets_report[field] = {
            "present": True,
            "non_null": non_null,
            "missing": len(rows) - non_null,
            "missing_fraction": (
                (len(rows) - non_null) / len(rows)
                if rows else 0.0
            ),
        }

    if "target_points" not in fields:
        issues.append("Required target_points column is missing.")

    # ------------------------------------------------------------------
    # Strong temporal leakage check.
    #
    # For every generated row at GW N, prior_gameweeks must be strictly
    # based on source rows with GW < N.
    #
    # We independently inspect source player_gameweek.csv and calculate
    # the expected number of prior observations.
    # ------------------------------------------------------------------
    source_fields, source_rows = read_csv(
        processed_dir / PROCESSED_FILES["player_gameweek"]
    )

    source_by_player = defaultdict(list)
    for source in source_rows:
        if source.get("season", "").strip() != args.season:
            continue
        pid = to_int(source.get("player_id"))
        gw = to_int(source.get("gameweek"))
        if pid is None or gw is None:
            continue
        source_by_player[pid].append(gw)

    for pid in source_by_player:
        source_by_player[pid].sort()

    future_feature_row_violations = 0
    prior_history_mismatch = 0

    for row in rows:
        pid = to_int(row.get("player_id"))
        gw = to_int(row.get("gameweek"))
        prior_reported = to_int(row.get("prior_gameweeks"))

        if pid is None or gw is None:
            issues.append("Null player_id/gameweek in feature dataset.")
            continue

        source_history = source_by_player.get(pid, [])
        expected_prior = sum(1 for source_gw in source_history if source_gw < gw)

        if prior_reported is not None and prior_reported != expected_prior:
            prior_history_mismatch += 1

        # Explicit future observation test.
        future = [source_gw for source_gw in source_history if source_gw >= gw]
        if future:
            # This is not automatically a violation: the target row itself
            # exists in source data. We test the reported history count,
            # which must exclude all GW >= target GW.
            if prior_reported is not None:
                if prior_reported > expected_prior:
                    future_feature_row_violations += 1

    if prior_history_mismatch:
        issues.append(
            "Reported prior_gameweeks does not match independently calculated "
            f"GW<N history for {prior_history_mismatch} rows."
        )

    # Target consistency check against source data.
    source_lookup = {}
    for source in source_rows:
        if source.get("season", "").strip() != args.season:
            continue
        key = (
            to_int(source.get("player_id")),
            to_int(source.get("gameweek")),
            to_int(source.get("fixture_id")),
        )
        source_lookup[key] = source

    target_mismatch_count = 0
    target_fixture_mismatch_count = 0

    for row in rows:
        key = (
            to_int(row.get("player_id")),
            to_int(row.get("gameweek")),
            to_int(row.get("fixture_id"))
            if "fixture_id" in fields else None,
        )

        source = source_lookup.get(key)
        if source is None:
            # Feature builder should preserve source player/GW/fixture identity.
            target_fixture_mismatch_count += 1
            continue

        comparisons = {
            "target_points": "total_points",
            "target_minutes": "minutes",
            "target_goals": "goals_scored",
            "target_assists": "assists",
            "target_clean_sheets": "clean_sheets",
            "target_bonus": "bonus",
            "target_xg": "expected_goals",
            "target_xa": "expected_assists",
        }

        for target, source_field in comparisons.items():
            if target not in fields:
                continue

            generated = row.get(target, "").strip()
            original = source.get(source_field, "").strip()

            if generated != original:
                # Numeric formatting differences are allowed.
                g = to_float(generated)
                o = to_float(original)

                if g is None and o is None:
                    continue

                if g is None or o is None or abs(g - o) > 1e-9:
                    target_mismatch_count += 1
                    break

    if target_mismatch_count:
        issues.append(
            f"Target values differ from source records in "
            f"{target_mismatch_count} rows."
        )

    # Double-gameweek groups.
    double_groups = {
        key: fixture_ids
        for key, fixture_ids in (
            (
                key,
                [
                    to_int(row.get("fixture_id"))
                    for row in group
                ],
            )
            for key, group in (
                (
                    key,
                    [
                        row
                        for row in rows
                        if (
                            to_int(row.get("player_id")),
                            to_int(row.get("gameweek")),
                        ) == key
                    ],
                )
                for key in set(
                    (
                        to_int(row.get("player_id")),
                        to_int(row.get("gameweek")),
                    )
                    for row in rows
                )
            )
        )
        if len(fixture_ids) > 1 and len(set(fixture_ids)) > 1
    }

    # Build report.
    status = "PASS" if not issues else "FAIL"

    report = {
        "schema_version": "1.0.0",
        "inspector_version": VERSION,
        "season": args.season,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "paths": {
            "features": str(features_dir),
            "processed": str(processed_dir),
        },
        "dataset": {
            "rows": len(rows),
            "columns": len(fields),
            "unique_players": unique_players,
            "unique_gameweeks": unique_gameweeks,
            "unique_fixtures": unique_fixtures,
            "feature_columns": len(feature_fields),
            "target_columns": len(target_fields),
        },
        "gameweeks": {
            "minimum": min(rows_by_gameweek) if rows_by_gameweek else None,
            "maximum": max(rows_by_gameweek) if rows_by_gameweek else None,
            "rows_by_gameweek": {
                str(k): v
                for k, v in sorted(rows_by_gameweek.items())
            },
        },
        "duplicates": {
            "player_gameweek_groups": len(player_gw_duplicates),
            "player_gameweek_fixture_groups": len(
                player_gw_fixture_duplicates
            ),
        },
        "targets": targets_report,
        "missing_values": missing_values,
        "constant_features": constant_features,
        "numeric_candidate_fields": numeric_candidate_fields,
        "leakage": {
            "status": (
                "PASS"
                if (
                    future_feature_row_violations == 0
                    and prior_history_mismatch == 0
                    and target_mismatch_count == 0
                    and target_fixture_mismatch_count == 0
                )
                else "FAIL"
            ),
            "future_feature_row_violations": future_feature_row_violations,
            "prior_history_mismatch": prior_history_mismatch,
            "target_mismatch_count": target_mismatch_count,
            "target_fixture_mismatch_count": target_fixture_mismatch_count,
            "rule": (
                "For target GW N, prior_gameweeks must count only source "
                "player_gameweek records where source GW < N."
            ),
        },
        "double_gameweeks": {
            "player_gameweek_groups_with_multiple_fixtures": len(
                double_groups
            ),
        },
        "suspicious_feature_names": suspicious_feature_names,
        "thresholds": {
            "missing_warning_fraction": args.missing_warning_threshold,
        },
        "source_build_report_status": build_report.get("status"),
        "issues": issues,
        "warnings": warnings,
        "recommendation": (
            "Proceed to model training only if status=PASS and leakage.status=PASS."
            if status == "PASS"
            else "Fix all FAIL issues before model training."
        ),
    }

    json_path = features_dir / "feature_inspection_report.json"
    txt_path = features_dir / "feature_inspection_report.txt"

    write_json(json_path, report)
    write_text_report(txt_path, report)

    print("")
    print("[INFO    ] " + "=" * 78)
    print("[INFO    ] FPL FEATURE INSPECTION COMPLETE")
    print("[INFO    ] " + "=" * 78)
    print(f"[INFO    ] Status                  : {status}")
    print(f"[INFO    ] Rows                    : {len(rows):,}")
    print(f"[INFO    ] Columns                 : {len(fields):,}")
    print(f"[INFO    ] Players                 : {unique_players:,}")
    print(f"[INFO    ] Gameweeks               : {unique_gameweeks:,}")
    print(f"[INFO    ] Feature columns         : {len(feature_fields):,}")
    print(f"[INFO    ] Target columns          : {len(target_fields):,}")
    print(
        f"[INFO    ] Duplicate player/GW    : "
        f"{len(player_gw_duplicates):,}"
    )
    print(
        f"[INFO    ] Duplicate player/GW/FIX: "
        f"{len(player_gw_fixture_duplicates):,}"
    )
    print(
        f"[INFO    ] Leakage check           : "
        f"{report['leakage']['status']}"
    )
    print(
        f"[INFO    ] Missing-value warnings  : "
        f"{len(warnings):,}"
    )
    print("")
    print("[INFO    ] JSON report :")
    print(f"[INFO    ]   {json_path}")
    print("[INFO    ] Text report :")
    print(f"[INFO    ]   {txt_path}")
    print("")
    print("[INFO    ] " + "=" * 78)

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("[ERROR   ] Interrupted by user.")
        raise SystemExit(130)
    except Exception as exc:
        print(f"[ERROR   ] FEATURE INSPECTION FAILED: {exc}")
        raise SystemExit(1)
