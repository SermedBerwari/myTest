"""
build_training_dataset_v1.py
============================
Concatenates multi-season leakage-safe feature CSVs into a single unified
training dataset for model training and evaluation.

Input  : data/features/<season>/player_gameweek_features.csv
Output : data/processed/training_dataset_v1.csv
         data/processed/training_dataset_v1_manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

VERSION = "1.0.0"

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
DEFAULT_SEASONS = ["2022-23", "2023-24", "2024-25", "2025-26"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate seasonal features into unified training dataset."
    )
    parser.add_argument(
        "--seasons",
        nargs="+",
        default=DEFAULT_SEASONS,
        help="List of seasons to include, e.g. 2022-23 2023-24",
    )
    parser.add_argument(
        "--project-root",
        default=None,
        help="Project root. Defaults to parent of scripts/",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    seasons = args.seasons

    root = (
        Path(args.project_root).resolve()
        if args.project_root
        else Path(__file__).resolve().parents[2]
    )

    output_dir = root / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)

    dfs = []
    season_counts = {}

    print("=" * 72)
    print(f"BUILDING UNIFIED TRAINING DATASET (v{VERSION})")
    print("=" * 72)

    for season in seasons:
        feature_path = root / "data" / "features" / season / "player_gameweek_features.csv"
        if not feature_path.exists():
            raise FileNotFoundError(f"Feature dataset not found: {feature_path}")

        df = pd.read_csv(feature_path)
        dfs.append(df)
        season_counts[season] = len(df)
        print(f"Loaded {season}: {len(df)} rows, {len(df.columns)} columns")

    unified = pd.concat(dfs, ignore_index=True)

    # Deduplicate exact duplicate rows if any exist
    before_len = len(unified)
    unified = unified.drop_duplicates().reset_index(drop=True)
    after_len = len(unified)
    if before_len > after_len:
        print(f"Removed {before_len - after_len} exact duplicate rows.")

    print(f"Total rows: {len(unified)}")
    print(f"Total columns: {len(unified.columns)}")

    # Write output CSV
    output_path = output_dir / "training_dataset_v1.csv"
    unified.to_csv(output_path, index=False)
    print(f"\nSaved training dataset to: {output_path}")

    # Manifest
    manifest = {
        "dataset_name": "training_dataset_v1",
        "version": VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "seasons_included": seasons,
        "total_rows": len(unified),
        "total_columns": len(unified.columns),
        "row_breakdown_by_season": season_counts,
        "target_column": "target_points",
        "key_columns": ["season", "player_id", "fixture_id"],
        "columns": unified.columns.tolist(),
    }
    manifest["checksums"] = {
        "algorithm": "sha256",
        "dataset": {
            "path": "data/processed/training_dataset_v1.csv",
            "sha256": sha256_file(output_path),
        },
        "source_feature_manifests": {
            season: {
                "path": f"data/features/{season}/feature_manifest.json",
                "sha256": sha256_file(root / "data" / "features" / season / "feature_manifest.json"),
            }
            for season in seasons
        },
    }


    reproducibility_payload = {
        "version": VERSION,
        "seasons": seasons,
        "columns": unified.columns.tolist(),
        "checksums": manifest["checksums"],
    }
    manifest["reproducibility_signature"] = hashlib.sha256(
        json.dumps(reproducibility_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()

    manifest_path = output_dir / "training_dataset_v1_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Saved dataset manifest to: {manifest_path}")
    print("=" * 72)


if __name__ == "__main__":
    main()


