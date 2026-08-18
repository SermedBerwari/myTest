# Phase 4 Canonical Feature Path

## Production command

```powershell
py scripts/build_features.py --season 2025-26
```

The wrapper delegates exclusively to `scripts/features/build_features_v1_3.py`, which is the only supported production feature builder. The v1.3 builder enforces target-GW cutoffs, excludes target columns from model features, and emits feature manifests and leakage reports.

Legacy builders are retained only under `old documents/phase4_archived_feature_builders/` for historical reference and are not production entry points. `scripts/features/inspect_features.py` remains diagnostic-only. `scripts/features/build_training_dataset_v1.py` consumes normalized feature artifacts and does not generate features.

All model registry entries use feature version `builder-1.3.0`. Any future builder must be introduced through a new explicit version, regression tests, manifest version, and promotion review.
