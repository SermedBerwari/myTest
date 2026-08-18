import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def test_standardized_baseline_report_is_complete():
    path=ROOT/"data/processed/baseline_benchmark_report_v1.json"
    report=json.loads(path.read_text(encoding="utf-8"))
    assert report["version"]=="1.0.0"
    assert report["evaluation_policy"]["baseline_comparison_mandatory"] is True
    assert report["evaluation_policy"]["net_of_hit"] is True
    assert len(report["models"])>=5
    assert "spearman" in report["ranking_metric_definition"]
    assert "top_k_hit_rate" in report["ranking_metric_definition"]

def test_ranking_quality_evaluator_outputs_grouped_metrics(tmp_path):
    source=tmp_path/"predictions.csv"
    source.write_text(chr(10).join(["target_gw,pred,target_points","1,10,8","1,8,10","1,2,1","2,1,2","2,4,3","2,3,4"])+chr(10),encoding="utf-8")
    output=tmp_path/"ranking.json"
    subprocess.run([sys.executable,str(ROOT/"scripts/evaluation/evaluate_ranking_quality.py"),"--input",str(source),"--prediction-column","pred","--output",str(output)],check=True,cwd=ROOT)
    result=json.loads(output.read_text(encoding="utf-8"))
    assert result["groups_evaluated"]==2
    assert result["macro_spearman"] is not None
    assert result["macro_top_k_hit_rate"] is not None

