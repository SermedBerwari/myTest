import json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
meta=json.loads((ROOT/"data/processed/phase16_model_variants.json").read_text(encoding="utf-8"))
pred=pd.read_csv(ROOT/"data/processed/phase16_model_variant_predictions.csv")
assert meta["strategies"]==["historical_average_xp","ridge_xp"]
assert len(meta["seasons"])==3
assert not pred[["historical_average_xp","ridge_xp"]].isna().any().any()
assert (pred[["historical_average_xp","ridge_xp"]]>=0).all().all()
assert all(r["spearman"]==r["spearman"] for r in meta["summary"])
assert "strictly before" in meta["leakage_policy"]
print("PASS historical-average and Ridge walk-forward variant validation")
