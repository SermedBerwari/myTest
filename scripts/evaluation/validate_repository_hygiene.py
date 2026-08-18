from __future__ import annotations
import argparse
from pathlib import Path

def main() -> int:
    parser=argparse.ArgumentParser(description="Validate repository hygiene and artifact boundaries.")
    parser.add_argument("--project-root",default=".")
    args=parser.parse_args()
    root=Path(args.project_root).resolve()
    errors=[]
    required=[".gitignore","requirements.txt","FPL_Fantasy_MASTER_PLAN.md","data/processed/model_registry.json","data/processed/reproducibility_manifest.json"]
    for rel in required:
        if not (root/rel).exists(): errors.append(f"missing required file: {rel}")
    forbidden=["catboost_info","logs",".venv_phase20_check"]
    for rel in forbidden:
        if (root/rel).exists(): errors.append(f"generated/local directory remains: {rel}")
    for pattern in ["*_diagnostic.json","*_error.txt","*_smoke*.json"]:
        for path in (root/"data/processed").glob(pattern): errors.append(f"disposable diagnostic remains: {path.relative_to(root)}")
    for rel in ["make_prepare_historical_v2_2.py","make_prepare_historical_v2_2_corrected.py"]:
        if (root/rel).exists(): errors.append(f"obsolete generator outside archive: {rel}")
    archive=root/"old documents/phase21_archived_experiments"
    if not archive.exists(): errors.append("archive directory missing")
    gitignore=(root/".gitignore").read_text(encoding="utf-8")
    for token in ["catboost_info/","logs/","data/processed/*_diagnostic.json","make_prepare_historical_v2_2*.py"]:
        if token not in gitignore: errors.append(f"missing ignore rule: {token}")
    if errors:
        for error in errors: print("FAIL: "+error)
        return 1
    print("PASS repository hygiene, archive boundaries, generated-output rules, and required release files")
    return 0

if __name__=="__main__": raise SystemExit(main())
