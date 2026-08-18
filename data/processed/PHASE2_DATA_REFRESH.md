# Phase 2 Canonical Weekly Data Refresh

The canonical weekly refresh command is:

```powershell
py scripts/weekly_data_refresh.py --season 2026-27
```

The command collects timestamped bootstrap, fixture, and player-history snapshots, then runs the release-data policy gate. Existing timestamped snapshots are write-once and cannot be overwritten. Use `--dry-run` to inspect the commands without network access or filesystem writes.

The release-warning policy is documented in `data/processed/DATA_VALIDATION_RELEASE_POLICY.md`. Only zero-error validation with the explicitly documented `snapshot_coverage` warning is accepted for release.
