"""
weekly_pipeline.py
==================
End-to-end Weekly Orchestration Pipeline (Phase 14).

Executes sequentially:
  1. Live FPL API fetch (bootstrap & fixtures) via external intelligence signals
  2. Feature vector construction / decision-ready player scoring (points
     model + expected minutes + starting probability -- see FIX 3 and
     scripts/decision/expected_points.py)
  3. External intelligence signals integration
  4. Squad & Transfer optimization (ILP + Manager Engine) against a REAL squad
  5. AI Decision Agent report generation

FIX 2 (see FPL_PROJECT_COMPLETION_AND_FIX_PLAN.md):
  This pipeline no longer fabricates a demo/sample 15-player squad from the
  player pool. It requires the caller's actual current squad, supplied via
  config/my_squad.json (or an explicit --squad path / squad_player_ids arg).
  If no real squad is available, the pipeline fails loudly instead of
  silently substituting synthetic data, so transfer recommendations are
  never computed against a fake squad.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s][%(levelname)s] %(message)s")
LOG = logging.getLogger("weekly_pipeline")

# Append scripts directory to sys.path to enable imports
scripts_dir = Path(__file__).resolve().parent
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))


class SquadConfigError(RuntimeError):
    """Raised when no valid real current squad can be loaded."""


def _default_squad_config_path(project_root: Path) -> Path:
    return project_root / "config" / "my_squad.json"


def load_real_squad(project_root: Path, squad_path: Path | None, season: str) -> dict:
    """
    Load the user's REAL current 15-player squad from a JSON config file.

    Expected schema:
        {
          "season": "2026-27",
          "player_ids": [<15 unique int player_id values>],
          "free_transfers": 1,
          "bank": 0.0
        }

    Raises SquadConfigError with an actionable message if the file is
    missing, malformed, or still contains placeholder values. This
    pipeline intentionally does NOT fall back to a fabricated squad.
    """
    path = squad_path or _default_squad_config_path(project_root)

    if not path.exists():
        example = project_root / "config" / "my_squad.example.json"
        raise SquadConfigError(
            f"No real squad config found at {path}.\n"
            f"Copy {example} to {path} and fill in your actual 15 current "
            f"FPL player_id values (see data/processed/{season}/players.csv "
            f"for the player_id <-> web_name mapping). Refusing to proceed "
            f"with a fabricated squad, since that would invalidate transfer "
            f"recommendations."
        )

    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    player_ids = cfg.get("player_ids")
    if not isinstance(player_ids, list) or len(player_ids) != 15:
        raise SquadConfigError(
            f"{path} must contain a 'player_ids' list with exactly 15 entries."
        )

    player_ids = [int(p) for p in player_ids]

    if any(p <= 0 for p in player_ids):
        raise SquadConfigError(
            f"{path} still contains placeholder player_id values (<= 0). "
            f"Fill in your real current squad's player IDs before running "
            f"the weekly pipeline."
        )

    if len(set(player_ids)) != 15:
        raise SquadConfigError(f"{path} contains duplicate player_id values.")

    cfg["player_ids"] = player_ids
    cfg.setdefault("free_transfers", 1)
    cfg.setdefault("bank", 0.0)
    return cfg


def _score_player_pool(project_root: Path, season: str, target_gw: int) -> pd.DataFrame:
    """
    Load features for the target GW and produce a DECISION-READY expected
    points figure per player (FIX 3): points model output, rescaled by the
    minutes regressor + starting classifier, rather than the raw points
    model prediction alone. See scripts/decision/expected_points.py for the
    full method and rationale.
    """
    feature_csv = project_root / "data" / "features" / season / "player_gameweek_features.csv"

    if feature_csv.exists():
        pool = pd.read_csv(feature_csv, low_memory=False)
        if "target_gw" in pool.columns:
            pool = pool[pool["target_gw"] == target_gw].copy()
    else:
        # Fallback to the master training dataset if per-season features
        # haven't been generated yet.
        fallback_csv = project_root / "data" / "processed" / "training_dataset_v1.csv"
        if not fallback_csv.exists():
            raise FileNotFoundError(
                f"Neither {feature_csv} nor {fallback_csv} exist. "
                f"Run the feature-building scripts first."
            )
        df = pd.read_csv(fallback_csv, low_memory=False)
        pool = df.loc[(df["season"] == season) & (df["target_gw"] == target_gw)].copy()

    if pool.empty:
        raise ValueError(f"No feature rows found for season={season}, target_gw={target_gw}.")

    from decision.expected_points import compute_decision_ready_points
    from decision.official_xp import rank_players
    pool = compute_decision_ready_points(pool, project_root)
    pool = rank_players(pool)

    return pool


def _attach_real_metadata(project_root: Path, season: str, pool: pd.DataFrame) -> pd.DataFrame:
    """Attach real team_id, position_id, cost and web_name from players.csv. No synthetic fallback."""
    players_meta_path = project_root / "data" / "processed" / season / "players.csv"
    if not players_meta_path.exists():
        raise FileNotFoundError(
            f"Player metadata not found at {players_meta_path}; cannot attach "
            f"real team_id/position_id/cost. Refusing to use synthetic metadata."
        )

    players_meta = pd.read_csv(players_meta_path)
    meta_cols = [c for c in ["player_id", "web_name", "position_id", "team_id", "now_cost"] if c in players_meta.columns]
    required_meta = {"player_id", "position_id", "team_id"}
    missing_required_meta = required_meta - set(meta_cols)
    if missing_required_meta:
        raise ValueError(f"Historical player metadata is missing required columns: {sorted(missing_required_meta)}")
    if "now_cost" not in meta_cols:
        players_meta = players_meta.copy()
        players_meta["now_cost"] = pd.NA
        meta_cols.append("now_cost")
    pool = pool.merge(
        players_meta[meta_cols],
        on="player_id",
        how="left",
        suffixes=("", "_meta"),
    )

    if "web_name_meta" in pool.columns:
        pool["web_name"] = pool["web_name_meta"].fillna("Player_" + pool["player_id"].astype(str))
    if "position_id_meta" in pool.columns:
        pool["position_id"] = pool["position_id_meta"]
    if "team_id_meta" in pool.columns:
        pool["team_id"] = pool["team_id_meta"]
    if "now_cost_meta" in pool.columns:
        pool["cost"] = pool["now_cost_meta"] / 10.0
    elif "now_cost" in pool.columns:
        pool["cost"] = pool["now_cost"] / 10.0

    missing_meta = pool[pool["team_id"].isna() | pool["position_id"].isna() | pool["cost"].isna()]
    if not missing_meta.empty:
        bad_ids = missing_meta["player_id"].tolist()
        raise ValueError(
            f"Could not resolve real metadata (team_id/position_id/cost) for "
            f"player_id(s): {bad_ids}. These players cannot be safely optimized."
        )

    pool["position_id"] = pool["position_id"].astype(int)
    pool["team_id"] = pool["team_id"].astype(int)
    pool = pool.drop_duplicates("player_id").reset_index(drop=True)
    return pool


def run_weekly_pipeline(
    season: str = "2026-27",
    target_gw: int = 1,
    squad_path: Path | None = None,
) -> dict:
    project_root = Path(__file__).resolve().parents[1]
    LOG.info("=" * 72)
    LOG.info(f"STARTING FPL AI WEEKLY AUTOMATION PIPELINE FOR {season} GW{target_gw}")
    LOG.info("=" * 72)

    # Step 0: Load the REAL current squad up-front. Fail loudly if absent
    # rather than fabricating one later in the pipeline.
    LOG.info("Step 0/5: Loading real current squad from config...")
    squad_cfg = load_real_squad(project_root, squad_path, season)
    LOG.info(f"Loaded real squad with {len(squad_cfg['player_ids'])} players.")

    # Step 1: Live intelligence fetch
    LOG.info("Step 1/6: Running External Intelligence Pipeline...")
    from intelligence.external_intelligence import fetch_availability_signals, apply_availability_adjustment
    df_signals = fetch_availability_signals(project_root)
    LOG.info(f"Loaded {len(df_signals)} player availability signals.")

    # Step 2: Load feature dataset for target season & compute decision-ready
    # expected points (CatBoost points model + minutes regressor + starting
    # classifier -- see scripts/decision/expected_points.py).
    LOG.info(f"Step 2/6: Scoring player pool for {season} GW{target_gw} (points model + expected minutes)...")
    pool = _score_player_pool(project_root, season, target_gw)
    pool = _attach_real_metadata(project_root, season, pool)

    # Step 3: Apply external intelligence BEFORE optimization (FIX 4) so
    # availability actually changes who gets picked/captained/transferred,
    # not just a post-hoc warning.
    LOG.info("Step 3/6: Applying availability/news signals to decision-ready expected points...")
    pool = apply_availability_adjustment(pool, df_signals)
    flagged = pool[pool["availability_multiplier"] < 1.0]
    if not flagged.empty:
        LOG.info(f"  {len(flagged)} player(s) had expected points discounted for availability risk.")

    # Step 4: Squad Optimization
    LOG.info("Step 4/6: Running ILP Squad Optimizer...")
    from optimizer.squad_optimizer import optimize_squad
    opt_squad = optimize_squad(pool, budget=100.0)
    LOG.info(f"Optimal Squad expected points: {opt_squad['expected_points']:.2f}")

    # Step 5: Manager Engine — evaluated against the REAL current squad.
    LOG.info("Step 5/6: Running Personalized Manager Engine against real squad...")
    from optimizer.manager_engine import recommend_transfers

    real_squad_ids = squad_cfg["player_ids"]
    missing_from_pool = sorted(set(real_squad_ids) - set(pool["player_id"].astype(int)))
    if missing_from_pool:
        raise SquadConfigError(
            f"Your real squad (config/my_squad.json) references player_id(s) "
            f"not present in this week's player pool: {missing_from_pool}. "
            f"They may be unavailable, transferred out of the league, or the "
            f"player_id values may be wrong."
        )

    mgr_rec = recommend_transfers(
        real_squad_ids,
        pool,
        free_transfers=int(squad_cfg["free_transfers"]),
        bank=float(squad_cfg["bank"]),
    )

    # Step 6: AI Decision Agent Report
    LOG.info("Step 6/6: Generating AI Decision Agent Report...")
    from agent.ai_decision_agent import generate_weekly_report
    report = generate_weekly_report(opt_squad, mgr_rec, df_signals.to_dict(orient="records"))

    summary = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "target_season": season,
        "target_gameweek": int(target_gw),
        "real_squad_player_ids": real_squad_ids,
        "optimal_squad": opt_squad,
        "manager_recommendations": mgr_rec,
        "ai_report": report,
    }

    out_file = project_root / "data" / "processed" / "weekly_automation_summary.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    LOG.info("=" * 72)
    LOG.info(f"WEEKLY AUTOMATION PIPELINE EXECUTED SUCCESSFULLY. Output: {out_file}")
    LOG.info("=" * 72)
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the FPL weekly automation pipeline.")
    parser.add_argument("--season", default="2026-27", help="Season, e.g. 2026-27")
    parser.add_argument("--gw", type=int, default=1, help="Target gameweek")
    parser.add_argument(
        "--squad",
        type=str,
        default=None,
        help="Path to a squad JSON config (defaults to config/my_squad.json)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    squad_arg = Path(args.squad) if args.squad else None
    run_weekly_pipeline(season=args.season, target_gw=args.gw, squad_path=squad_arg)


