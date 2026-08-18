# Phase 2–3 Dependency Audit

| Phase | Checklist item | Status | Evidence | Required next action |
|---:|---|---|---|---|
| 2 | Define release-blocking versus acceptable warnings | **SATISFIED** | data/processed/DATA_VALIDATION_RELEASE_POLICY.md | Keep policy linked to the Phase 2 ingestion gate. |
| 2 | Add automated ingestion regression tests | **MISSING** | No dedicated raw-data regression test module found. | Add tests for snapshot structure, required fields, IDs, fixtures, warnings, and strict/non-strict exit behavior. |
| 2 | Add freshness checks | **PARTIAL** | validate_raw_data.py validates snapshots but no dedicated freshness contract was found. | Add max-age and timestamp-order assertions with a documented clock/tolerance policy. |
| 2 | Define canonical weekly data-refresh command | **PARTIAL** | Pipeline and CLI entry points exist, but no Phase 2 canonical refresh command document was found. | Document one command covering capture, validation, and immutable snapshot naming. |
| 2 | Preserve immutable pre-deadline snapshots | **SATISFIED** | Timestamped data/raw/2026-27 bootstrap, fixtures, and player snapshots exist. | Keep write-once snapshot behavior and test that existing snapshots are not overwritten. |
| 3 | Establish one canonical normalization command | **MISSING** | Multiple normalization variants exist under scripts/data. | Create one documented wrapper command and designate variants as archived compatibility tools. |
| 3 | Archive obsolete preparation variants | **PARTIAL** | An archive exists, but multiple historical preparation variants remain in the operational tree. | Move superseded variants into the archive and retain only the canonical path. |
| 3 | Add normalization regression tests | **MISSING** | No dedicated normalization regression test module found. | Add fixture-based tests for row counts, keys, season/gameweek ordering, and rerun determinism. |
| 3 | Document exact input/output contracts | **PARTIAL** | Dataset and feature manifests exist, but no dedicated normalization contract document was found. | Document raw input paths, normalized schemas, output paths, versions, and failure semantics. |

## Summary
Satisfied: 2; partial: 4; missing: 3.
