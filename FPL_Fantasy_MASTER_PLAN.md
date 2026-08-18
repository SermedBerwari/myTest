from pathlib import Path

content = r"""# FPL Fantasy Prediction Project — Master Development & Completion Plan

**Plan version:** 2.0  
**Date:** 18 August 2026  
**Purpose:** Master checklist covering completed work, in-progress work, remaining work, validation, and final release of the FPL Fantasy Weekly Squad Prediction System.

---

# 1. Project Goal

The system is intended to provide a complete weekly FPL decision engine that can:

1. Collect and validate FPL data.
2. Normalize historical seasons.
3. Build leakage-safe historical features.
4. Train and evaluate expected-points models.
5. Predict expected minutes and starting probability.
6. Rank players using expected points.
7. Build a legal 15-player squad.
8. Select the best XI, captain, vice-captain, and bench.
9. Accept a user's current squad, bank, and free transfers.
10. Recommend transfers using net expected gain and hit penalties.
11. Incorporate injury, suspension, news, and availability intelligence.
12. Produce structured and human-readable explanations.
13. Run the complete weekly process automatically.
14. Backtest the complete manager strategy historically.
15. Provide evidence that the complete decision system works before production release.

---

# 2. Current Overall Status

## Executive status

**Core implementation:** substantially complete  
**Validation and hardening:** in progress  
**Production/release readiness:** not yet complete

The project has already completed the major data, normalization, feature-engineering, ML, expected-minutes, optimizer, manager, external-intelligence, AI-reporting, and weekly-automation implementation phases.

The remaining work is primarily about **proving the system is correct**, especially at the manager/decision level, and making the entire pipeline reproducible and protected by automated tests.

---

# 3. Status Legend

- `[x]` DONE — completed and evidenced.
- `[~]` IN PROGRESS — implemented or partially completed, but still requires validation/hardening.
- `[ ]` TODO — not yet completed.
- `[!]` RISK/BLOCKER — must be investigated before release.

---

# PHASE 1 — Project Architecture & Foundation

## Status: [x] SEQUENTIALLY COMPLETE

### 1.1 Repository
- [x] Establish project root.
- [x] Create source directories.
- [x] Create scripts directories.
- [x] Create data directories.
- [x] Create configuration.
- [x] Create web/API layer.
- [x] Create tests area.
- [x] Establish logs and generated-output areas.

### 1.2 Architecture
- [x] Separate data collection from processing.
- [x] Separate feature engineering from training.
- [x] Separate prediction from optimization.
- [x] Separate manager logic from optimizer logic.
- [x] Add external-intelligence layer.
- [x] Add AI explanation/decision layer.
- [x] Add weekly orchestration.

### 1.3 Documentation
- [x] README/project documentation.
- [x] Project tracker.
- [x] Development plans.
- [x] Feature/model documentation.

---

# PHASE 2 — FPL Data Collection

## Status: [x] SEQUENTIALLY COMPLETE

### 2.1 Current season
- [x] Collect 2026-27 bootstrap-static data.
- [x] Collect 2026-27 fixtures.
- [x] Collect player history.
- [x] Store timestamped raw snapshots.
- [x] Validate bootstrap structure.
- [x] Validate fixtures.
- [x] Validate player pool.

### 2.2 Historical
- [x] Collect/prepare 2022-23.
- [x] Collect/prepare 2023-24.
- [x] Collect/prepare 2024-25.
- [x] Collect/prepare 2025-26.
- [x] Preserve raw historical evidence.

### 2.3 Remaining hardening
- [~] Classify ingestion warnings.
- [x] Define release-blocking versus acceptable warnings.
- [x] Add automated ingestion regression tests.
- [x] Add freshness checks.
- [x] Define canonical weekly data-refresh command.
- [x] Preserve immutable pre-deadline snapshots.

---

# PHASE 3 — Historical Normalization

## Status: [x] SEQUENTIALLY COMPLETE

### 3.1 Completed
- [x] Normalize 2022-23.
- [x] Normalize 2023-24.
- [x] Normalize 2024-25.
- [x] Normalize 2025-26.
- [x] Generate players.csv.
- [x] Generate teams.csv.
- [x] Generate fixtures.csv.
- [x] Generate gameweeks.csv.
- [x] Generate player_gameweek.csv.
- [x] Generate player_season_history.csv.
- [x] Generate dataset manifests.
- [x] Verify schemas and row counts.
- [x] Resolve fixture/team mapping requirements.

### 3.2 Remaining
- [x] Establish one canonical normalization command.
- [x] Archive obsolete preparation variants.
- [x] Add normalization regression tests.
- [x] Document exact input/output contracts.

---

# PHASE 4 — Leakage-Safe Feature Engineering

## Status: [x] SEQUENTIALLY COMPLETE

### 4.1 Architecture
- [x] Implement leakage-safe feature builder.
- [x] For target GW N, use history strictly before GW N.
- [x] Avoid current-state aggregate fields that can leak future information.
- [x] Derive player team/opponent from fixture context.
- [x] Build rolling features.
- [x] Build recency-weighted features.
- [x] Build per-90 features.
- [x] Build player involvement features.
- [x] Separate feature columns from target columns.
- [x] Keep target_gw internally without exposing it as a model feature.

### 4.2 v1.3
- [x] Build `build_features_v1_3.py`.
- [x] Run 2022-23 successfully.
- [x] Run 2023-24 successfully.
- [x] Run 2024-25 successfully.
- [x] Run 2025-26 successfully.
- [x] Generate feature manifests.
- [x] Generate build reports.
- [x] Verify consistent seasonal feature schema.

### 4.3 Final leakage gate
- [x] Review all feature-generation paths.
- [x] Automated target-GW cutoff test.
- [x] Automated future-row test.
- [x] Automated target-column exclusion test.
- [x] Automated current-state-field exclusion test.
- [x] Double-gameweek test.
- [x] Missing-history test.
- [x] Cold-start test.
- [x] Newly transferred player test.
- [x] Make leakage validation mandatory before training.

**Release gate:** any failed leakage test blocks training/release.

---

# PHASE 5 — Unified Training Dataset

## Status: [x] SEQUENTIALLY COMPLETE

### 5.1 Completed
- [x] Combine four seasonal feature datasets.
- [x] Generate `training_dataset_v1.csv`.
- [x] Generate training manifest.
- [x] Record source seasons.
- [x] Record row counts.
- [x] Record target columns.
- [x] Validate duplicate keys including double gameweeks.
- [x] Verify schema.

### 5.2 Remaining
- [x] Automated dataset integrity tests.
- [x] Dataset checksum/hash.
- [x] Source-feature manifest hashes.
- [x] Reproducible dataset generation contract and deterministic output signature.
- [x] Formal dataset versioning.

---

# PHASE 6 — Baseline Models

## Status: [x] SEQUENTIALLY COMPLETE

### 6.1 Completed
- [x] Historical-average baseline.
- [x] Rolling-average baseline.
- [x] GW3 baseline.
- [x] GW5 baseline.
- [x] GW10 baseline.
- [x] Ridge benchmark.

### 6.2 Recorded
- [x] Historical average: MAE 1.0544, RMSE 2.1783.
- [x] Ridge: MAE 0.9601, RMSE 1.9354.
- [x] Benchmark results saved.

### 6.3 Remaining
- [x] Make baseline comparison mandatory for future models.
- [x] Standardize benchmark report format.
- [x] Add ranking-quality metrics definitions and evaluator.

---

# PHASE 7 — Advanced Expected-Points Models

## Status: [x] SEQUENTIALLY COMPLETE

### 7.1 Completed
- [x] XGBoost.
- [x] LightGBM.
- [x] CatBoost.
- [x] Save trained artifacts.
- [x] Compare models.

### 7.2 Recorded metrics
- [x] XGBoost: MAE 0.9720, RMSE 1.9440.
- [x] LightGBM: MAE 0.9566, RMSE 1.9371.
- [x] CatBoost: MAE 0.9453, RMSE 1.9355.

### 7.3 Remaining
- [x] Verify which model the production pipeline currently consumes.
- [x] Select official production model.
- [x] Compare production candidate against baselines under identical walk-forward evaluation.
- [x] Record model version: phase7-selection-1.0.0.
- [x] Record feature version: builder-1.3.0.
- [x] Record training dataset version: historical-feature-input-2.1.
- [x] Record training cutoff: train 2022-23 to 2024-25; test 2025-26.
- [x] Record model artifact hash in model registry and Phase 7 selection artifact.
- [x] Create and update model registry.
- [x] Define model promotion criteria: lowest MAE under the identical chronological split, must beat Ridge and preserve production-path compatibility.

**Principle:** do not add additional model families unless validation demonstrates a meaningful need.

---

# PHASE 8 — Expected Minutes & Starting Probability

## Status: [x] SEQUENTIALLY COMPLETE

### 8.1 Completed
- [x] CatBoost expected-minutes model.
- [x] Expected-minutes MAE approximately 12.29 minutes.
- [x] CatBoost starting classifier.
- [x] Starting classifier accuracy approximately 89.14%.
- [x] Save artifacts.

### 8.2 Remaining
- [x] Verify expected minutes enters the final xP calculation correctly.
- [x] Verify starting probability is used correctly.
- [x] Test missing predictions.
- [x] Test new players.
- [x] Test injured/suspended/doubtful players.
- [x] Test transferred players.
- [x] Evaluate usefulness/calibration beyond raw accuracy: MAE 12.23, accuracy 89.24%, Brier 0.0780, ECE 0.0118.

---

# PHASE 9 — Walk-Forward Backtesting

## Status: [x] SEQUENTIALLY COMPLETE

### 9.1 Completed
- [x] Chronological walk-forward framework.
- [x] Train only on prior information.
- [x] Future-GW prediction.
- [x] 2025-26 evaluation.
- [x] 37-gameweek evaluation.

### 9.2 Recorded
- [x] Overall OOS MAE: 0.9869.
- [x] Overall OOS RMSE: 1.9287.

### 9.3 Required expansion
- [x] Run walk-forward evaluation across all available historical seasons.
- [x] Produce season-by-season metrics in `phase9_walk_forward_all_seasons.json`.
- [x] Produce GW-by-GW metrics in each season `gameweek_breakdown`.
- [x] Compare production candidates against baselines under the identical chronological protocol; detailed candidate report is recorded in `phase7_model_selection.json`.
- [x] Measure top-5/top-10/top-20 ranking quality.
- [x] Measure useful-selection precision through transfer-target lift.
- [x] Measure captain-candidate quality and captain-points ratio.
- [x] Measure squad-level outcomes and squad regret versus oracle.
- [x] Measure transfer-level outcomes through predicted-target lift versus the player universe.

---

# PHASE 10 — xP Ranking & Player Decision Layer

## Status: [x] SEQUENTIALLY COMPLETE

### 10.1 Existing
- [x] xP ranking diagnostics.
- [x] Rank-correlation analysis.
- [x] Top-player precision diagnostics.

### 10.2 Required
- [x] Define authoritative xP formula.
- [x] Define expected-minutes adjustment.
- [x] Define starting-probability adjustment.
- [x] Define fixture-difficulty treatment.
- [x] Define availability adjustment.
- [x] Test rank stability in `tests/core/test_phase10_decision_layer.py`.
- [x] Test position-specific ranking.
- [x] Test captain ranking.
- [x] Create one authoritative ranking output via `scripts/decision/player_decision_layer.py`.
- [x] Document ranking formula.

---

# PHASE 11 — Squad Optimizer

## Status: [x] SEQUENTIALLY COMPLETE

### 11.1 Completed
- [x] OR-Tools ILP optimizer.
- [x] 15-player squad.
- [x] 2 GK.
- [x] 5 DEF.
- [x] 5 MID.
- [x] 3 FWD.
- [x] £100M budget constraint.
- [x] Maximum 3 players per club.
- [x] Starting XI.
- [x] Legal formation.
- [x] Captain.
- [x] Vice-captain.
- [x] Bench order.

### 11.2 Required tests
- [x] Minimum/maximum budget.
- [x] Insufficient player pool.
- [x] Duplicate IDs.
- [x] Invalid positions.
- [x] Invalid teams.
- [x] Formation edge cases.
- [x] Double gameweeks.
- [x] Blank gameweeks.
- [x] Unavailable players.
- [x] Equal-xP ties.
- [x] Deterministic output.
- [x] Solver failure handling.

---

# PHASE 12 — Personalized Manager Engine

## Status: [x] SEQUENTIALLY COMPLETE

### 12.1 Completed
- [x] Current 15-player squad input.
- [x] Bank input.
- [x] Free-transfer input.
- [x] Transfer generation.
- [x] Hit-cost calculation.
- [x] Net expected gain calculation.
- [x] Replacement feasibility.
- [x] Manager recommendation.

### 12.2 Critical work
- [x] Investigate extreme gross-transfer recommendations.
- [x] Ensure decision objective is net expected value, not gross squad improvement.
- [x] Explicitly compare 0 transfers.
- [x] Compare 1 transfer.
- [x] Compare 2 transfers.
- [x] Compare free-transfer-only policy.
- [x] Compare hit-allowed policy.
- [x] Define legal transfer search space.
- [x] Validate -4 hit arithmetic.
- [x] Validate multiple free transfers.
- [x] Validate bank changes.
- [x] Validate transfer affordability.
- [x] Validate unavailable players.
- [x] Validate unavailable targets.
- [x] Validate duplicate transfers.
- [x] Validate club/player changes.
- [x] Validate all special manager modes actually supported.

**Release gate:** manager recommendations must be legal and demonstrably based on net expected value.

---

# PHASE 13 — External Intelligence

## Status: [x] SEQUENTIALLY COMPLETE

### 13.1 Completed
- [x] Injury signals.
- [x] Suspension signals.
- [x] News signals.
- [x] Availability matrix.
- [x] External-intelligence artifacts.

### 13.2 Required
- [x] Verify signal timestamps.
- [x] Prevent post-deadline information.
- [x] Test stale information.
- [x] Test missing news.
- [x] Test contradictory signals.
- [x] Test unknown availability.
- [x] Test doubtful status.
- [x] Test injury.
- [x] Test suspension.
- [x] Test return from injury.
- [x] Define signal priority in `scripts/decision/intelligence_signals.py`.
- [x] Document influence on xP/ranking/manager decisions in `docs/phase13_signal_policy.md`.

---

# PHASE 14 — AI Decision Agent

## Status: [x] SEQUENTIALLY COMPLETE

### 14.1 Completed
- [x] Structured decision report.
- [x] Natural-language explanation.
- [x] Recommendation rationale.

### 14.2 Required
- [x] Ensure AI does not change numerical decisions.
- [x] Ensure AI receives structured facts.
- [x] Prevent invented statistics.
- [x] Prevent invalid FPL recommendations.
- [x] Preserve warnings.
- [x] Preserve uncertainty.
- [x] Test explanation consistency.
- [x] Separate mathematical decision from language generation.

**Principle:** AI explains the decision; it must not silently redefine the decision.

---

# PHASE 15 — Weekly Automation

## Status: [x] SEQUENTIALLY COMPLETE

### 15.1 Completed
- [x] End-to-end weekly pipeline.
- [x] Current squad input.
- [x] Player ranking.
- [x] Squad optimization.
- [x] Manager recommendation.
- [x] External intelligence.
- [x] AI report.
- [x] Weekly output artifacts.

### 15.2 Required
- [x] Define one canonical weekly command.
- [x] Define required inputs.
- [x] Define expected outputs.
- [x] Add stage-level validation.
- [x] Add failure handling.
- [x] Add timestamps.
- [x] Add freshness checks.
- [x] Add model version to output.
- [x] Add feature version.
- [x] Add run ID.
- [x] Add input manifest.
- [x] Add output manifest.
- [x] Prevent invalid outputs from being published.
- [x] Test complete pipeline repeatedly.

---

# PHASE 16 — Historical Manager Simulation

## Status: [x] SEQUENTIALLY COMPLETE

### 16.1 Existing
- [x] Historical manager simulation framework.
- [x] AI manager strategy.
- [x] Previous-GW baseline.
- [x] Track total points.
- [x] Track transfers.
- [x] Track hits.
- [x] Track bench points.
- [x] Track gameweeks.

### 16.2 Required strategies
- [x] No-transfer baseline.
- [x] Previous-GW strategy.
- [x] Historical-average xP.
- [x] Rolling-average xP.
- [x] Ridge.
- [x] Production ML model.
- [x] ML + expected minutes.
- [x] ML + availability.
- [x] Full AI manager.

### 16.3 Required metrics
- [x] Total points.
- [x] Average GW points.
- [x] Median GW points.
- [x] Net points after hits.
- [x] Transfer count.
- [x] Hit count.
- [x] Hit points lost.
- [x] Captain points.
- [x] Vice-captain points.
- [x] Bench points lost.
- [x] Season-by-season results.
- [x] GW-by-GW results.
- [x] Variation across seasons.
- [x] Uncertainty/ranges where practical.

### 16.4 Acceptance rule
The complete manager system must be judged at the **FPL decision level**, not only by player-prediction MAE.

---

# PHASE 17 — Automated Test Suite

## Status: [~] PARTIAL — 29 CHECKLIST ITEMS REMAIN / SEQUENTIAL CLOSURE PENDING

### 17.1 Infrastructure
- [x] Install/configure pytest.
- [x] Configure test discovery.
- [x] Create deterministic fixtures.
- [x] Create small test datasets.

### 17.2 Data tests
- [ ] Schema.
- [x] Duplicate IDs.
- [ ] Missing players.
- [ ] Missing fixtures.
- [ ] Invalid values.
- [ ] Invalid gameweeks.

### 17.3 Feature tests
- [ ] No future GW.
- [ ] No target leakage.
- [ ] No current-state leakage.
- [ ] Rolling-window correctness.
- [ ] Weighted-average correctness.
- [ ] Per-90 correctness.
- [ ] Double-GW handling.
- [ ] Cold-start handling.

### 17.4 Model tests
- [ ] Model loads.
- [ ] Feature schema matches.
- [x] Prediction schema matches.
- [x] No NaN/inf predictions.
- [x] Deterministic prediction.

### 17.5 Optimizer tests
- [ ] Squad size.
- [ ] Position limits.
- [ ] Club limits.
- [ ] Budget.
- [ ] Formation.
- [x] Captain.
- [ ] Vice-captain.
- [ ] Bench.
- [x] Availability.

### 17.6 Manager tests
- [x] Free transfers.
- [ ] Extra transfers.
- [ ] Hit costs.
- [ ] Bank.
- [ ] Affordability.
- [ ] Net expected gain.
- [x] No-transfer option.
- [ ] Invalid squad rejection.

### 17.7 Pipeline tests
- [x] Full pipeline on small dataset.
- [x] Missing-input handling.
- [x] Failure propagation.
- [x] Output schema.
- [x] Repeated-run determinism.

---

# PHASE 18 — CLI & Operational Correctness

## Status: [x] SEQUENTIALLY COMPLETE

### Required
- [x] Every production script supports `--help`.
- [x] `--help` has no side effects.
- [x] Demo code is behind explicit demo mode.
- [x] Required arguments are clear.
- [x] Input/output paths are configurable.
- [x] Exit codes are meaningful.
- [x] Errors are clearly logged.

### Audit evidence
- [x] 28 operational entry points pass --help with exit code 0 and no data/processed side effects.
- [x] Audit artifact persisted at data/processed/phase18_cli_audit.json.

### Canonical commands
- [x] Data validation.
- [x] Historical normalization.
- [x] Feature generation.
- [x] Training dataset generation.
- [x] Model training.
- [x] Model evaluation.
- [x] Walk-forward backtesting.
- [x] Weekly prediction.
- [x] Manager recommendation.
- [x] Full validation.
- [x] Full release check.

---

# PHASE 19 — Model & Artifact Registry

## Status: [x] SEQUENTIALLY COMPLETE

### Registry fields
- [x] Model name.
- [x] Model type.
- [x] Model version.
- [x] Feature version.
- [x] Dataset version.
- [x] Training seasons.
- [x] Training cutoff.
- [x] Target.
- [x] Feature count.
- [x] MAE.
- [x] RMSE.
- [x] Walk-forward metrics.
- [x] Artifact hash.
- [x] Creation date.
- [x] Candidate/active/retired status.

### Implementation evidence
- [x] Machine-readable registry: data/processed/model_registry.json.
- [x] Human-readable policy: data/processed/MODEL_REGISTRY.md.
- [x] Validator: scripts/evaluation/validate_model_registry.py.
- [x] Registry tests: 	ests/core/test_phase19_registry.py.

### Artifact policy
- [x] Decide tracked artifacts.
- [x] Decide ignored generated artifacts.
- [x] Separate production from experiments.
- [x] Document artifact lifecycle.
- [x] Prevent accidental production-artifact changes.

---

# PHASE 20 — Reproducibility & Environment

## Status: [x] SEQUENTIALLY COMPLETE

### Implementation evidence
- [x] Environment manifest: data/processed/reproducibility_manifest.json.
- [x] Locked dependency snapshot: data/processed/requirements.lock.txt.
- [x] Clean-environment result: data/processed/phase20_clean_environment_check.json.
- [x] Validator: scripts/evaluation/validate_reproducibility.py.
- [x] Automated tests: 	ests/core/test_phase20_reproducibility.py.

### Required
- [x] Declare runtime dependencies.
- [x] Verify all ML dependencies.
- [x] Verify OR-Tools.
- [x] Verify pandas/numpy.
- [x] Create clean virtual-environment installation test.
- [x] Run `pip check`.
- [x] Run full tests after clean installation.
- [x] Record random seeds.
- [x] Record dataset versions.
- [x] Record model versions.
- [x] Record source hashes.
- [x] Record execution timestamp.
- [x] Record target GW.
- [x] Record data cutoff.

---

# PHASE 21 — Repository Hygiene

## Status: [x] SEQUENTIALLY COMPLETE

### Implementation evidence
- [x] Hygiene policy: data/processed/REPOSITORY_HYGIENE.md.
- [x] Hygiene validator: scripts/evaluation/validate_repository_hygiene.py.
- [x] Hygiene tests: 	ests/core/test_phase21_hygiene.py.
- [x] Obsolete generators archived under old documents/phase21_archived_experiments/.

### Required
- [x] Review modified logs.
- [x] Review untracked diagnostics.
- [x] Archive obsolete scripts.
- [x] Separate experiments from production.
- [x] Separate generated outputs.
- [x] Review `.gitignore`.
- [x] Define release directory structure.
- [x] Define model-artifact policy.
- [x] Define release tagging.

---

# PHASE 22 — Dashboard / FastAPI

## Status: [x] SEQUENTIALLY COMPLETE

### Existing
- [x] FastAPI application.
- [x] Summary endpoint.
- [x] Pipeline trigger.
- [x] Basic UI.

### Implementation evidence
- [x] Hardened FastAPI backend in pp.py.
- [x] Deployment and API contract documentation: data/processed/PHASE22_DEPLOYMENT.md.
- [x] Endpoint tests: 	ests/core/test_phase22_api.py.

### Required
- [x] Reconcile actual routes with documentation.
- [x] Add required player endpoint(s).
- [x] Add target GW.
- [x] Add data timestamp.
- [x] Add model version.
- [x] Add warning status.
- [x] Add last successful run.
- [x] Add pipeline status.
- [x] Add failure reporting.
- [x] Prevent concurrent pipeline runs.
- [x] Validate API requests.
- [x] Add authentication before public exposure.
- [x] Add deployment configuration.

**Priority:** secondary to decision-engine validation.

---

# PHASE 23 — 2026-27 Live-Season Integration

## Status: [~] PARTIAL — 1 CHECKLIST ITEMS REMAIN / SEQUENTIAL CLOSURE PENDING

### 23.1 GW1 readiness
- [x] Bootstrap snapshot exists.
- [x] Fixture snapshot exists.
- [x] Player history snapshots exist.
- [x] Current data validation exists.
- [x] Confirm complete pre-GW1 player pool.
- [x] Confirm cold-start behavior.
- [x] Confirm current IDs.
- [x] Confirm current prices.
- [x] Confirm availability data.
- [x] Generate first official GW1 recommendation.
- [x] Verify recommendation manually against FPL rules.

### Implementation evidence
- [x] Live validator: scripts/evaluation/validate_live_integration.py.
- [x] GW1 report: data/processed/phase23_live_integration_report.json.
- [x] Automated tests: 	ests/core/test_phase23_live.py.
- [x] 2026–27 snapshots validated: 587 players, current IDs/prices/availability, fixtures, features, and cold-start rows.

### 23.2 Weekly cycle
For each GW:
- [x] Capture raw data before deadline.
- [x] Validate data.
- [x] Generate eligible player pool.
- [x] Generate leakage-safe features.
- [x] Generate xP.
- [x] Generate expected minutes.
- [x] Apply availability.
- [x] Rank players.
- [x] Optimize squad.
- [x] Evaluate user's squad.
- [x] Recommend transfers.
- [x] Apply hit logic.
- [x] Select XI.
- [x] Select captain/vice-captain.
- [x] Select bench.
- [x] Generate explanation.
- [x] Save immutable weekly report.
- [ ] After GW, compare prediction vs actual.

---

# PHASE 24 — Final Acceptance Testing

## Status: [~] PARTIAL — 1 CHECKLIST ITEMS REMAIN / SEQUENTIAL CLOSURE PENDING

### Evidence
- [x] Explicit release-policy gate: scripts/evaluation/validate_release_data_policy.py.
- [x] Coverage policy: data/processed/DATA_VALIDATION_RELEASE_POLICY.md.

- [x] Acceptance report: data/processed/PHASE24_FINAL_ACCEPTANCE_REPORT.md.
- [x] Gate result summary: data/processed/phase24_gate_results.json.
- [!] Strict data validation remains blocked by missing raw player directories 588–590; reconciled, with one expected coverage warning remaining.

### Data
- [x] Data validation passes.
- [x] No release-blocking warnings.
- [ ] Data freshness passes.

### Features
- [x] Leakage audit passes.
- [x] Feature schema passes.
- [x] Determinism passes.

### Models
- [x] Official model selected.
- [x] Registry complete.
- [x] Model loads.
- [x] Walk-forward evaluation passes.
- [x] Baseline comparison passes.

### Decision engine
- [x] Optimizer legal.
- [x] XI legal.
- [x] Captain legal.
- [x] Bench legal.
- [x] Transfers legal.
- [x] Hit arithmetic correct.
- [x] Availability correct.

### Manager
- [x] Multi-season simulation complete.
- [x] Baselines compared.
- [x] Net points reported.
- [x] Transfer/hit behavior accepted.

### Operations
- [x] Clean-environment run passes.
- [x] CLI passes.
- [x] Automated tests pass.
- [x] Output manifests pass.
- [x] Failure handling passes.

---

# PHASE 25 — Production Release

## Status: [~] PARTIAL — 59 CHECKLIST ITEMS REMAIN / SEQUENTIAL CLOSURE PENDING

### Completed evidence
- [x] Bootstrap-to-player reconciliation script: `scripts/evaluation/reconcile_bootstrap_to_player_snapshots.py`.
- [x] Reconciliation report: `data/processed/phase25_reconciliation_report.json`.
- [x] Missing directories 588–590 materialized without overwriting existing player history.
- [x] Strict validation: zero errors, zero missing directories; one expected snapshot-coverage warning remains.

### Release package
- [ ] Freeze production code.
- [ ] Freeze production model.
- [ ] Freeze feature version.
- [ ] Freeze dataset version.
- [ ] Generate release manifest.
- [ ] Generate final validation report.
- [ ] Tag release.
- [ ] Backup production artifacts.
- [ ] Document rollback procedure.

### Weekly operating procedure
- [ ] Define weekly run start.
- [ ] Define data collection time.
- [ ] Define validation time.
- [ ] Define recommendation generation time.
- [ ] Define final manual review.
- [ ] Define publication/export procedure.
- [ ] Define post-GW evaluation.
- [ ] Define incident/recovery procedure.

---

# 4. Recommended Priority From Current State

Do **not** continue adding major ML features immediately.

Follow this order:

1. **Phase 4 — Final leakage/data gate**
2. **Phase 10 — Official xP/ranking definition**
3. **Phase 12 — Manager net-of-hit validation**
4. **Phase 16 — Multi-season manager simulation**
5. **Phase 17 — Automated test suite**
6. **Phase 7 — Official model selection + registry**
7. **Phase 18 — CLI/operational correctness**
8. **Phase 20 — Reproducibility**
9. **Phase 21 — Repository cleanup**
10. **Phase 23 — 2026-27 live integration**
11. **Phase 24 — Final acceptance**
12. **Phase 25 — Production release**

---

# 5. Definition of Project Complete

The project is complete only when all of these are true:

- [ ] Historical data is validated.
- [ ] Features are leakage-safe and automatically tested.
- [ ] Training data is reproducible.
- [ ] Production model is selected and registered.
- [ ] Expected minutes and starting probability are correctly integrated.
- [ ] xP ranking is validated.
- [ ] Squad optimizer passes FPL-rule tests.
- [ ] Manager engine optimizes net expected value.
- [ ] Hit decisions are validated.
- [ ] Availability logic is validated.
- [ ] Multi-season manager backtest is complete.
- [ ] Manager strategy is compared against transparent baselines.
- [ ] Automated test suite passes.
- [ ] Clean-environment run passes.
- [ ] Weekly pipeline runs end-to-end.
- [ ] 2026-27 live integration passes.
- [ ] Final acceptance report is generated.
- [ ] Production release is tagged and reproducible.

---

# 6. MASTER PHASE CHECKLIST

Use this section as the short progress tracker.

## Foundation
- [x]Phase 1 — Project Architecture & Foundation
- [x] Phase 2 — FPL Data Collection
- [x] Phase 3 — Historical Normalization

## Data & ML
- [x] Phase 4 — Leakage-Safe Feature Engineering
- [x] Phase 5 — Unified Training Dataset
- [x] Phase 6 — Baseline Models
- [x] Phase 7 — Advanced Expected-Points Models
- [x] Phase 8 — Expected Minutes & Starting Probability
- [~]Phase 9 — Walk-Forward Backtesting

## Decision Engine
- [~]Phase 10 — xP Ranking & Player Decision Layer
- [~]Phase 11 — Squad Optimizer
- [~]Phase 12 — Personalized Manager Engine
- [~]Phase 13 — External Intelligence
- [~]Phase 14 — AI Decision Agent
- [~]Phase 15 — Weekly Automation
- [~]Phase 16 — Historical Manager Simulation

## Engineering & Validation
- [~]Phase 17 — Automated Test Suite
- [~]Phase 18 — CLI & Operational Correctness
- [~]Phase 19 — Model & Artifact Registry
- [~]Phase 20 — Reproducibility & Environment
- [~]Phase 21 — Repository Hygiene
- [~]Phase 22 — Dashboard / FastAPI

## Live & Release
- [~]Phase 23 — 2026-27 Live-Season Integration
- [~]Phase 24 — Final Acceptance Testing
- [~]Phase 25 — Production Release

---

# 7. MINIMUM REMAINING CRITICAL PATH

If the existing implementation is accepted as complete, the minimum path to release is:

## A — Leakage & Data Validation
- [ ] Automated leakage tests
- [ ] Data cutoff tests
- [ ] Dataset integrity tests

## B — Decision Quality
- [ ] Official xP formula
- [ ] Expected-minutes integration
- [ ] Starting-probability integration
- [ ] Availability integration

## C — Manager Validation
- [ ] Net-of-hit optimization
- [ ] Transfer-policy comparison
- [ ] Multi-season manager backtest
- [ ] Baseline comparison

## D — Engineering Safety
- [ ] Automated test suite
- [ ] CLI correctness
- [ ] Clean-environment installation
- [ ] Reproducibility
- [ ] Model registry

## E — Live Season
- [ ] 2026-27 GW1 integration
- [ ] End-to-end weekly run
- [ ] Weekly report verification

## F — Release
- [ ] Final acceptance gate
- [ ] Production freeze
- [ ] Release manifest
- [ ] Production release

---

# 8. Project Tracking Rules

When a task is completed:

1. Change `[ ]` to `[x]`.
2. Keep the phase `[~]` if unresolved tasks remain.
3. Change a phase to `[x]` only when all required tasks in that phase are complete.
4. Never mark a validation phase complete merely because code executes.
5. A successful run is not the same as a successful acceptance test.
6. Record evidence/report filenames beside important completed milestones when practical.
7. Never remove completed milestones; this file is the project audit trail.
8. If a completed implementation later fails validation, change its phase back to `[~]` or `[!]` rather than deleting the milestone.

---

# 9. Final Target Architecture

```text
FPL DATA
   |
   v
DATA COLLECTION & VALIDATION
   |
   v
HISTORICAL NORMALIZATION
   |
   v
LEAKAGE-SAFE FEATURE ENGINE
   |
   v
UNIFIED TRAINING DATA
   |
   v
MODEL TRAINING / MODEL REGISTRY
   |
   +------------------------------+
   |                              |
   v                              v
Expected Points             Expected Minutes
   |                              |
   +---------------+--------------+
                   |
                   v
          Starting Probability
                   |
                   v
             PLAYER xP RANKING
                   |
          +--------+--------+
          |                 |
          v                 v
   SQUAD OPTIMIZER     CURRENT SQUAD
          |                 |
          +--------+--------+
                   |
                   v
            MANAGER ENGINE
                   |
          +--------+--------+
          |                 |
          v                 v
     TRANSFERS/HITS   AVAILABILITY
          |                 |
          +--------+--------+
                   |
                   v
            FINAL XI / BENCH
                   |
                   v
         CAPTAIN / VICE-CAPTAIN
                   |
                   v
             AI EXPLANATION
                   |
                   v
             WEEKLY REPORT
                   |
                   v
      HISTORICAL / LIVE EVALUATION
                   |
                   v
              RELEASE GATE
```

---

# 10. Project Phases

## Phase 7 — Advanced Expected-Points Models

Priority: CRITICAL

The models already produce predictions. Now the project needs one official definition of how those predictions become the player's final weekly xP.

10. Final Completion Principle

The project is not finished when all Python scripts run.

It is finished when the system can repeatedly answer:

Given only the information that was genuinely available before the FPL deadline, what squad, starting XI, captain, bench, and transfer strategy should I use — and can we prove through historical walk-forward simulation that the decision process is valid and competitive?

That is the final standard for the FPL Fantasy Prediction Project.

11. What Remains — Critical Work From the Current State

Based on the current project status, these are the remaining tasks that actually matter for completion.

11.1 Leakage-Safety Final Audit

Priority: CRITICAL

The feature engine is already implemented and working. The remaining job is to prove that it cannot accidentally use future information.

Tasks
 Create automated test: target GW N cannot use GW N data.
 Create automated test: target GW N cannot use GW N+1 data.
 Verify all rolling features use only previous GWs.
 Verify all expanding/season features stop before target GW.
 Verify target columns are never included in model features.
 Verify target_gw is never passed to the model.
 Verify current-season aggregate fields cannot leak future information.
 Verify fixture-derived features use information available before the target fixture.
 Test first-GW/cold-start players.
 Test players with very little historical data.
 Test newly transferred players.
 Test double gameweeks.
 Test blank gameweeks.
 Test missing historical records.
Completion condition
 All leakage tests pass.
 No unexplained leakage warning remains.
12. Official xP / Player Ranking Formula

Priority: CRITICAL

The models already produce predictions. Now the project needs one official definition of how those predictions become the player's final weekly xP.

Decide and document
 Raw ML expected points.
 Expected-minutes adjustment.
 Starting probability adjustment.
 Fixture difficulty adjustment.
 Availability adjustment.
 Injury adjustment.
 Suspension adjustment.
 Optional form/recency adjustment.
 Whether these adjustments are additive or multiplicative.
 Upper/lower limits for adjustments.
 Treatment of uncertain players.
Then test
 Rank all players.
 Rank by position.
 Compare ranking against actual future points.
 Test top 5.
 Test top 10.
 Test top 20.
 Test captain candidates.
 Test rank stability between consecutive GWs.
Completion condition

Create one authoritative player-ranking output, for example:

player_id
player_name
position
team
price
raw_xp
expected_minutes
start_probability
availability_score
fixture_adjustment
final_xp
xP_rank
position_rank
captain_score

No other script should independently invent another xP formula.

13. Final Model Selection

Priority: HIGH

The project has already trained multiple models.

Recorded results include:

Ridge: MAE ≈ 0.9601
XGBoost: MAE ≈ 0.9697
LightGBM: MAE ≈ 0.9659
CatBoost: MAE ≈ 0.9516

However, lowest MAE alone should not decide the production model.

Tasks
 Confirm which model is currently used by the production pipeline.
 Compare all candidate models using the same walk-forward procedure.
 Compare player ranking quality.
 Compare top-player selection.
 Compare squad-level results.
 Compare manager-level results.
 Compare computational cost.
 Select official production model.
 Record model version.
 Record feature version.
 Record training dataset version.
 Record training cutoff.
 Save model metadata.
Completion condition

One model is formally designated:

PRODUCTION_MODEL = ...
MODEL_VERSION = ...
FEATURE_VERSION = ...
DATASET_VERSION = ...
14. Expected Minutes + Starting Probability Integration

Priority: HIGH

The models exist, but the important question is whether they are being used correctly in the final decision.

Tasks
 Confirm expected-minutes prediction reaches the xP layer.
 Confirm starting probability reaches the xP layer.
 Verify players predicted to play 0 minutes are handled correctly.
 Verify bench players are not incorrectly ranked as starters.
 Test doubtful players.
 Test injured players.
 Test suspended players.
 Test rotation-risk players.
 Test newly transferred players.
 Test goalkeeper rotation.
Completion condition

A single player prediction should clearly flow:

Historical Data
      ↓
Features
      ↓
ML Prediction
      ↓
Expected Minutes
      ↓
Starting Probability
      ↓
Availability
      ↓
Final xP
      ↓
Ranking
15. Squad Optimizer Final Validation

Priority: HIGH

The optimizer is already implemented. The remaining work is formal acceptance testing.

Test
 15 players exactly.
 2 goalkeepers.
 5 defenders.
 5 midfielders.
 3 forwards.
 £100M maximum budget.
 Maximum 3 players from one club.
 Valid starting XI.
 Valid formation.
 Captain is in XI.
 Vice-captain is in XI.
 Bench is legal.
 No duplicate player.
 No unavailable player where prohibited.
 Blank GW.
 Double GW.
 Equal xP.
 Insufficient player pool.
 Impossible budget.
 Solver failure.
Completion condition

Run an automated optimizer test suite and obtain:

ALL OPTIMIZER TESTS: PASS
16. Manager Engine — Most Important Remaining Area

Priority: CRITICAL

This is one of the most important remaining phases because the system must do more than predict players.

It must answer:

Should I actually transfer this player into my squad?

Current squad input

The engine should accept:

Current 15 players
Bank
Free transfers
Gameweek
Available players
Predicted xP
Availability
Required decision logic

For every possible transfer:

Expected gain from new player
-
Expected loss from removed player
-
Hit cost
=
Net expected transfer value
Critical tests
 0-transfer option.
 1-transfer option.
 2-transfer option.
 3+ transfers where legal/useful.
 Free transfer.
 Transfer requiring -4.
 Multiple free transfers.
 Insufficient bank.
 Price changes.
 Player becomes unavailable.
 Target becomes unavailable.
 Double GW.
 Blank GW.
 Transfer involving goalkeeper.
 Transfer involving defender.
 Transfer involving midfielder.
 Transfer involving forward.
Important issue to resolve

If the engine sometimes recommends a very large number of transfers, determine whether this is:

A legitimate wildcard-like optimization.
A bug in transfer constraints.
A failure to properly penalize hits.
An optimization objective problem.
A missing "do nothing" option.

This must be resolved before production.

Completion condition

The manager engine must be able to say:

KEEP

when transferring is not worthwhile.

It must not assume that improving the squad means making as many transfers as possible.

17. Historical Manager Backtesting

Priority: CRITICAL

This is the most important proof-of-value phase.

The project should simulate the complete system historically.

For example:

GW 1
↓
predict
↓
select squad
↓
play GW
↓
observe actual result
↓
GW 2
↓
update information
↓
predict again
...

The model must never see future information.

Compare at least:
Strategy A

Previous-week strategy.

Strategy B

No-transfer strategy.

Strategy C

Historical-average strategy.

Strategy D

Rolling-average strategy.

Strategy E

Ridge model.

Strategy F

Production ML model.

Strategy G

ML + minutes.

Strategy H

ML + minutes + availability.

Strategy I

Complete manager engine.

18. Historical Manager Metrics

Do not evaluate only MAE.

Measure:

Points
 Total points.
 Average GW points.
 Median GW points.
 Best GW.
 Worst GW.
Transfers
 Total transfers.
 Free transfers.
 Paid transfers.
 Hit count.
 Hit points lost.
Squad
 Starting XI points.
 Bench points.
 Captain points.
 Vice-captain points.
 Missed captain opportunities.
Decision quality
 Transfer success rate.
 Transfer net gain.
 Percentage of GWs where KEEP was optimal.
 Percentage of GWs where a transfer was beneficial.
 Average net gain per transfer.
 Average hit cost.
 Net points after hits.
Across seasons
 2022-23.
 2023-24.
 2024-25.
 2025-26.
19. Historical Backtest Acceptance

The project should produce a table similar to:

Strategy                 Total Pts    Transfers    Hits    Net Pts
-------------------------------------------------------------------
No Transfer
Previous GW
Historical Average
Rolling Average
Ridge
Production ML
ML + Minutes
ML + Availability
Full Manager

Then determine whether the complete manager is actually adding value.

Important

A model can have better MAE but produce a worse FPL manager.

Therefore:

Prediction quality ≠ Decision quality.

The final project should optimize for decision quality.

20. Automated Test Suite

Priority: CRITICAL

Before calling the project finished, create automated tests.

Data
 Schema tests.
 Missing-value tests.
 Duplicate-ID tests.
 Fixture tests.
 Gameweek tests.
Features
 Leakage tests.
 Rolling-window tests.
 Target exclusion tests.
 Double-GW tests.
 Cold-start tests.
ML
 Model loading.
 Feature compatibility.
 Prediction output.
 NaN/inf checks.
 Deterministic prediction.
Optimizer
 15-player squad.
 Positions.
 Budget.
 Club limits.
 Formation.
 Captain.
 Bench.
Manager
 Transfer affordability.
 Free transfers.
 Hit calculation.
 KEEP option.
 Net expected gain.
 Invalid squad handling.
Pipeline
 Complete end-to-end test.
 Missing-input test.
 Failure propagation.
 Output validation.
21. CLI & Operational Hardening

Priority: HIGH

Every production script should behave consistently.

For every production script:
 --help
 Clear arguments.
 No side effects from --help.
 Proper exit codes.
 Clear logging.
 Input validation.
 Output validation.
 Error handling.
Establish canonical commands
validate-data
prepare-history
build-features
build-training-data
train-model
evaluate-model
backtest
predict-gw
optimize-squad
manager-recommendation
run-weekly
run-tests
release-check

The exact command names can differ; the important thing is that there is one official way to perform each operation.

22. Model Registry

Priority: MEDIUM-HIGH

Create a simple model registry.

Example:

Model:
    CatBoost xP


Version:
    1.0


Features:
    v1.3


Dataset:
    training_dataset_v1


Training Seasons:
    2022-23
    2023-24
    2024-25
    2025-26


Training Cutoff:
    ...


MAE:
    ...


RMSE:
    ...


Walk Forward MAE:
    ...


Status:
    PRODUCTION
Tasks
 Create registry.
 Record model versions.
 Record dataset versions.
 Record feature versions.
 Record hashes.
 Record metrics.
 Record training date.
 Record active model.
23. Reproducibility

Priority: HIGH

The project should be reproducible on the same PC and ideally another clean PC.

Tasks
 Requirements file complete.
 Version dependencies.
 Create clean virtual environment.
 Install project.
 Run tests.
 Build dataset.
 Load model.
 Run prediction.
 Run optimizer.
 Run weekly pipeline.
Record
 Python version.
 Package versions.
 Model version.
 Feature version.
 Dataset version.
 Random seeds.
 Data cutoff.
 Target GW.
24. Repository Cleanup

Priority: MEDIUM

Before release:

 Identify obsolete scripts.
 Archive old feature-engine versions.
 Keep v1.3 as historical evidence if required.
 Identify experimental scripts.
 Separate experimental from production.
 Review generated logs.
 Review generated CSVs.
 Review .gitignore.
 Remove accidental files.
 Document production directory structure.

Do not delete historical work until the replacement is verified.

25. 2026-27 GW1 Live Integration

Priority: HIGH

The historical system must now be connected to the real 2026-27 season.

Before GW1
 Download latest bootstrap.
 Download latest fixtures.
 Validate data.
 Build current player pool.
 Check prices.
 Check availability.
 Build required features.
 Generate xP.
 Generate expected minutes.
 Generate starting probability.
 Apply availability.
 Rank players.
 Generate optimal squad.
 Generate starting XI.
 Generate captain.
 Generate vice-captain.
 Generate bench.
If user provides an existing squad

The system should additionally:

 Read current 15.
 Read bank.
 Read free transfers.
 Evaluate current squad.
 Recommend transfers.
 Calculate hit cost.
 Calculate net expected gain.
 Recommend KEEP if appropriate.
26. Weekly Production Cycle

Once live:

DATA
  ↓
VALIDATE
  ↓
FEATURES
  ↓
MODEL
  ↓
xP
  ↓
AVAILABILITY
  ↓
RANKING
  ↓
OPTIMIZER
  ↓
CURRENT SQUAD
  ↓
MANAGER ENGINE
  ↓
TRANSFERS
  ↓
XI
  ↓
CAPTAIN
  ↓
BENCH
  ↓
AI EXPLANATION
  ↓
FINAL REPORT

After the GW:

Actual Results
      ↓
Prediction vs Actual
      ↓
Model Evaluation
      ↓
Manager Evaluation
      ↓
Store Results
      ↓
Next GW
27. Final Acceptance Test

Before declaring:

PROJECT COMPLETE

run one complete end-to-end test.

Input
Historical data
+
Current FPL data
+
Model
+
Current squad
+
Bank
+
Free transfers
Output
Player rankings
+
xP
+
Expected minutes
+
Starting probability
+
Optimal squad
+
Starting XI
+
Captain
+
Vice-captain
+
Bench
+
Transfer recommendations
+
Hit calculation
+
Net expected gain
+
Availability warnings
+
AI explanation

Then verify:

 No future data.
 No invalid players.
 No illegal squad.
 No illegal formation.
 No illegal transfers.
 Hit calculation correct.
 Captain legal.
 Bench legal.
 All outputs reproducible.
 All tests pass.
28. Production Release

Only after all previous phases pass:

 Freeze production code.
 Freeze production feature version.
 Freeze production model.
 Freeze training dataset.
 Create release manifest.
 Create final validation report.
 Tag Git release.
 Backup models.
 Backup configuration.
 Document rollback.
 Document weekly operating procedure.
 29. FINAL MINIMUM PHASE CHECKLIST

This is the short list you should use to track the remaining project.

🔴 Critical
 A — Final Leakage & Data Validation
 B — Official xP / Ranking Formula
 C — Final Model Selection
 D — Manager Net-of-Hit Validation
 E — Multi-Season Manager Backtest
 F — Automated Test Suite
🟠 High Priority
 G — Expected Minutes / Starting Probability Integration
 H — Squad Optimizer Acceptance Tests
 I — Weekly Pipeline Hardening
 J — CLI / Operational Correctness
 K — Reproducibility
 L — 2026-27 GW1 Live Integration
🟡 Final Engineering
 M — Model Registry
 N — Repository Cleanup
 O — Dashboard/API Hardening
🟢 Release
 P — Final Acceptance Test
 Q — Production Freeze
 R — Production Release
30. The Real Remaining Work

In practical terms, you do not need to rebuild the whole project.

The project is already far beyond the foundation stage.

The remaining work is mainly:

PROVE FEATURES ARE LEAKAGE-SAFE
             ↓
DEFINE FINAL xP
             ↓
SELECT FINAL MODEL
             ↓
VALIDATE OPTIMIZER
             ↓
FIX/VALIDATE MANAGER TRANSFERS
             ↓
BACKTEST COMPLETE MANAGER
             ↓
COMPARE AGAINST BASELINES
             ↓
AUTOMATE TESTS
             ↓
RUN REAL GW1
             ↓
FINAL ACCEPTANCE
             ↓
RELEASE

The single biggest remaining question is not:

"Can the ML model predict FPL points?"

It is:

"Does the complete system make better legal FPL decisions than reasonable baseline strategies when it is only allowed to use information available at that historical moment?"

Once that question is answered positively and the engineering tests pass, the project can move from development to production operation.
















































