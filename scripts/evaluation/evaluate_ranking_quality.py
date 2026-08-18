import argparse
import json
from pathlib import Path
import pandas as pd

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",required=True)
    ap.add_argument("--prediction-column",required=True)
    ap.add_argument("--target-column",default="target_points")
    ap.add_argument("--group-column",default="target_gw")
    ap.add_argument("--k",type=int,default=10)
    ap.add_argument("--output")
    a=ap.parse_args()
    df=pd.read_csv(a.input)
    rows=[]
    for group,frame in df.groupby(a.group_column):
        frame=frame[[a.prediction_column,a.target_column]].dropna()
        if len(frame)<2: continue
        spearman=frame[a.prediction_column].rank().corr(frame[a.target_column].rank())
        predicted=set(frame.nlargest(min(a.k,len(frame)),a.prediction_column).index)
        realized=set(frame.nlargest(min(a.k,len(frame)),a.target_column).index)
        rows.append({"group":group,"spearman":float(spearman),"top_k_hit_rate":len(predicted&realized)/len(predicted)})
    result={"version":"1.0.0","prediction_column":a.prediction_column,"target_column":a.target_column,"group_column":a.group_column,"k":a.k,"groups_evaluated":len(rows),"macro_spearman":sum(x["spearman"] for x in rows)/len(rows) if rows else None,"macro_top_k_hit_rate":sum(x["top_k_hit_rate"] for x in rows)/len(rows) if rows else None,"groups":rows}
    text=json.dumps(result,indent=2)+"\n"
    Path(a.output).write_text(text,encoding="utf-8") if a.output else print(text)
if __name__=="__main__": main()
