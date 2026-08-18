from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

def main()->int:
    ap=argparse.ArgumentParser(description="Canonical leakage-safe feature build command backed by build_features_v1_3.py.")
    ap.add_argument("--project-root",default="."); ap.add_argument("--season",default="2025-26"); ap.add_argument("--dry-run",action="store_true"); ap.add_argument("--verbose",action="store_true")
    a=ap.parse_args(); root=Path(a.project_root).resolve(); cmd=[sys.executable,str(root/"scripts/features/build_features_v1_3.py"),"--project-root",str(root),"--season",a.season]
    if a.dry_run: print("DRY-RUN:"," ".join(map(str,cmd))); return 0
    if a.verbose: cmd.append("--verbose")
    return subprocess.run(cmd,cwd=root).returncode

if __name__=="__main__": raise SystemExit(main())
