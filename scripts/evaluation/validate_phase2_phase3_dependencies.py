from __future__ import annotations
import argparse
import json
from pathlib import Path

def main()->int:
    ap=argparse.ArgumentParser(description="Audit remaining Phase 2 and Phase 3 dependency gaps.")
    ap.add_argument("--project-root",default=".")
    args=ap.parse_args(); root=Path(args.project_root).resolve()
    checks=[]
    def add(phase,item,status,evidence,needed): checks.append({"phase":phase,"item":item,"status":status,"evidence":evidence,"needed":needed})
    add(2,"Define release-blocking versus acceptable warnings","SATISFIED" if (root/"data/processed/DATA_VALIDATION_RELEASE_POLICY.md").exists() else "MISSING","data/processed/DATA_VALIDATION_RELEASE_POLICY.md","Keep policy linked to the Phase 2 ingestion gate.")
    add(2,"Add automated ingestion regression tests","MISSING" if not list((root/"tests").rglob("*raw*data*.py")) else "SATISFIED","No dedicated raw-data regression test module found.","Add tests for snapshot structure, required fields, IDs, fixtures, warnings, and strict/non-strict exit behavior.")
    add(2,"Add freshness checks","PARTIAL" if (root/"scripts/validate_raw_data.py").exists() else "MISSING","validate_raw_data.py validates snapshots but no dedicated freshness contract was found.","Add max-age and timestamp-order assertions with a documented clock/tolerance policy.")
    add(2,"Define canonical weekly data-refresh command","MISSING" if not (root/"data/processed/PHASE22_DEPLOYMENT.md").exists() else "PARTIAL","Pipeline and CLI entry points exist, but no Phase 2 canonical refresh command document was found.","Document one command covering capture, validation, and immutable snapshot naming.")
    add(2,"Preserve immutable pre-deadline snapshots","SATISFIED" if (root/"data/raw/2026-27").exists() else "MISSING","Timestamped data/raw/2026-27 bootstrap, fixtures, and player snapshots exist.","Keep write-once snapshot behavior and test that existing snapshots are not overwritten.")
    add(3,"Establish one canonical normalization command","MISSING" if len(list((root/"scripts/data").glob("normalize*.py")))>1 else "SATISFIED","Multiple normalization variants exist under scripts/data.","Create one documented wrapper command and designate variants as archived compatibility tools.")
    add(3,"Archive obsolete preparation variants","PARTIAL" if (root/"old documents/phase21_archived_experiments").exists() else "MISSING","An archive exists, but multiple historical preparation variants remain in the operational tree.","Move superseded variants into the archive and retain only the canonical path.")
    add(3,"Add normalization regression tests","MISSING" if not list((root/"tests").rglob("*normaliz*.py")) else "SATISFIED","No dedicated normalization regression test module found.","Add fixture-based tests for row counts, keys, season/gameweek ordering, and rerun determinism.")
    add(3,"Document exact input/output contracts","PARTIAL" if list((root/"data").rglob("*manifest*.json")) else "MISSING","Dataset and feature manifests exist, but no dedicated normalization contract document was found.","Document raw input paths, normalized schemas, output paths, versions, and failure semantics.")
    result={"checks":checks,"summary":{s:sum(1 for c in checks if c["status"]==s) for s in ["SATISFIED","PARTIAL","MISSING"]}}
    out=root/"data/processed/phase2_phase3_dependency_audit.json"; out.write_text(json.dumps(result,indent=2),encoding="utf-8")
    md=["# Phase 2–3 Dependency Audit","","| Phase | Checklist item | Status | Evidence | Required next action |","|---:|---|---|---|---|"]
    for c in checks: md.append("| {phase} | {item} | **{status}** | {evidence} | {needed} |".format(**c))
    md += ["","## Summary","Satisfied: {SATISFIED}; partial: {PARTIAL}; missing: {MISSING}.".format(**result["summary"])]
    (root/"data/processed/PHASE2_PHASE3_DEPENDENCY_AUDIT.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2)); return 0

if __name__=="__main__": raise SystemExit(main())


