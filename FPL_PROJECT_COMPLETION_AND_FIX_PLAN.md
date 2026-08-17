# FPL Fantasy Prediction — Project Completion & Fix Plan

**Repository:** `SermedBerwari/myTest`  
**Source of truth:** current `PLAN TRACKER.md`, repository structure, and implementation audit.

## Executive Summary

The project has a strong foundation and should **not be restarted**.

The major remaining problem is not another ML model. It is converting the existing components into one **leakage-safe, end-to-end FPL manager system** and proving that system works through historical simulation.

Current priority:

> **Integrate prediction + expected minutes + intelligence + optimization + transfers + captaincy into a historical manager simulator, then benchmark it against simple strategies.**

---

# 1. Completed Work

## Historical Data Foundation
**Status: COMPLETE / KEEP**

- Historical seasons collected and normalized.
- Historical audit performed.
- Team-ID mapping issues investigated/resolved.
- Duplicate fixture/gameweek behavior checked.
- 2021-22 intentionally excluded.

## Feature Engineering
**Status: STRONG FOUNDATION / KEEP**

The feature builder enforces the key temporal rule:

> For target GW N, historical observations must come from gameweeks `< N`.

Historical player-team relationships are derived from historical fixtures rather than blindly using current team assignments.

Tracker reports:
- ~110,025 training rows
- 142 feature columns
- consistent feature schema across seasons

**Action:** do not rewrite the feature engine unless a concrete validation failure appears.

## Baseline Models
**Status: COMPLETE / VALID BENCHMARK**

Implemented:
- Historical average
- Rolling average
- Ridge

Keep these as benchmark models.

## Advanced Models
**Status: IMPLEMENTED / VALID HOLDOUT BENCHMARK**

Implemented:
- XGBoost
- LightGBM
- CatBoost

Reported best:
- CatBoost MAE ≈ **0.9516**

This is only a modest improvement over the reported Ridge benchmark. Do not assume that more model complexity is the main path to improvement.

## Walk-Forward Prediction
**Status: IMPLEMENTED / PARTIALLY VALIDATED**

The current backtest uses an expanding chronological window, which is the correct general direction.

Reported:
- MAE ≈ **0.9869**
- 37 gameweeks

Limitation: this is primarily a player-prediction backtest and does not yet prove that the complete FPL manager works across multiple seasons.

## Expected Minutes
**Status: IMPLEMENTED / NEEDS INTEGRATION**

Implemented:
- minutes regression
- starting probability classifier

But the downstream decision pipeline does not yet clearly demonstrate that these outputs are integrated into decision-ready expected points.

## Squad Optimizer
**Status: IMPLEMENTED / NEEDS REAL-DATA VALIDATION**

The ILP structure includes the basic FPL constraints:
- 15 players
- 2 GK
- 5 DEF
- 5 MID
- 3 FWD
- maximum 3 players per real team
- budget constraint

Problem: its prototype/smoke-test path uses synthetic values such as:
- `team_id = player_id % 20`
- `cost = 5.5`
- rolling historical points instead of model predictions

Therefore the optimizer has not yet been proven with the real production player pool.

**Action:** keep the ILP design; replace synthetic inputs with real FPL data and model outputs.

## Manager Engine
**Status: IMPLEMENTED / REQUIRES FIX**

The old implementation silently replaced an incomplete current squad with an optimized squad. That can invalidate transfer calculations.

A corrected replacement has been prepared:
- requires exactly 15 players
- rejects duplicate IDs
- rejects missing players
- validates 2/5/5/3 positions
- validates max 3 players per team
- calculates current xP from the actual squad
- validates transfer IN/OUT counts
- removes synthetic team IDs/prices from the test path

File prepared:
`manager_engine_fixed.py`

Replace:
`scripts/optimizer/manager_engine.py`

Then run:
```powershell
python scripts\optimizer\manager_engine.py
```

## External Intelligence
**Status: IMPLEMENTED / NEEDS DECISION-PIPELINE VALIDATION**

External intelligence can produce signals, but those signals need to affect actual decision variables such as:
- availability
- expected minutes
- eligibility
- confidence
- captaincy risk
- transfer decisions

## AI Decision Agent
**Status: IMPLEMENTED / NEEDS DECISION-QUALITY VALIDATION**

The agent exists, but its existence does not demonstrate that it improves historical FPL decisions.

It needs historical evaluation of:
- captain
- vice captain
- transfers
- hits
- starting XI
- final weekly points

## Weekly Pipeline
**Status: IMPLEMENTED / NOT PRODUCTION READY**

The pipeline exists, but the current implementation contains sample/demo behavior rather than a demonstrated real-user workflow.

It needs to accept the actual 15-player squad and run the complete production decision chain.

---

# 2. Critical Missing Phase

## End-to-End Historical Manager Simulation
**Status: NOT DONE**

This is the most important remaining milestone.

The simulator must behave as if it were living in the historical season.

For every GW:

```text
Only information available before GW N
        ↓
Build features
        ↓
Predict player points
        ↓
Predict expected minutes / starting probability
        ↓
Apply external intelligence
        ↓
Create decision-ready xP
        ↓
Optimize squad
        ↓
Compare against actual squad
        ↓
Decide transfers
        ↓
Decide hits
        ↓
Select starting XI
        ↓
Select captain / vice captain
        ↓
Score actual GW
        ↓
Update squad
        ↓
Next GW
```

This must be leakage-safe.

---

# 3. Required Benchmarks

Compare the AI manager against at least:

1. Previous-GW strategy
2. Rolling-average xP strategy
3. No-transfer strategy
4. Simple highest-xP optimizer
5. AI manager

Measure:
- total season points
- average GW points
- captain points
- transfers
- hits
- transfer gains
- bench points
- starting XI points
- minutes-related errors

---

# 4. Multi-Season Validation

Do not rely on only one historical season.

Recommended:

```text
2022-23
2023-24
2024-25
2025-26
```

Each simulation must use only information that would have been available at that point in time.

---

# 5. Separate Prediction Quality From Decision Quality

## Prediction layer

Evaluate:
- MAE
- RMSE
- calibration where appropriate
- expected-minutes accuracy

## Decision layer

Evaluate:
- weekly points
- season points
- captain performance
- transfer performance
- hit efficiency
- squad efficiency

A lower prediction MAE does not automatically mean a better FPL manager.

---

# 6. Exact Fix Order

## FIX 1 — Manager Engine
Replace `scripts/optimizer/manager_engine.py` with the prepared corrected version.

Run:
```powershell
python scripts\optimizer\manager_engine.py
```

Do not move on until the result is checked.

## FIX 2 — Weekly Pipeline
Inspect `scripts/weekly_pipeline.py`.

Remove sample/demo squad behavior.

The pipeline must accept a real 15-player squad.

## FIX 3 — Expected Minutes Integration
Connect:
```text
points model
+
minutes regressor
+
starting classifier
```

to a defined, validated decision-ready expected-points calculation.

## FIX 4 — External Intelligence
Integrate availability/news signals into:
- expected minutes
- player eligibility
- confidence/risk
- transfer/captain decisions

## FIX 5 — Real-Data Optimizer
Replace all synthetic:
- team IDs
- prices
- expected points

with real production values.

## FIX 6 — Historical Manager Simulator
Build the full GW-by-GW simulation.

## FIX 7 — Strategy Benchmarking
Run the same historical periods against the baseline strategies.

## FIX 8 — Captain / Transfer / Hit Optimization
Only after the simulator works.

## FIX 9 — AI Decision Agent Validation
Measure whether the AI layer improves decisions.

## FIX 10 — Production Weekly Pipeline
Only after historical simulation passes.

---

# 7. Do NOT Do Yet

Do not:
- add another ML model merely because CatBoost only modestly beats Ridge
- rewrite the feature engine without evidence
- optimize the LLM/AI agent first
- build a custom MCP server yet
- add complicated external data sources before validating the core system
- claim the manager is production-ready
- perform extensive hyperparameter tuning before decision-level validation

The project currently needs **integration and validation more than complexity**.

---

# 8. Definition of Done

## Data
- [ ] Historical seasons validated
- [ ] No unexplained duplicate fixture/player records

## Features
- [ ] Target GW features use only information available before that GW
- [ ] Feature schema stable
- [ ] Leakage audit passes

## Models
- [ ] Baseline benchmarks recorded
- [ ] CatBoost benchmark recorded
- [ ] Walk-forward validation recorded
- [ ] Minutes model validated

## Optimizer
- [ ] Real FPL prices
- [ ] Real team IDs
- [ ] Real positions
- [ ] Real model predictions
- [ ] All squad constraints validated

## Manager
- [ ] Real current 15-player squad
- [ ] Free-transfer logic
- [ ] Hit logic
- [ ] Bank logic
- [ ] Transfer IN/OUT validation
- [ ] Captain / vice captain

## Intelligence
- [ ] Availability signals integrated
- [ ] Minutes impact validated
- [ ] Decision impact demonstrated

## Backtesting
- [ ] Multi-season simulation
- [ ] No future-information leakage
- [ ] AI manager benchmarked against simple strategies

## Production
- [ ] Real current FPL data
- [ ] Weekly pipeline
- [ ] Real squad input
- [ ] Automated report
- [ ] Regression tests
- [ ] Reproducible model versions

---

# 9. Current Priority

The single most important objective is:

> **Turn the existing collection of working components into one leakage-safe, end-to-end historical FPL manager simulator.**

Once that simulator exists, we can determine whether the project actually produces better FPL decisions.

Until then, individual model improvements are secondary.

---

# 10. Working Rule

For every change:

```text
CHANGE
  ↓
RUN TEST
  ↓
CHECK OUTPUT
  ↓
COMPARE AGAINST BASELINE
  ↓
KEEP / REVERT
```

Use Git branches/commits so changes are reversible.

Recommended branch:
```text
ai-fpl-audit
```

Keep `main` stable.

---

# 11. Immediate Next Action

After replacing `manager_engine.py`:

```powershell
cd "E:\Python\FPL Fantasy Predictiom"
python scripts\optimizer\manager_engine.py
```

Send the complete output.

Then proceed to **FIX 2 — `weekly_pipeline.py`**.
