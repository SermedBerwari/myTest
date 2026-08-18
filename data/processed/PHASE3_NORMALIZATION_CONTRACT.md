# Phase 3 Historical Normalization Contract

## Canonical command

```powershell
py scripts/normalize_historical.py --seasons 2022-23 2023-24 2024-25 2025-26
```

The canonical command delegates to `scripts/data/normalize_historical_seasons_v1_3.py`. The live season `2026-27` is protected and must not be normalized as historical data. Use `--dry-run` to inspect execution without writing outputs.

## Inputs

Each season must provide `data/raw/<season>/historical_source/player_gameweek.csv` and `data/raw/<season>/historical_source/fixtures.csv`.

## Outputs

Normalized outputs are written under `data/processed/<season>/historical/` and include `player_gameweek.csv`, `players.csv`, `teams.csv`, `fixtures.csv`, `gameweeks.csv`, `player_season_history.csv`, and `normalization_manifest.json`.

## Policy

The normalizer validates required keys, fixture/gameweek mappings, unique identifiers, row counts, and manifest metadata. Superseded variants are archived under `old documents/phase3_archived_variants/`.
