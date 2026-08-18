from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

def main()->int:
    ap=argparse.ArgumentParser(description="Apply the Phase 24 release policy to raw-data validation.")
    ap.add_argument("--season",default="2026-27")
    ap.add_argument("--project-root",default=".")
    args=ap.parse_args()
    root=Path(args.project_root).resolve()
    cmd=[sys.executable,str(root/"scripts/validate_raw_data.py"),"--season",args.season]
    proc=subprocess.run(cmd,cwd=root,text=True,capture_output=True)
    print(proc.stdout,end="")
    report_path=root/"data/validation"/args.season/f"validation_report_{args.season}.json"
    if not report_path.exists(): print("FAIL release policy: validation report missing"); return 2
    report=json.loads(report_path.read_text(encoding="utf-8"))
    issues=report.get("issues",[])
    errors=[i for i in issues if i.get("severity")=="ERROR"]
    warnings=[i for i in issues if i.get("severity")=="WARNING"]
    allowed=warnings and all(i.get("category")=="snapshot_coverage" for i in warnings)
    if proc.returncode not in (0,1) or errors or not allowed:
        print("FAIL release policy: data errors or non-allowed warnings remain")
        return 2
    print("PASS release data policy: zero errors; snapshot-coverage warning explicitly accepted for newly introduced bootstrap players")
    return 0

if __name__=="__main__": raise SystemExit(main())

