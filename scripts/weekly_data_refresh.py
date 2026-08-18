from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

def main()->int:
    ap=argparse.ArgumentParser(description="Canonical weekly FPL data refresh: collect timestamped snapshots, validate raw data, and apply the release-warning policy.")
    ap.add_argument("--project-root",default="."); ap.add_argument("--season",default="2026-27"); ap.add_argument("--dry-run",action="store_true")
    args=ap.parse_args(); root=Path(args.project_root).resolve()
    commands=[[sys.executable,str(root/"scripts/fetch_bootstrap.py")],[sys.executable,str(root/"scripts/fetch_fixtures.py")],[sys.executable,str(root/"scripts/fetch_player_history.py")],[sys.executable,str(root/"scripts/evaluation/validate_release_data_policy.py"),"--season",args.season,"--project-root",str(root)]]
    if args.dry_run:
        for c in commands: print("DRY-RUN:"," ".join(map(str,c)))
        return 0
    for c in commands:
        result=subprocess.run(c,cwd=root)
        if result.returncode != 0: return result.returncode
    return 0

if __name__=="__main__": raise SystemExit(main())
