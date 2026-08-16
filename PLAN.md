# Plan: FPL Fantasy Prediction — Complete Phases Task Plan

**TL;DR**: The project is 30% complete (phases 0-3) and needs to finish historical normalization, complete feature engineering, then build prediction models sequentially (baseline → advanced → minutes → backtesting → optimizer → AI agent). The immediate blocker is recollecting genuine 2021-22 data; after that, 7 specific tasks unblock the remaining 13 phases. Total estimated delivery: 12–18 weeks to production-ready system.

---

## Immediate Priorities (Next 7 Steps)

These must be completed in sequence; each unblocks the next.

### Step 1 — Fix 2021-22 (Blocker)
**Objective**: Replace invalid duplicate with genuine 2021-22 data
- Find authentic 2021-22 Premier League stats source
- Verify: correct season dates (Aug 2021–May 2022), 38 gameweeks, ~380 fixtures
- Recollect and store in `data/raw/2021-22/historical_source/`
- Generate `collection_manifest.json`
- Compute SHA-256 hash to confirm it differs from current file
- **Status**: 🔴 BLOCKED — Requires external data source

### Step 2 — Normalize Remaining Historical Seasons
**Objective**: Complete Phase 3 normalization
- Run: `python scripts\data\normalize_historical_seasons_v1_4.py --seasons 2022-23 --force`
- Run: `python scripts\data\normalize_historical_seasons_v1_4.py --seasons 2024-25 --force`
- Run: `python scripts\data\normalize_historical_seasons_v1_4.py --seasons 2021-22 --force` (after Step 1)
- Verify: all five seasons have `data/processed/SEASON/historical/{player_gameweek.csv, fixtures.csv, normalization_manifest.json}`
- **Blockers**: Step 1
- **Status**: 🟡 READY

### Step 3 — Complete Historical Audit
**Objective**: Validate all five normalized seasons for consistency
- Check each season: row count, unique players, unique fixtures, gameweek coverage
- Verify no schema deviations across seasons
- Document any anomalies (e.g., GW7 missing in 2022-23 due to postponement)
- Generate audit report
- **Blockers**: Step 2
- **Status**: 🟡 READY

### Step 4 — Feature Engineering Audit
**Objective**: Verify leakage safety before proceeding to multi-season build
- Review `build_features_v1_3.py` for leakage patterns
- Confirm `target_gw` is excluded from `feature_columns` (metadata only)
- Test rolling-window correctness: verify GW N features only use GW 1–N-1 data
- Validate against `FPL_Feature_Engine_v1_1_Implementation_Spec.md`
- **Blockers**: Step 3
- **Status**: 🟡 READY

### Step 5 — Build Multi-Season Features
**Objective**: Generate feature datasets for all normalized seasons
- Run `build_features_v1_3.py` on 2023-24, 2025-26, and 2024-25
- Verify feature schema identical across all seasons
- Store in `data/features/SEASON/player_gameweek_features.csv`
- Generate feature manifests
- **Blockers**: Step 4
- **Status**: 🟡 READY

### Step 6 — Aggregate Training Dataset
**Objective**: Produce single unified training CSV for model training
- Concatenate all seasonal feature CSVs: 2021-22, 2022-23, 2023-24, 2024-25, 2025-26
- Columns: `season`, `player_id`, `target_gw`, `[all features]`, `target_points`
- Verify: no duplicate (player_id, target_gw) pairs, no leakage, correct time boundaries
- Output: `data/processed/training_dataset_v1.csv`
- Generate metadata: player count, gameweek range, missing-value statistics
- **Blockers**: Step 5
- **Status**: 🟡 READY

### Step 7 — Baseline Prediction Models
**Objective**: Establish reference performance before advanced models
- Implement historical-average predictor
- Implement rolling-average predictor (windows: 1, 3, 5, 10)
- Implement linear regression (scikit-learn)
- Evaluate each with chronological walk-forward validation
- Document baseline metrics: MAE, RMSE per gameweek/season
- Select best baseline as production reference
- **Blockers**: Step 6
- **Output**: Baseline benchmark + model scores
- **Status**: 🟡 READY

---

## Phases Task Breakdown (Summary)

| Phase | Title | Status | Key Artifacts | Est. Time |
|-------|-------|--------|---|---|
| **0** | Project Foundation | ✅ Complete | Config, logging, structure | — |
| **1** | Historical Collection | 🟢 Substantially Complete | 5 raw seasons (+ 2021-22 to fix) | — |
| **2** | Historical Validation | 🟢 Substantially Complete | Validation reports | — |
| **3** | Historical Normalization | 🟡 IN PROGRESS | v1.4 normalizer, manifests | 1–2 weeks |
| **4** | Leakage-Safe Features | 🟡 IN PROGRESS | Multi-season feature CSVs | 1–2 weeks |
| **5** | Training Dataset | ⏳ PENDING | Combined training CSV | 2–3 days |
| **6** | Baseline Models | ⏳ PENDING | Baseline benchmarks | 1 week |
| **7** | Advanced Models | ⏳ PENDING | XGBoost/LightGBM/CatBoost | 1–2 weeks |
| **8** | Expected-Minutes Model | ⏳ PENDING | Minutes classifier + integration | 1 week |
| **9** | Backtesting Framework | ⏳ PENDING | Walk-forward validation, performance report | 1–2 weeks |
| **10** | Squad Optimizer | ⏳ PENDING | OR-Tools solver, legal squad generator | 1–2 weeks |
| **11** | Personalized Manager Engine | ⏳ PENDING | Transfer recommender, hit evaluation | 1 week |
| **12** | External Intelligence | ⏳ PENDING | Injury/news pipeline | 1 week |
| **13** | AI Decision Agent | ⏳ PENDING | Explanation layer, guardrails | 1–2 weeks |
| **14** | Weekly Automation | ⏳ PENDING | Orchestrated pipeline, scheduling | 1 week |
| **15** | Web/Mobile App | ⏳ SKIP (for now) | — | — |
| **16** | Production Deployment | ⏳ SKIP (for now) | — | — |

---

## Detailed Workflows for Each Phase

### Phase 3 — Historical Normalization (IN PROGRESS)

**Completed**:
- ✅ normalize_historical_seasons_v1_4.py created with team-name resolution
- ✅ 2023-24 and 2025-26 already normalized

**Remaining Tasks**:
1. Recollect genuine 2021-22 (external, blocks everything)
2. Run v1.4 normalizer on 2022-23, 2024-25, then 2021-22
3. Verify all manifests generated, schema consistent
4. Document any anomalies

**Success Criteria**: All five seasons normalized, zero schema inconsistencies, manifests complete

---

### Phase 4 — Leakage-Safe Feature Engineering (IN PROGRESS)

**Current State**: build_features_v1_3.py exists; features built for 2022-23

**Tasks**:
1. Audit v1.3 for leakage (target_gw usage, rolling windows)
2. Build features for 2023-24, 2024-25, 2025-26 (reuse v1.3)
3. Verify feature schema identical across seasons
4. Generate combined feature manifest
5. Produce unified feature dataset (all seasons combined)

**Success Criteria**: No leakage detected, features consistent, multi-season dataset ready

---

### Phase 5 — Training Dataset (PENDING)

**Objective**: Convert features into supervised-learning rows

**Tasks**:
1. Concatenate all seasonal feature CSVs
2. Ensure columns: season, player_id, target_gw, [features], target_points
3. No duplicates, no leakage, correct time boundaries
4. Document missing-value policy
5. Split: chronological train/val/test boundaries

**Output**: Single `training_dataset_v1.csv`

---

### Phase 6 — Baseline Prediction Models (PENDING)

**Task Order**:
1. Historical average (all prior gameweeks for player)
2. Rolling average (windows: 1, 3, 5, 10 GWs)
3. Linear regression (all features, L2 regularization)
4. Walk-forward evaluation for each
5. Document MAE/RMSE per model
6. Select best baseline

**Success Criteria**: Baseline established; advanced models must beat it

---

### Phase 7 — Advanced Prediction Models (PENDING)

**Candidates**:
- XGBoost
- LightGBM
- CatBoost

**Tasks**:
1. Implement each model
2. Hyperparameter tuning
3. Cross-validate against baseline
4. Feature importance analysis
5. Select production model
6. Document performance lift over baseline

**Success Criteria**: Model outperforms baseline out-of-sample

---

### Phase 8 — Expected-Minutes Model (PENDING)

**Approach**:
1. Extract minutes from historical features
2. Build minutes classifier (outputs: 0, 1-45, 45-60, 60-90, 90 minutes)
3. Or: direct probabilities P(starting), P(60+), P(90)
4. Integrate with expected-points model: expected_value = expected_points × P(playing)

**Success Criteria**: Minutes model calibrated, integrated with points model

---

### Phase 9 — Backtesting Framework (PENDING)

**Critical Rule**: For GW N, train only on GW 1–N-1, predict GW N, evaluate

**Tasks**:
1. Implement walk-forward loop
2. For each gameweek: train → predict → compare to actual
3. Calculate player-level MAE/RMSE
4. Calculate squad-level cumulative points
5. Compare vs. baseline, simple average, hindsight optimal
6. Generate performance report by season/gameweek

**Success Criteria**: Multi-season backtest complete, model beats baselines

---

### Phase 10 — Squad Optimizer (PENDING)

**Technology**: Google OR-Tools

**Constraints**:
- 15 total players (2 GK, 5 DEF, 5 MID, 3 FWD)
- Starting XI: 11 players (1 GK, ≥3 DEF, ≥2 MID, ≥1 FWD)
- Budget: £100M max team value
- Max 3 from same club
- 1 captain, 1 vice-captain

**Objective**: Maximize expected points subject to constraints

**Tasks**:
1. Define constraints in code
2. Implement 15-player solver
3. Implement starting-XI selector
4. Test all squads are legal
5. Optimize for expected points

**Success Criteria**: All squads legal, budget respected, captain rules correct

---

### Phase 11 — Personalized Manager Engine (PENDING)

**Inputs**: Current squad, free transfers, money in bank, team value, chips

**Tasks**:
1. Compare current squad vs. optimal squad
2. Generate transfer recommendations
3. Evaluate hit costs (4-point penalty)
4. Support multiple transfer scenarios
5. Explain improvement potential per transfer

**Output**: "OUT: Player A (2.8 pts) → IN: Player B (6.4 pts) = +3.6 pts expected"

---

### Phase 12 — External Intelligence (PENDING)

**Tasks**:
1. Injury detection pipeline
2. Suspension detection
3. Expected-lineup collection
4. Press-conference signals
5. Validate sources
6. Integrate with minutes/risk models

**Output**: Structured injury/availability data for model features

---

### Phase 13 — AI Decision Agent (PENDING)

**Critical**: LLM must receive structured predictions only (no inventing scores)

**Tasks**:
1. Design input schema (predictions + optimizer output + injuries)
2. Explain why each player selected
3. Explain captain choice
4. Compare alternatives (e.g., "If I captain Player X instead…")
5. Generate weekly report
6. Guardrails: never override hard constraints
7. Distinguish facts (FPL data) vs. predictions vs. recommendations

**Success Criteria**: All explanations traceable to structured data

---

### Phase 14 — Weekly Automation (PENDING)

**Orchestration**:
1. Fetch FPL API (bootstrap, fixtures, player history)
2. Update feature vectors for all active players
3. Predict expected points + minutes
4. Run squad optimizer
5. Generate captain recommendations
6. Evaluate transfer options
7. Send recommendation to user/UI
8. Post-gameweek: fetch results, evaluate error, log metrics

**Scheduling**: APScheduler or Celery

**Success Criteria**: Fully automated, error-logged, reproducible

---

## Quality Gates (Pass/Fail Before Each Phase)

| Gate | Must Verify | Pass Criteria |
|------|---|---|
| **Data Gate** | Raw data correct for each season | Valid season dates, 38 GWs, no corruption |
| **Normalization Gate** | Normalized schema consistent | Same columns, same types, all fields populated |
| **Feature Gate** | No leakage, target excluded | target_gw not in feature_columns, rolling windows correct |
| **Model Gate** | Baseline exists, model better | Model MAE < baseline MAE (out-of-sample) |
| **Optimizer Gate** | Squads always legal | 100% of generated squads pass constraint check |
| **Production Gate** | Live data isolated, reproducible | 2026-27 not touched, all models versioned |

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|---|
| 2021-22 recollection delays | Blocks phase 3 completion | Proceed with 4-season training; catch up later |
| Feature leakage undetected | Invalid model | Independent audit + unit tests before phase 5 |
| Model overfits historical data | Poor live performance | Mandatory walk-forward validation (phase 9) |
| Optimizer produces illegal squads | Product failure | Automated constraint testing in every build |
| Live data contaminated | Model corruption | Strict folder separation + read-only protection |

---

## Timeline Estimate

- **Phases 0–2**: ✅ Complete
- **Phase 3** (Normalization + 2021-22 fix): 1–2 weeks
- **Phase 4** (Feature build + audit): 1–2 weeks
- **Phase 5** (Training dataset): 2–3 days
- **Phase 6** (Baseline models): 1 week
- **Phase 7** (Advanced models): 1–2 weeks
- **Phase 8** (Minutes model): 1 week
- **Phase 9** (Backtesting): 1–2 weeks
- **Phase 10** (Optimizer): 1–2 weeks
- **Phase 11–13** (Manager + AI): 2–3 weeks
- **Phase 14** (Automation): 1 week

**Total to production-ready: 12–18 weeks** (excluding web/deployment phases 15–16)

---

## Files to Monitor/Update

- `fpl.md` — Master project documentation (update Phase status table after each phase)
- `/memories/session/plan.md` — Detailed task plan
- `/memories/repo/v1_4_patch_applied.md` — Patch status

---

## Success Criteria for Project Completion

✅ = Must have before claiming "production-ready"

- ✅ All five historical seasons valid, normalized, audited
- ✅ Feature dataset leakage-free (independent audit)
- ✅ Training dataset ready (no duplicates, correct time boundaries)
- ✅ Baseline model established + benchmarked
- ✅ Advanced model outperforms baseline (quantified out-of-sample)
- ✅ Backtesting validates across all 5 seasons + all gameweeks
- ✅ Squad optimizer produces 100% legal squads
- ✅ Expected-minutes model integrated + calibrated
- ✅ AI agent explains recommendations from structured data (no invented scores)
- ✅ Weekly automation runs end-to-end without errors
- ✅ 2026-27 live data remains isolated (no accidental contamination)
- ✅ All artifacts versioned, reproducible, documented

---

## Next Action

1. **Clarify 2021-22 data source** — Do you have access to genuine 2021-22 Premier League FPL data, or should we proceed with 4-season training?
2. **Approve Phase 3–4 scope** — Confirm you want to complete normalization and feature engineering before moving to model training?
3. **Confirm timeline expectations** — Is 12–18 weeks realistic for your use case?
