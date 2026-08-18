from __future__ import annotations
import argparse
import json
from datetime import datetime
from pathlib import Path

def main()->int:
    ap=argparse.ArgumentParser(description="Materialize missing per-player snapshots from a bootstrap snapshot without overwriting history.")
    ap.add_argument("--project-root",default=".")
    ap.add_argument("--season",default="2026-27")
    ap.add_argument("--bootstrap",default="data/raw/2026-27/bootstrap/2026-08-18_08-57-18.json")
    ap.add_argument("--snapshot-name",default="2026-08-18_08-57-18.json")
    ap.add_argument("--dry-run",action="store_true")
    args=ap.parse_args()
    root=Path(args.project_root).resolve(); source=root/args.bootstrap; out_root=root/"data/raw"/args.season/"players"
    data=json.loads(source.read_text(encoding="utf-8")); elements=data.get("elements",[])
    if not isinstance(elements,list) or not elements: raise SystemExit("Bootstrap contains no elements")
    created=[]; skipped=[]
    for player in elements:
        pid=player.get("id")
        if not isinstance(pid,int): continue
        directory=out_root/str(pid); target=directory/args.snapshot_name
        if directory.exists(): skipped.append(pid); continue
        created.append(pid)
        if not args.dry_run:
            directory.mkdir(parents=True,exist_ok=True)
            payload={"fixtures":[],"history":[],"history_past":[]}
            target.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    report={"season":args.season,"source":str(source.relative_to(root)),"snapshot_name":args.snapshot_name,"bootstrap_players":len(elements),"created_player_ids":created,"skipped_existing_ids":skipped,"dry_run":args.dry_run,"created_at_utc":datetime.utcnow().isoformat()+"Z"}
    out=root/"data/processed/phase25_reconciliation_report.json"; out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))
    return 0

if __name__=="__main__": raise SystemExit(main())

