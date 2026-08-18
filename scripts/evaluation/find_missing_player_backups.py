from __future__ import annotations
import argparse
import json
from pathlib import Path

TARGETS={"585","586","587"}
def main()->int:
    ap=argparse.ArgumentParser(description="Find backups or archive snapshots for missing live-season player IDs.")
    ap.add_argument("--project-root",default=".")
    ap.add_argument("--season",default="2026-27")
    args=ap.parse_args()
    root=Path(args.project_root).resolve(); hits={k:[] for k in TARGETS}; scanned=0
    excluded={".git","__pycache__",".pytest_cache",".venv","venv"}
    for path in root.rglob("*"):
        if not path.is_file() or any(part in excluded for part in path.parts): continue
        scanned+=1; text=""
        name=path.name.lower(); rel=str(path.relative_to(root)).replace("\\","/")
        if any(part in TARGETS for part in path.parts):
            for target in TARGETS:
                if target in path.parts: hits[target].append({"path":rel,"reason":"directory_or_filename_match"})
            continue
        if path.suffix.lower() in {".json",".jsonl",".txt",".csv"} and path.stat().st_size<=20_000_000:
            try: text=path.read_text(encoding="utf-8",errors="ignore")
            except OSError: continue
            for target in TARGETS:
                if (f"\"id\": {target}" in text or f"\"id\":{target}" in text or f"\"player_id\": {target}" in text or f"\"player_id\":{target}" in text): hits[target].append({"path":rel,"reason":"content_match"})
        if path.suffix.lower() in {".zip",".gz",".tar",".7z"} and any(x in name for x in ["backup","archive","raw","2026","2027"]):
            for target in TARGETS: hits[target].append({"path":rel,"reason":"archive_candidate_needs_inspection"})
    result={"season":args.season,"targets":sorted(TARGETS),"files_scanned":scanned,"hits":hits}
    out=root/"data/processed/phase24_missing_player_backup_search.json"; out.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))
    return 0

if __name__=="__main__": raise SystemExit(main())
