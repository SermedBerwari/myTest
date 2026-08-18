from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

ROOT=Path(__file__).resolve().parents[2]
INPUT=ROOT/"data/processed/training_dataset_v1.csv"
OUT=ROOT/"data/processed/phase16_model_variants.json"
PRED=ROOT/"data/processed/phase16_model_variant_predictions.csv"
NON={"season","player_id","gameweek","target_gw","feature_cutoff_gw","web_name","first_name","second_name","position_name","target_points","target_minutes","target_goals","target_assists","target_clean_sheets","target_bonus","target_xg","target_xa"}

def main():
    df=pd.read_csv(INPUT,low_memory=False).sort_values(["season","target_gw","player_id"]).reset_index(drop=True)
    df["historical_average_xp"]=df.groupby("player_id")["target_points"].transform(lambda s: s.shift().expanding().mean()).fillna(0.0).clip(lower=0.0)
    features=[c for c in df.columns if c not in NON and pd.api.types.is_numeric_dtype(df[c])]
    rows=[]
    seasons=sorted(df["season"].dropna().unique())
    for season in seasons:
        prior=df[df["season"]<season]
        test=df[df["season"]==season].copy()
        if prior.empty or test.empty: continue
        model=Ridge(alpha=10.0)
        model.fit(prior[features].fillna(0.0),prior["target_points"].fillna(0.0))
        test["ridge_xp"]=np.clip(model.predict(test[features].fillna(0.0)),0.0,None)
        test["variant_season"]=season
        rows.append(test[["season","target_gw","player_id","target_points","historical_average_xp","ridge_xp"]])
    out=pd.concat(rows,ignore_index=True)
    summary=[]
    for season,g in out.groupby("season"):
        for name in ["historical_average_xp","ridge_xp"]:
            err=g[name]-g.target_points
            summary.append({"season":season,"strategy":name,"rows":int(len(g)),"mae":float(err.abs().mean()),"rmse":float(np.sqrt((err**2).mean())),"spearman":float(g[[name,"target_points"]].corr(method="spearman").iloc[0,1])})
    result={"schema_version":"phase16-model-variants-v1.0.0","source":str(INPUT),"features":features,"seasons":sorted(out.season.unique()),"strategies":["historical_average_xp","ridge_xp"],"summary":summary,"leakage_policy":"Ridge trains only on seasons strictly before each evaluated season; historical average uses shifted player history."}
    OUT.write_text(json.dumps(result,indent=2),encoding="utf-8"); out.to_csv(PRED,index=False); print(json.dumps(result,indent=2))
if __name__=="__main__": main()

