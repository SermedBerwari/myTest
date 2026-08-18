# Repository Hygiene and Release Structure

## Production boundary

Production source code lives under `src/` and operational entry points live under `scripts/`. Model and reproducibility metadata is stored under `data/processed/`. The authoritative registry is `data/processed/model_registry.json`; the reproducibility manifest is `data/processed/reproducibility_manifest.json`.

## Generated and local outputs

Raw downloads, logs, CatBoost training diagnostics, virtual environments, caches, disposable smoke outputs, and diagnostic files are ignored. These outputs must not be used as production inputs or committed as release artifacts.

## Archive policy

Obsolete generators and superseded experiments are moved to `old documents/phase21_archived_experiments/`. They remain available for historical reference but are outside the production execution path.

## Release structure

| Directory | Policy |
|---|---|
| `src/` | Reusable production modules. |
| `scripts/` | Operational and validation entry points. |
| `data/raw/` | Downloaded source data; generated and ignored. |
| `data/processed/` | Validated manifests, reports, registries, and selected reproducible outputs. |
| `data/models/` | Model artifacts referenced by the model registry. |
| `tests/` | Automated regression and contract tests. |
| `old documents/` | Archived legacy documentation and experiments. |

## Validation

Run `py scripts/evaluation/validate_repository_hygiene.py` from the project root before release. The validator checks required control files, forbidden generated directories, disposable diagnostics, archive placement, and essential `.gitignore` rules.
