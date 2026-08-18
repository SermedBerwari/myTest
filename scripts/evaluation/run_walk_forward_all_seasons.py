from pathlib import Path
import json, subprocess, sys

SEASONS=["2022-23","2023-24","2024-25","2025-26"]
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/"scripts/evaluation/run_backtest.py"
OUT=ROOT/"data/processed/phase9_walk_forward_all_seasons.json"

def main():
    source=SOURCE.read_text(encoding="utf-8")
    reports=[]
    temp=ROOT/"data/processed/_phase9_runner_temp.py"
    try:
        for season in SEASONS:
            text=source.replace('test_season = "2025-26"', f'test_season = "{season}"')
            temp.write_text(text, encoding="utf-8")
            subprocess.run([sys.executable,str(temp)], cwd=ROOT, check=True, timeout=900)
            reports.append(json.loads((ROOT/"data/processed/backtest_results.json").read_text(encoding="utf-8")))
    finally:
        temp.unlink(missing_ok=True)
    maes=[float(r["overall_walk_forward_mae"]) for r in reports]
    result={"report_name":"phase9_walk_forward_all_seasons","version":"1.0.0","protocol":{"train_only_prior_information":True,"within_season_cutoff":"target_gw < test_gw","seasons":SEASONS},"season_reports":reports,"drift":{"mae_min":min(maes),"mae_max":max(maes),"mae_range":max(maes)-min(maes)}}
    OUT.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(OUT)
    for r in reports: print(r["season"],r["overall_walk_forward_mae"],r["overall_walk_forward_rmse"])

if __name__=="__main__":
    main()
