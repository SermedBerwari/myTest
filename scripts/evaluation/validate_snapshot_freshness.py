from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

def ts(path:Path):
    return datetime.strptime(path.stem,"%Y-%m-%d_%H-%M-%S").replace(tzinfo=timezone.utc)
def main()->int:
    ap=argparse.ArgumentParser(description="Validate timestamp freshness and ordering of FPL raw snapshots.")
    ap.add_argument("--project-root",default="."); ap.add_argument("--season",default="2026-27"); ap.add_argument("--max-age-hours",type=float,default=72); ap.add_argument("--as-of-utc",default=None)
    a=ap.parse_args(); root=Path(a.project_root).resolve(); raw=root/"data/raw"/a.season; now=datetime.fromisoformat(a.as_of_utc.replace("Z","+00:00")) if a.as_of_utc else datetime.now(timezone.utc)
    checks=[]; latest=[]
    for kind in ["bootstrap","fixtures"]:
        files=sorted((raw/kind).glob("*.json"),key=ts); checks.append({"check":f"{kind}_present","pass":bool(files),"count":len(files)}); latest.append(files[-1] if files else None)
        if files: checks.append({"check":f"{kind}_ordered","pass":all(ts(x)<ts(y) for x,y in zip(files,files[1:])),"count":len(files)}); age=(now-ts(files[-1])).total_seconds()/3600; checks.append({"check":f"{kind}_fresh","pass":0<=age<=a.max_age_hours,"age_hours":round(age,3),"max_age_hours":a.max_age_hours})
    dirs=[x for x in (raw/"players").iterdir() if x.is_dir()] if (raw/"players").exists() else []; checks.append({"check":"player_directories_present","pass":bool(dirs),"count":len(dirs)}); player_files=[]
    for d in dirs:
        fs=sorted(d.glob("*.json"),key=ts); player_files += fs; checks.append({"check":f"player_{d.name}_present","pass":bool(fs),"count":len(fs)})
    if player_files:
        ages=[(now-ts(x)).total_seconds()/3600 for x in player_files]; checks.append({"check":"player_latest_fresh","pass":min(ages)>=0 and min(ages)<=a.max_age_hours,"latest_age_hours":round(min(ages),3),"max_age_hours":a.max_age_hours})
    result={"season":a.season,"as_of_utc":now.isoformat(),"max_age_hours":a.max_age_hours,"checks":checks,"pass":all(x["pass"] for x in checks)}
    out=root/"data/processed/phase2_freshness_report.json"; out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8"); print(json.dumps(result,indent=2)); return 0 if result["pass"] else 2
if __name__=="__main__": raise SystemExit(main())
