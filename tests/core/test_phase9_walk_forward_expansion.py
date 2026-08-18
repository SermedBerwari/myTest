import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
REPORT=ROOT/"data/processed/phase9_walk_forward_all_seasons.json"

def test_all_season_report_has_expansion_protocol():
    report=json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["protocol"]["train_only_prior_information"] is True
    assert report["protocol"]["within_season_cutoff"]=="target_gw < test_gw"
    assert report["protocol"]["seasons"]==["2022-23","2023-24","2024-25","2025-26"]

def test_each_season_contains_requested_metrics():
    report=json.loads(REPORT.read_text(encoding="utf-8"))
    required={"mean_precision_at_5","mean_precision_at_10","mean_precision_at_20","mean_captain_hit","mean_captain_points_ratio","mean_predicted_squad_points","mean_oracle_squad_points","mean_squad_regret","mean_transfer_target_lift"}
    assert len(report["season_reports"])==4
    for season in report["season_reports"]:
        metrics=season["ranking_metrics"]
        assert required.issubset(metrics)
        assert 0.0 <= metrics["mean_precision_at_5"] <= 1.0
        assert 0.0 <= metrics["mean_precision_at_10"] <= 1.0
        assert 0.0 <= metrics["mean_precision_at_20"] <= 1.0
        assert 0.0 <= metrics["mean_captain_hit"] <= 1.0
        assert metrics["mean_oracle_squad_points"] >= metrics["mean_predicted_squad_points"]
        assert metrics["mean_squad_regret"] >= 0.0

def test_gameweek_rows_have_finite_outcome_metrics():
    report=json.loads(REPORT.read_text(encoding="utf-8"))
    for season in report["season_reports"]:
        assert len(season["gameweek_breakdown"])>0
        for row in season["gameweek_breakdown"]:
            for key in ("precision_at_5","precision_at_10","precision_at_20","captain_hit","captain_points_ratio","predicted_squad_points","oracle_squad_points","squad_regret","transfer_target_lift"):
                assert row[key] is not None
                assert row[key] == row[key]
