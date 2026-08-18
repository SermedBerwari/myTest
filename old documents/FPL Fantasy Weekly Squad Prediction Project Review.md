# FPL Fantasy Weekly Squad Prediction Project Review

**Author:** Manus AI  
**Review date:** 17 August 2026  
**Scope:** Review of the project in its current state only; no production changes were made.

## Executive evaluation

The project is **a substantial working prototype, but not yet a production-ready weekly FPL decision system**. It has a credible end-to-end shape: FPL data collection, raw-data validation, historical normalization, feature construction, baseline modeling, expected-points ranking, squad optimization, manager-style transfer logic, external-intelligence artifacts, a weekly pipeline, and a small FastAPI dashboard. The strongest evidence is that the repository contains real FPL snapshots, four historical seasons in processed data, a validated 2026–27 bootstrap/fixture snapshot, model and backtest artifacts, and a current 15-player squad configuration.

The main limitation is not the absence of components. It is the absence of a single, reproducible, leakage-safe and sufficiently tested path that proves the **weekly recommendation is reliable and operationally safe**. The current evidence demonstrates that pieces run and that some ranking/backtest metrics are reasonable; it does not yet demonstrate that the recommended squad, captain, bench order, transfers, hit decisions, and availability handling outperform transparent baselines under walk-forward simulation across the full historical period.

| Area | Current assessment | Confidence | Main reason |
|---|---:|---:|---|
| Data collection and raw validation | Strong prototype | High | Real snapshots exist; the 2026–27 raw validation report is marked `PASSED` with 1,170 JSON files checked and no invalid latest player snapshots. |
| Historical processing and feature engineering | Partially complete | Medium | Multiple seasons and feature manifests exist, but processed inspection reports zero current-season player-gameweek rows, and the repository contains several versioned preparation scripts that require consolidation. |
| Expected-points modeling | Working baseline | Medium | Ridge and rolling-average results exist; the Ridge benchmark reports MAE 0.9601 and RMSE 1.9354, but advanced-model superiority is not established in the reviewed artifacts. |
| Squad optimization | Functional component | Medium | A 15-player optimizer and starting-XI logic exist, but transfer and hit behavior still need systematic historical validation. |
| Manager simulation and backtesting | Incomplete evidence | Medium-low | Backtest artifacts exist, but the reviewed results do not establish a complete apples-to-apples comparison across all intended seasons and decision policies. |
| Weekly automation | Demonstrated once / prototype | Medium | A weekly summary exists for target GW1 with a real 15-player input, but the report contains a very large gross transfer recommendation that becomes negative after hits. |
| Dashboard/API | Minimal working shell | Medium-low | FastAPI exposes summary and pipeline-trigger routes, but there is no visible player endpoint despite the application description mentioning one, and the UI is not backed by a documented test suite. |
| Testing and maintainability | Weak | High | The `tests/` directory contains only `__init__.py` and a placeholder `.gitkeep`; pytest is not installed in the project environment. |
| Production readiness | Not ready | High | Reproducibility, automated regression tests, model versioning, operational safeguards, and decision-quality validation remain incomplete. |

## What is already done

### 1. The repository has a coherent project architecture

The project is organized into `src/`, `scripts/`, `data/`, `config/`, `web/`, `tests/`, and `logs/`. The scripts cover collection, historical normalization, feature generation, model training, expected-points evaluation, optimization, manager simulation, external intelligence, and weekly execution. This is a good foundation because the project is not merely a notebook or isolated model; it attempts to represent a complete decision pipeline. The structure is documented in `README.md` and the completion plan.

### 2. Real FPL data collection and validation are substantially implemented

The raw-data area contains 2026–27 bootstrap and fixture snapshots plus player-specific snapshot directories. The stored validation artifact reports `status=PASSED`, 1,170 JSON files checked, 584 bootstrap players, 20 teams, 38 gameweeks, 380 fixtures, zero duplicate player IDs, zero duplicate fixture IDs, zero invalid latest player snapshots, and zero missing player directories. This is meaningful progress toward a reliable ingestion layer. Evidence: `data/validation/2026-27/validation_report_2026-27.json`.

The processed-data inspection also reports `status=PASS`, 20 teams, 584 players, 38 gameweeks, 380 fixtures, zero errors, and 24 warnings. The warnings appear to be dominated by expected pre-season/current-season sparsity and missing fields in FPL data rather than immediate structural failure. However, warnings need to be classified and enforced explicitly before production use. Evidence: `data/validation/2026-27/processed_inspection_report_2026-27.json`.

### 3. Historical data coverage exists across multiple seasons

The processed directory contains seasons `2022-23`, `2023-24`, `2024-25`, `2025-26`, and `2026-27`. The xP diagnostic artifact states that its dataset covers 2022–23 through 2025–26, with target gameweeks 2–38. This is better than relying on a single season and is consistent with the completion plan's stated requirement to avoid single-season validation.

The project also has manifests for normalized data, feature construction, and training datasets. That is a positive reproducibility practice. The remaining issue is that multiple historical-preparation versions coexist, including `prepare_historical_for_features.py`, `v2.py`, `v2_2.py`, and top-level helper scripts. The project needs one canonical path and a clear version policy.

### 4. Baseline modeling and ranking diagnostics are present

The repository contains historical average and rolling-average baselines as well as a Ridge linear regression benchmark. The stored results show the following metrics:

| Strategy | MAE | RMSE | Interpretation |
|---|---:|---:|---|
| Historical average, last three | 1.0544 | 2.1783 | Simple reference baseline. |
| Rolling average, GW3 | Not reliably surfaced in the reviewed scalar output | Not reliably surfaced | Present in the artifact, but should be reported consistently. |
| Rolling average, GW5 | 1.0490 | 2.1163 | Slightly better than the historical average. |
| Rolling average, GW10 | 1.0522 | 2.0783 | Similar MAE, lower RMSE. |
| Ridge linear regression | 0.9601 | 1.9354 | Best of the clearly surfaced baselines. |

The walk-forward artifact for season 2025–26 reports overall MAE 0.9869 and RMSE 1.9287 across 37 gameweeks. These results suggest that the model layer has predictive signal. They do **not** by themselves prove that the final squad selection produces better fantasy outcomes, because player-level error metrics and top-ranked-player metrics are not equivalent to squad-level points, captaincy, bench, transfers, or hits.

The xP ranking diagnostic reports approximately 0.71 mean Spearman rank correlation for the evaluated formulas, but top-10 precision is low, roughly 0.14–0.17 depending on formula and aggregation. The minutes-adjusted formula does not clearly improve the raw formula in the stored diagnostic. This is an important finding: ranking quality is usable as a starting point, but the decision layer should not assume that a high rank correlation guarantees correct top picks.

### 5. A real 15-player squad input and manager output exist

`config/my_squad.json` contains 15 player IDs, one free transfer, and zero bank. The weekly summary reports a real-squad input count of 15 and produces an optimal squad, starting XI, bench, captain, and manager recommendation. This is materially better than a pipeline that only optimizes a synthetic pool without accepting the user's current squad.

The project also includes an external-intelligence artifact and an AI decision-report generator. These show that the intended product is not only a numeric optimizer but also a human-readable decision assistant.

### 6. The squad optimizer includes important FPL constraints

The optimizer code includes validation for unique player IDs, required player-pool columns, squad size, positional limits, starting-XI formation constraints, team limits, bank constraints, and current-squad resolution. The manager-engine code also attempts to account for free transfers, hit penalties, replacement feasibility, and captain selection. These are the right categories of constraints for an FPL decision engine.

## What remains and why it matters

### 1. The final recommendation path is not yet proven leakage-safe end to end

The completion plan correctly identifies leakage-safe temporal validation as the central milestone. The repository has leakage-policy fields in manifests and a walk-forward artifact, but the review did not find a complete, automated audit that proves every feature, model input, external-intelligence signal, transfer decision, and manager simulation uses only information available before the target gameweek.

This matters because FPL features such as final minutes, final points, injury status, fixture outcomes, and post-gameweek player histories can leak into training or ranking if the cutoff is applied inconsistently. The project should make the temporal cutoff an explicit parameter passed through collection, feature construction, model prediction, optimizer input, and evaluation, then add tests that fail on any future row or future-derived column.

### 2. The manager decision layer still shows behavior that is not decision-ready

The current weekly summary reports current expected points of approximately 41.96, an unconstrained or gross optimal expected-points figure of approximately 60.73, 15 transfers, 56 points of hit penalty, and a net expected gain of approximately -37.23. The stored recommendation therefore correctly recognizes that the gross gain does not justify the hit cost, but the size of the gross transfer set is still a major diagnostic signal. A production manager engine should usually compare a small, explicit set of legal policies—zero transfers, one transfer, two transfers, free-transfer-only, and hit-allowed—and return the best **net** policy directly rather than producing an extreme gross target and explaining it away afterward.

The same weekly artifact reports one availability warning. The warning pathway is present, but it must be demonstrated with controlled cases: unavailable player, doubtful player, missing chance-of-playing value, newly transferred player, suspended player, and a player without enough history. The correct behavior should be tested for selection, bench order, captain, vice-captain, and transfer recommendations.

### 3. Historical manager simulation is present but not yet an adequate acceptance test

The historical manager artifact covers 2023–24, 2024–25, and 2025–26 and contains strategies including `ai_manager` and `previous_gw`. One surfaced result for a strategy reports 1,566 actual points, 70 transfers, 34 hits, 37 weeks, 352 bench points wasted, and 42.32 average gameweek points. These are useful diagnostic fields, but the review did not find a concise benchmark table demonstrating that the AI manager beats clearly defined alternatives after transfer penalties and under identical information constraints.

The acceptance test should include at least a no-transfer strategy, a previous-gameweek strategy, rolling-average xP, model xP with free transfers only, model xP with hit decisions, and an idealized upper bound. It should report total points, points per gameweek, transfer count, hits, captain points, bench points lost, rank/top-percentile proxies if available, and confidence intervals or season-by-season variation.

### 4. Advanced model usage is not established by the stored evidence

The repository contains training scripts for advanced models and a tracked `data/models/xgboost_model.json`, as well as CatBoost training logs. However, the reviewed result artifacts primarily expose baseline and diagnostic outputs. There is no compact, authoritative model registry showing which model is currently used in production, its feature schema, training cutoff, training data hash, version, validation metrics, and relationship to the weekly pipeline.

The project should avoid adding more models until it can answer five questions reproducibly: which model is active, what exact features it consumes, what temporal cutoff it used, what baseline it beats, and whether the improvement survives squad-level walk-forward evaluation. A modestly better player-level error metric is not sufficient evidence for a better FPL manager.

### 5. Automated testing is the largest engineering gap

The test suite is effectively empty: `tests/` contains only `__init__.py` and `collectors/.gitkeep`, and the environment does not have pytest installed. Syntax compilation passes for `app.py`, `src`, `scripts`, and `tests`, and dependency checking reports no broken installed requirements, but compilation is not behavioral validation.

At minimum, the project needs unit tests for data validation, feature cutoff behavior, expected-points formulas, minutes adjustment, squad constraints, formation legality, team limits, budget handling, transfer and hit arithmetic, captain/vice-captain logic, unavailable-player handling, duplicate IDs, missing columns, and deterministic output. It also needs integration tests for the weekly pipeline and manager engine using a small fixed fixture dataset.

### 6. The manager engine CLI has a clear usability defect

Running `scripts/optimizer/manager_engine.py --help` does not display help. It executes a sample manager-engine calculation, prints a demo result, and writes a sample report. This indicates that the script lacks a proper argument parser or does not honor the conventional help flag. It is a direct reproducibility and automation risk: orchestration systems, users, and deployment checks cannot safely discover the interface.

The CLI should support explicit arguments for season, gameweek, player pool, current squad, bank, free transfers, output path, and model version. A help invocation should be side-effect free. Demo behavior should be moved into a separate example script or protected behind an explicit `--demo` flag.

### 7. The weekly pipeline and dashboard need production hardening

The FastAPI application exposes `/api/summary`, `/api/run-pipeline`, and `/`. The frontend has a button to rerun the pipeline. This demonstrates a usable shell, but the reviewed code does not provide evidence of authentication, concurrency protection, request validation, job status tracking, failure recovery, or a documented deployment configuration. A publicly reachable rerun endpoint could trigger expensive or conflicting jobs if exposed without safeguards.

The application docstring mentions a `GET /api/players` endpoint, but the route scan found only `/api/summary`, `/api/run-pipeline`, and `/`. The documentation and implementation should be made consistent. The dashboard should also show data timestamp, target gameweek, model version, warning count, last successful run, and whether the current recommendation is based on complete or partial data.

### 8. Documentation and dependency declaration are too thin for handoff

`README.md` documents the broad folder structure and basic setup, but it does not explain the canonical pipeline, expected inputs, output schemas, model training workflow, data cutoff policy, validation commands, or how to interpret recommendation warnings. `requirements.txt` declares only `pandas` and `requests`, although the code and environment use additional packages such as FastAPI, scikit-learn, CatBoost/XGBoost-related tooling, NumPy, and an integer-programming solver. The environment happens to pass `pip check`, but a clean-machine installation from the declared requirements is not demonstrably sufficient.

The project needs a locked or fully declared environment, a one-command setup, a one-command validation run, a one-command weekly run, and a data/model artifact manifest. Generated outputs should be clearly separated from source data and should not be modified accidentally by smoke tests.

### 9. Repository hygiene needs improvement

The working tree contains modified CatBoost logs and manifests plus untracked diagnostic scripts and outputs. A tracked 1.87 MB XGBoost model artifact exists, while generated CSV outputs are ignored. This is not inherently wrong, but the project lacks a clear policy for which models and reports are versioned, which are reproducible build outputs, and which are local diagnostics. Several historical-preparation script variants and top-level helper scripts also suggest active experimentation that has not yet been consolidated into a stable release path.

## Prioritized remaining-work plan

| Priority | Work package | Definition of done |
|---|---|---|
| P0 | Freeze one canonical weekly pipeline | One documented command accepts season, GW, current squad, bank, and free transfers; it produces a versioned report with inputs, cutoff, model, warnings, legal squad, XI, bench, captain, vice-captain, and net transfer recommendation. |
| P0 | Add leakage and temporal-cutoff tests | Automated tests prove that target-GW features use only pre-GW information and that external signals are timestamped and filtered. |
| P0 | Make manager decisions net-of-hits | The optimizer directly selects among legal transfer policies using net expected gain, with explicit free-transfer and hit accounting. Extreme gross-transfer solutions should not be the primary output. |
| P0 | Build a real automated test suite | At least unit and integration coverage for validators, features, formulas, optimizer constraints, manager arithmetic, availability, and pipeline output schemas. |
| P1 | Establish a model registry and benchmark table | Record active model, version, feature set, training cutoff, dataset hash, MAE/RMSE, rank metrics, and squad-level walk-forward results against baselines. |
| P1 | Complete multi-season manager backtesting | Run identical policies across 2022–23 through 2025–26 where data permits; report points, transfers, hits, captain points, bench waste, and season variation. |
| P1 | Consolidate historical and feature scripts | Choose one canonical normalization and feature-builder path; archive or clearly label experimental variants. |
| P1 | Harden the API and dashboard | Align route documentation with implementation, add job locking/status, validate inputs, handle failures, and display data/model freshness and warnings. |
| P2 | Improve data-quality policy | Convert the 24 processed-data warnings into categorized expected warnings versus blocking errors, with thresholds and alerting. |
| P2 | Complete documentation and environment setup | Expand README, declare all runtime dependencies, add reproducible setup, and document artifacts and operational procedures. |
| P2 | Clean repository outputs | Decide which logs, models, diagnostics, reports, and manifests are tracked; keep smoke tests side-effect free. |

## Recommended release gate

The project should not be described as production-ready until it passes the following gate. First, a clean environment must install the declared dependencies and run the validation and weekly pipeline commands without manual edits. Second, the same input snapshot must produce deterministic outputs apart from explicitly recorded timestamps. Third, temporal leakage tests must pass. Fourth, manager simulation must demonstrate legal, net-of-hit behavior across multiple seasons against transparent baselines. Fifth, the API must expose only documented, validated, side-effect-controlled operations. Finally, the project should produce a human-readable report that makes uncertainty and data-quality warnings visible rather than hiding them.

## Final conclusion

The project is **approximately at the advanced prototype / pre-production validation stage**. The data layer and broad component architecture are the most mature parts. Baseline prediction and optimization are operational enough to generate a weekly-looking result. The critical remaining work is validation discipline: proving that the end-to-end weekly recommendation is temporally honest, legally constrained, economically sensible after hits, stable across seasons, tested, and reproducible from a clean installation.

The best next move is therefore **not another model**. The best next move is to stabilize and test the existing manager pipeline, formalize the model registry and backtest protocol, and make the release gate pass. Once that is complete, model improvements can be evaluated on the metric that matters: improvement in simulated FPL decisions after captaincy, benching, transfers, hits, and uncertainty are all included.

## Evidence references

[1]: `README.md` — project structure, setup, and development overview.

[2]: `FPL_PROJECT_COMPLETION_AND_FIX_PLAN.md` — stated completion criteria, leakage-safety requirements, benchmark expectations, and remaining milestones.

[3]: `data/validation/2026-27/validation_report_2026-27.json` — raw-data validation status, file counts, snapshots, duplicates, and collection checks.

[4]: `data/validation/2026-27/processed_inspection_report_2026-27.json` — processed-data status, schema checks, business rules, warnings, and row counts.

[5]: `data/processed/baseline_model_results.json` — baseline model metrics.

[6]: `data/processed/backtest_results.json` — 2025–26 walk-forward error metrics.

[7]: `data/processed/xp_ranking_diagnostic.json` — ranking correlation, top-k precision, and points-capture diagnostics.

[8]: `data/processed/xp_formula_diagnostic.json` — formula comparison scope and target-gameweek coverage.

[9]: `data/processed/historical_manager_simulation.json` — multi-season manager-simulation outputs.

[10]: `data/processed/weekly_automation_summary.json` — current 2026–27 GW1 weekly output, squad size, transfer recommendation, hit penalty, and warning state.

[11]: `config/my_squad.json` — configured 15-player squad, bank, and free-transfer inputs.

[12]: `app.py`, `web/index.html` — dashboard/API routes and frontend pipeline interaction.

[13]: `scripts/weekly_pipeline.py`, `scripts/optimizer/manager_engine.py`, `scripts/optimizer/squad_optimizer.py` — weekly orchestration, manager decisions, and squad constraints.

[14]: `tests/` — current test-directory contents.

[15]: `requirements.txt`, `.gitignore`, and `git status` — declared dependencies and repository-hygiene evidence.

## Validation performed during this review

Syntax compilation across `app.py`, `src`, `scripts`, and `tests` passed. Installed-package dependency checking passed. The project environment did not contain pytest, and the test directory contained no substantive automated test modules. The weekly pipeline CLI responded to `--help`; the manager-engine script instead executed a sample run when invoked with `--help`, which was recorded as a production-readiness defect. No source changes were made as part of this review.
