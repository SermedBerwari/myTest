# FPL Feature Engine v1.1 — Production Extension Specification

## Purpose

Extend the existing:

`scripts/features/build_features.py`

without rewriting or removing the existing v1.0 feature engine.

The current v1.0 implementation is the baseline and must remain leakage-safe.

This document is the implementation map for the next coding step.

---

## 1. Non-Negotiable Rules

### Preserve v1.0

Do not:

- rewrite existing feature calculations
- rename existing feature columns
- remove existing features
- change existing rolling-window semantics
- change target definitions
- change existing output structure unless required for the new columns

### Leakage boundary

For target gameweek `N`:

```text
feature information <= GW N-1
target information   = GW N
```

Equivalent implementation rule:

```python
history = player_rows[player_rows["GW"] < target_gw]
target = player_rows[player_rows["GW"] == target_gw]
```

No feature may use target-GW results.

---

# 2. Existing v1.0 Feature Groups

Keep these unchanged:

- player historical performance
- rolling 3/5/10 features
- minutes/history features
- starts and appearance features
- fixture/team/opponent context already implemented
- double-gameweek handling
- target construction
- existing leakage exclusions
- existing output/manifest behavior

---

# 3. v1.1 Feature Groups

Add the following groups.

## A. Player Involvement / Per-90

### Features

```text
points_per_90
goals_per_90
assists_per_90
bonus_per_90
bps_per_90
xG_per_90
xA_per_90
xGI_per_90
```

### Rolling versions

Where source columns exist:

```text
rolling_3_xG_per_90
rolling_5_xG_per_90
rolling_10_xG_per_90

rolling_3_xA_per_90
rolling_5_xA_per_90
rolling_10_xA_per_90
```

Use prior completed gameweeks only.

Do not calculate these from target-GW values.

---

# 4. Team / Opponent Strength

Create historical, pre-target-GW team strength.

Recommended features:

```text
team_goals_for_last_3
team_goals_for_last_5

team_goals_against_last_3
team_goals_against_last_5

team_clean_sheets_last_5
team_points_last_5

opponent_goals_for_last_3
opponent_goals_for_last_5

opponent_goals_against_last_3
opponent_goals_against_last_5

opponent_clean_sheets_last_5
opponent_points_last_5
```

If reliable xG/xGC fields are available:

```text
team_xG_last_5
team_xGC_last_5

opponent_xG_last_5
opponent_xGC_last_5
```

Do not use final-season aggregates.

All strength values must be calculated as-of the prediction cutoff.

---

# 5. Player Team-Share Features

Where the historical source supports the required statistics:

```text
team_goal_share
team_assist_share
team_xG_share
team_xA_share
team_xGI_share
```

Definition example:

```text
player_xG / team_xG
```

Use only information available before the target GW.

Handle zero denominators safely.

---

# 6. Weighted Form

Add recency-weighted form.

Recommended:

```text
weighted_points_3
weighted_points_5
weighted_points_10

weighted_xG_5
weighted_xA_5
```

Recent gameweeks receive greater weight.

Example conceptual weighting:

```text
most recent > previous > older
```

The exact weighting should be implemented consistently and documented.

Do not tune weights using future target data.

---

# 7. Trend Features

Add:

```text
points_trend
xG_trend
xA_trend
minutes_trend
starts_trend
```

Preferred initial approach:

Compare recent window against an older window.

Example:

```text
points_trend =
mean(last_3) - mean(previous_3)
```

Only use observations before the target GW.

---

# 8. Fixture-Run Features

The next fixtures are known before the deadline, so future fixture scheduling itself is allowed.

Add:

```text
next_3_fixture_difficulty
next_5_fixture_difficulty

next_3_home_count
next_5_home_count
```

Optional:

```text
next_3_opponent_defence_avg
next_5_opponent_defence_avg

next_3_opponent_attack_avg
next_5_opponent_attack_avg
```

Important:

The fixture schedule can look forward.

Opponent/team strength values must represent what was knowable at the prediction cutoff.

Do not use end-of-season opponent strength.

---

# 9. Stability / Risk Features

Add:

```text
minutes_volatility
points_volatility
start_volatility

blank_rate_5
blank_rate_10

return_rate_5
return_rate_10
```

Suggested definitions:

```text
blank = 0 FPL points
return = meaningful attacking/defensive FPL return
```

The exact definition of `return` should match the project's existing point/stat semantics.

---

# 10. Leakage Audit Metadata

Every training row should expose:

```text
feature_cutoff_gw
target_gw
```

Example:

```text
target_gw = 20
feature_cutoff_gw = 19
```

This is not a predictive feature.

It exists to make leakage auditing possible.

If practical, also preserve:

```text
season
player_id
```

---

# 11. Exact Integration Order

Do not create a second independent feature engine.

Extend the existing flow:

```text
LOAD NORMALIZED DATA
        |
        v
EXISTING v1.0 FEATURES
        |
        v
EXISTING v1.0 ROLLING FEATURES
        |
        v
[NEW] PLAYER INVOLVEMENT
        |
        v
[NEW] TEAM / OPPONENT STRENGTH
        |
        v
[NEW] TEAM-SHARE FEATURES
        |
        v
[NEW] WEIGHTED FORM
        |
        v
[NEW] TREND FEATURES
        |
        v
[NEW] FIXTURE-RUN FEATURES
        |
        v
[NEW] STABILITY / RISK
        |
        v
[NEW] LEAKAGE AUDIT METADATA
        |
        v
EXISTING OUTPUT / VALIDATION
```

---

# 12. Recommended Function Boundaries

Do not implement everything inside one large function.

Add small helper functions to the existing module, preserving its current architecture.

Recommended logical boundaries:

```python
build_player_involvement_features(...)
build_team_strength_features(...)
build_team_share_features(...)
build_weighted_form_features(...)
build_trend_features(...)
build_fixture_run_features(...)
build_stability_features(...)
add_leakage_audit_columns(...)
```

Use the project's existing naming/style conventions if the current file already has equivalent helpers.

Do not duplicate functionality that v1.0 already provides.

---

# 13. Feature Calculation Rules

## Rolling features

Use:

```python
shift(1)
```

or equivalent prior-gameweek logic before rolling.

Correct:

```text
GW20 target
  |
  +-- GW19
  +-- GW18
  +-- GW17
```

Incorrect:

```text
GW20 target
  |
  +-- GW20
  +-- GW19
  +-- GW18
```

---

# 14. Missing Data

Do not silently fabricate values.

Use the existing project's missing-value policy.

For insufficient history:

```text
rolling_5 with only 2 previous games
```

must follow the same behavior as v1.0.

Do not introduce arbitrary zeros unless zero is semantically correct.

---

# 15. Double Gameweeks

A player may have multiple fixtures in the same GW.

Do not assume:

```text
one player = one row per GW
```

when processing target fixtures.

Preserve the existing v1.0 double-gameweek handling.

For fixture-run calculations, account for multiple fixtures in the relevant gameweek.

---

# 16. Feature Naming

Use clear, deterministic names.

Preferred pattern:

```text
<metric>_<window>
```

Examples:

```text
points_rolling_3
xg_rolling_5
minutes_rolling_10
weighted_points_5
blank_rate_5
```

Do not rename existing v1.0 columns simply to make naming more consistent.

---

# 17. Validation Required After Implementation

The enhanced feature dataset must pass:

### Schema

- no duplicate player/target rows
- expected target gameweeks
- expected player identifiers
- required new columns exist

### Leakage

Verify:

```text
feature_cutoff_gw < target_gw
```

for every row.

### Numeric integrity

Check:

- no infinite values
- no impossible negative minutes
- no invalid rates
- no impossible shares
- no unexpected NaN explosion

### Historical coverage

Expected historical seasons:

```text
2021-22
2022-23
2023-24
2024-25
2025-26
```

Only after those normalized datasets are complete.

---

# 18. Live 2026-27 Compatibility

The same feature definitions must eventually work on:

```text
2026-27
```

without allowing historical processing to overwrite or normalize the protected live dataset.

The live feature pipeline must use the same semantic definitions as the training pipeline.

---

# 19. What NOT to Add to build_features.py

Do not add:

```text
ML predictions
expected points
captain score
squad optimization
transfer optimization
LLM reasoning
external-news interpretation
final injury intelligence
```

Those belong to later layers.

Architecture:

```text
FEATURE ENGINE
      |
      v
PLAYER PREDICTION MODEL
      |
      v
EXPECTED POINTS
      |
      v
SQUAD OPTIMIZER
      |
      v
AI EXPLANATION
```

---

# 20. Implementation Sequence

When coding starts, do it in this order:

### Step 1
Add leakage audit columns.

### Step 2
Add player involvement/per-90 features.

### Step 3
Add team/opponent strength.

### Step 4
Add team-share features.

### Step 5
Add weighted form.

### Step 6
Add trend features.

### Step 7
Add fixture-run features.

### Step 8
Add stability/risk features.

### Step 9
Run feature inspection.

### Step 10
Run leakage validation.

### Step 11
Compare v1.0 vs v1.1 feature counts.

### Step 12
Only then proceed to model training.

---

# 21. Acceptance Criteria

v1.1 is accepted only if:

```text
[ ] Existing v1.0 features unchanged
[ ] New feature groups implemented
[ ] No target-GW leakage
[ ] No future-result leakage
[ ] Double-GW behavior preserved
[ ] Historical seasons supported
[ ] 2026-27 remains protected
[ ] Feature audit metadata present
[ ] No duplicate player-target rows
[ ] No infinite values
[ ] Validation passes
```

---

# 22. Current Project Position

```text
Historical collection        COMPLETE/PARTIAL
Historical normalization     COMPLETE/PARTIAL
Baseline feature engine      v1.0 COMPLETE
Production feature design    THIS DOCUMENT
Production feature coding    NEXT
Prediction model             NOT STARTED
Squad optimizer              NOT STARTED
AI agent                     NOT STARTED
```

## Next command/action

Before modifying `build_features.py`, inspect its actual function definitions and insert the v1.1 helpers into the existing architecture.

Do not rewrite the baseline engine.
