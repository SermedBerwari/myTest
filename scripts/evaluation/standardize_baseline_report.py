import json
from datetime import datetime, timezone
from pathlib import Path

root=Path(__file__).resolve().parents[2]
raw=json.loads((root/"data/processed/baseline_model_results.json").read_text(encoding="utf-8"))
models=[]
for name,metrics in raw.items():
    models.append({"model":name,"regression_metrics":{"mae":float(metrics["MAE"]),"rmse":float(metrics["RMSE"])},"ranking_metrics":{"status":"requires_prediction_artifact"}})
report={"report_name":"baseline_benchmark_report","version":"1.0.0","generated_at_utc":datetime.now(timezone.utc).isoformat(),"target":"target_points","evaluation_policy":{"chronological_split":"2025-26 test set","baseline_comparison_mandatory":True,"net_of_hit":True},"models":models,"ranking_metric_definition":{"spearman":"Macro-average within-gameweek Spearman correlation.","top_k_hit_rate":"Macro-average overlap of predicted and realized top-k players."}}
(root/"data/processed/baseline_benchmark_report_v1.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
