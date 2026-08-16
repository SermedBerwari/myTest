# FPL Fantasy Prediction — Complete Task Tracker

## Phase 3 — Historical Normalization
- [x] Normalize 2023-24 ✅
- [x] Normalize 2025-26 ✅
- [x] Normalize 2022-23 ✅
- [x] Normalize 2024-25 ✅
- [x] Skip 2021-22 (User decision)

## Phase 3b — Historical Audit (4 seasons)
- [x] Audit all 4 normalized seasons for schema consistency, row counts, GW coverage ✅
- [x] Resolved fixture & team mapping discrepancies (`v2.1.0` prepare script) ✅

## Phase 4 — Feature Engineering
- [x] Audit build_features_v1_3.py for data leakage ✅
- [x] Build features for 2022-23 (25,711 rows) ✅
- [x] Build features for 2023-24 (28,850 rows) ✅
- [x] Build features for 2024-25 (26,799 rows) ✅
- [x] Build features for 2025-26 (28,905 rows) ✅
- [x] Verify feature schema is identical across all seasons (142 columns) ✅

## Phase 5 — Training Dataset
- [x] Concatenate all 4 seasonal feature CSVs into `training_dataset_v1.csv` (110,025 rows) ✅
- [x] Validate zero duplicate keys across double gameweek fixtures ✅
- [x] Generate dataset manifest (`training_dataset_v1_manifest.json`) ✅

## Phase 6 — Baseline Models
- [x] Historical-average predictor (MAE: 1.0544, RMSE: 2.1783) ✅
- [x] Rolling-average predictor (GW3, GW5, GW10) (MAE: 1.0490 - 1.0544) ✅
- [x] Ridge Linear Regression (MAE: 0.9601, RMSE: 1.9354) ✅
- [x] Output benchmark results (`baseline_model_results.json`) ✅

## Phase 7 — Advanced Models
- [x] XGBoost Regressor (MAE: 0.9697, RMSE: 1.9447) ✅
- [x] LightGBM Regressor (MAE: 0.9659, RMSE: 1.9450) ✅
- [x] CatBoost Regressor (MAE: 0.9516, RMSE: 1.9460) ✅ (+0.89% lift over Ridge)
- [x] Save trained model artifacts (`xgboost_model.json`, `lightgbm_model.pkl`, `catboost_model.cbm`) ✅

## Phase 8 — Expected-Minutes Model
- [x] Minutes Regressor (CatBoost) — MAE: 12.29 mins ✅
- [x] Starting Classifier (CatBoost) — Accuracy: 89.14% ✅
- [x] Save minutes model artifacts (`minutes_regressor.cbm`, `starter_classifier.cbm`) ✅

## Phase 9 — Backtesting Framework
- [x] Chronological walk-forward loop (train GW 1..N-1, predict N for 2025-26) ✅
- [x] Overall out-of-sample MAE: 0.9869, RMSE: 1.9287 across 37 gameweeks ✅
- [x] Generate backtest report (`backtest_results.json`) ✅

## Phase 10 — Squad Optimizer
- [x] Google OR-Tools ILP Solver implementation (`squad_optimizer.py`) ✅
- [x] 15-player squad with all FPL constraints (2 GK, 5 DEF, 5 MID, 3 FWD, budget <= £100M, max 3/team) ✅
- [x] Starting XI & Captain/Vice-Captain selection ✅

## Phase 11 — Personalized Manager Engine
- [x] Transfer recommender (`manager_engine.py`) ✅
- [x] Hit penalty evaluation (-4 pts per extra transfer) ✅
- [x] Net expected points gain calculation (Delta xP) ✅

## Phase 12 — External Intelligence
- [x] Injury/suspension/news signal extraction pipeline (`external_intelligence.py`) ✅
- [x] Save availability matrix (`external_intelligence_signals.json`) ✅

## Phase 13 — AI Decision Agent
- [x] Natural language decision report & explanation layer (`ai_decision_agent.py`) ✅
- [x] Output structured rationale (`ai_decision_report.json`) ✅

## Phase 14 — Weekly Automation
- [x] End-to-end orchestrated pipeline (`weekly_pipeline.py`) ✅
- [x] Output pipeline summary (`weekly_automation_summary.json`) ✅
