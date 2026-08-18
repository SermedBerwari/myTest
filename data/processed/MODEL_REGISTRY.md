# Model and Artifact Registry

## Purpose

The registry is the authoritative record of model artifacts eligible for production use. It separates model identity from file location, records the feature and dataset versions used for training, and prevents silent replacement of artifacts through SHA-256 integrity checks.

## Registry file

The machine-readable registry is `data/processed/model_registry.json`. It records the registry version, active production model, feature version, dataset version, official xP formula version, model entries, and artifact policy.

## Required model fields

Each model entry contains the model name, model type, model version context, feature version, dataset version, training seasons, artifact path, SHA-256 artifact hash, creation timestamp, evaluation metrics, and lifecycle status.

| Field | Requirement |
|---|---|
| `model_name` | Stable unique identifier. |
| `model_type` | Serialization/model-family description. |
| `feature_version` | Feature-builder version used for training. |
| `dataset_version` | Training-data schema/version. |
| `training_seasons` | Chronological seasons included in training. |
| `artifact_hash` | SHA-256 hash prefixed with `sha256:`. |
| `created_at_utc` | UTC creation timestamp. |
| `status` | One of `candidate`, `active`, or `retired`. |
| `walk_forward_metrics` | Evaluation metrics, including RMSE where available. |

## Lifecycle

Models move through `candidate`, `active`, and `retired`. Only an active model may be selected as `production_model`. Promotion requires a passing registry validation, an existing artifact, matching SHA-256 hash, compatible feature and dataset versions, and a documented evaluation result.

## Artifact policy

Registry metadata, manifests, evaluation reports, and immutable production model files are tracked. Logs, caches, temporary predictions, and local training diagnostics are generated artifacts and are not production inputs. Artifact hashes must be recomputed after any intentional model replacement.

## Validation

Run `py scripts/evaluation/validate_model_registry.py` from the project root. The validator checks JSON structure, required fields, unique names, allowed statuses, artifact existence, active production selection, and SHA-256 integrity.
