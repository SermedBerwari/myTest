"""
expected_points.py
===================
FIX 3 (see FPL_PROJECT_COMPLETION_AND_FIX_PLAN.md): connects

    points model (CatBoost)  +  minutes regressor  +  starting classifier

into a single, defined, documented decision-ready expected-points figure
that the optimizer and manager engine actually consume.

Why this is needed
-------------------
The raw CatBoost model was trained to predict `target_points` -- the total
FPL points a player actually scored in a gameweek, including gameweeks
where the player barely played (or didn't play at all). Its prediction for
a given player therefore already reflects "typical" recent minutes for
that player *as encoded in the input features* (e.g. `last_5_points_per_game`,
`minutes_per_appearance_last_5`). This creates two problems for decision
making:

  1. It reacts slowly to THIS week's specific minutes signal (a starting
     XI change, a fresh injury, a new signing with no FPL history, a
     player rested for a cup game). The minutes regressor and starting
     classifier exist specifically to capture that up-to-date signal.
  2. Two players with the same predicted total points are not
     interchangeable if one is a nailed-on 90-minute starter and the
     other is a rotation risk who might play 20 minutes off the bench --
     the latter is a much riskier pick for captaincy and starting XI
     selection.

Method
------
1. `raw_points`               = CatBoost prediction (points, as trained).
2. `recent_minutes_fraction`  = minutes_per_appearance_last_5 / 90,
                                 clipped to [MIN_FRACTION_FLOOR, 1.0] so we
                                 never divide by (near) zero for a player
                                 who barely played recently.
3. `implied_points_per_90`    = raw_points / recent_minutes_fraction
                                 -- i.e. "how many points would this
                                 player be worth if they played a full 90,
                                 given the model's fixture-aware
                                 prediction and their recent scoring rate".
4. `expected_minutes`         = minutes regressor prediction, clipped to
                                 [0, 90].
5. `start_probability`        = starting classifier's predicted probability
                                 of the >=60-minute "started" class.
   Sanity guard: if the minutes regressor predicts significant minutes
   (>45) while the classifier says starting is unlikely (<0.3), we don't
   trust the higher figure -- these two models disagreeing usually means
   the player is a fringe / bench option, so we cap expected_minutes at a
   conservative substitute-appearance figure instead.
6. `decision_ready_points`    = implied_points_per_90 * (expected_minutes / 90)

This is intentionally simple and auditable rather than another model: the
plan is explicit that the project needs integration and validation, not
more model complexity.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from catboost import CatBoostClassifier, CatBoostRegressor

MIN_FRACTION_FLOOR = 0.15  # never treat a player as playing < ~13 mins/90 when inverting
FRINGE_MINUTES_CAP = 25.0  # conservative substitute-appearance minutes when models disagree
DISAGREEMENT_MINUTES_THRESHOLD = 45.0
DISAGREEMENT_START_PROB_THRESHOLD = 0.30

NON_FEATURE_COLS = [
    "season", "player_id", "fixture_id", "gameweek", "target_gw", "feature_cutoff_gw",
    "web_name", "first_name", "second_name", "position_name",
    "target_points", "target_minutes", "target_goals", "target_assists",
    "target_clean_sheets", "target_bonus", "target_xg", "target_xa",
]


def _feature_columns(df: pd.DataFrame) -> list[str]:
    """
    Must exactly mirror the feature-selection logic used to train
    catboost_model.cbm, minutes_regressor.cbm, and starter_classifier.cbm
    (see scripts/models/train_advanced_models.py and train_minutes_model.py).
    """
    return [
        c for c in df.columns
        if c not in NON_FEATURE_COLS and pd.api.types.is_numeric_dtype(df[c])
    ]


def compute_decision_ready_points(pool: pd.DataFrame, project_root: Path) -> pd.DataFrame:
    """
    Given a player pool DataFrame (one row per player, with the same feature
    columns used in training plus 'minutes_per_appearance_last_5'), attach:

        raw_points, expected_minutes, start_probability, decision_ready_points

    and return the pool with 'expected_points' set to decision_ready_points
    (the column name the optimizer / manager engine consume).
    """
    models_dir = project_root / "data" / "models"
    catboost_path = models_dir / "catboost_model.cbm"
    minutes_path = models_dir / "minutes_regressor.cbm"
    starter_path = models_dir / "starter_classifier.cbm"

    pool = pool.copy()
    feat_cols = _feature_columns(pool)
    X = pool[feat_cols].fillna(0)

    # 1. Raw points prediction
    if catboost_path.exists():
        points_model = CatBoostRegressor()
        points_model.load_model(str(catboost_path))
        pool["raw_points"] = points_model.predict(X)
    else:
        pool["raw_points"] = pool.get("last_5_points_per_game", pd.Series([0.0] * len(pool))).fillna(0.0)

    # 2/4. Expected minutes this week
    if minutes_path.exists():
        minutes_model = CatBoostRegressor()
        minutes_model.load_model(str(minutes_path))
        pool["expected_minutes"] = minutes_model.predict(X).clip(0, 90)
    else:
        # Fallback: assume recent per-appearance minutes continue.
        pool["expected_minutes"] = pool.get(
            "minutes_per_appearance_last_5", pd.Series([60.0] * len(pool))
        ).fillna(60.0).clip(0, 90)

    # 5. Starting probability
    if starter_path.exists():
        starter_model = CatBoostClassifier()
        starter_model.load_model(str(starter_path))
        pool["start_probability"] = starter_model.predict_proba(X)[:, 1].clip(0.0, 1.0)
    else:
        pool["start_probability"] = pool.get("start_probability", (pool["expected_minutes"] >= 60).astype(float))

    # Sanity guard: minutes regressor vs starting classifier disagreement.
    disagreement = (
        (pool["expected_minutes"] > DISAGREEMENT_MINUTES_THRESHOLD)
        & (pool["start_probability"] < DISAGREEMENT_START_PROB_THRESHOLD)
    )
    pool.loc[disagreement, "expected_minutes"] = FRINGE_MINUTES_CAP

    # 3. Implied points-per-90 from the model's fixture-aware raw prediction
    recent_minutes_fraction = (
        pool.get("minutes_per_appearance_last_5", pd.Series([45.0] * len(pool)))
        .fillna(45.0)
        / 90.0
    ).clip(lower=MIN_FRACTION_FLOOR, upper=1.0)

    pool["implied_points_per_90"] = pool["raw_points"] / recent_minutes_fraction

    # 6. Decision-ready expected points
    pool["decision_ready_points"] = (
        pool["implied_points_per_90"] * (pool["expected_minutes"] / 90.0)
    )

    # This is what optimizer.py / manager_engine.py actually consume.
    pool["expected_points"] = pool["decision_ready_points"]

    return pool

