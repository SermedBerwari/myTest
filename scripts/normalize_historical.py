from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

def main()->int:
    ap=argparse.ArgumentParser(description="Canonical historical normalization command backed by normalize_historical_seasons_v1_3.py.")
    ap.add_argument("--project-root",default="."); ap.add_argument("--seasons",nargs="+",default=["2022-23","2023-24","2024-25","2025-26"]); ap.add_argument("--force",action="store_true"); ap.add_argument("--dry-run",action="store_true"); ap.add_argument("--verbose",action="store_true")
    a=ap.parse_args(); root=Path(a.project_root).resolve(); cmd=[sys.executable,str(root/"scripts/data/normalize_historical_seasons_v1_3.py"),"--project-root",str(root),"--seasons",*a.seasons]
    if a.force: cmd.append("--force")
    if a.dry_run: cmd.append("--dry-run")
    if a.verbose: cmd.append("--verbose")
    if a.dry_run: print("DRY-RUN:"," ".join(map(str,cmd))); return 0
    return subprocess.run(cmd,cwd=root).returncode

if __name__=="__main__": raise SystemExit(main())
