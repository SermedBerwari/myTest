from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""): h.update(chunk)
    return "sha256:"+h.hexdigest()

def main() -> int:
    parser=argparse.ArgumentParser(description="Validate the reproducibility and environment manifest.")
    parser.add_argument("--manifest",default="data/processed/reproducibility_manifest.json")
    parser.add_argument("--project-root",default=".")
    args=parser.parse_args()
    root=Path(args.project_root).resolve()
    manifest=json.loads((root/args.manifest).read_text(encoding="utf-8"))
    errors=[]
    required=("manifest_version","execution_timestamp_utc","runtime","dependencies","dataset","models","source_hashes","randomness")
    errors += [f"missing manifest field: {x}" for x in required if x not in manifest]
    deps=manifest.get("dependencies",{})
    for rel,field in ((deps.get("declared_requirements"),"requirements_sha256"),(deps.get("locked_requirements"),"lockfile_sha256")):
        if not rel or not (root/rel).exists(): errors.append(f"missing dependency file: {rel}")
    for rel,field in ((deps.get("declared_requirements"),"requirements_sha256"),(deps.get("locked_requirements"),"lockfile_sha256")):
        if rel and (root/rel).exists() and deps.get(field)!=sha256(root/rel): errors.append(f"hash mismatch: {rel}")
    model_registry=manifest.get("models",{}).get("registry")
    if not model_registry or not (root/model_registry).exists(): errors.append("missing model registry")
    elif manifest["models"].get("registry_sha256")!=sha256(root/model_registry): errors.append("model registry hash mismatch")
    for rel,expected in manifest.get("source_hashes",{}).items():
        path=root/rel
        if not path.exists(): errors.append(f"missing source: {rel}")
        elif expected!=sha256(path): errors.append(f"source hash mismatch: {rel}")
    for key in ("python","platform","git_commit"):
        if not manifest.get("runtime",{}).get(key): errors.append(f"missing runtime metadata: {key}")
    for key in ("feature_version","data_cutoff_policy","target_season","target_gameweek"):
        if not manifest.get("dataset",{}).get(key): errors.append(f"missing dataset metadata: {key}")
    try:
        result=subprocess.run(["py","-m","pip","check"],cwd=root,text=True,capture_output=True)
        if result.returncode!=0: errors.append("pip check failed: "+result.stdout.strip()+result.stderr.strip())
    except OSError as exc: errors.append(f"could not run pip check: {exc}")
    if errors:
        for error in errors: print("FAIL: "+error)
        return 1
    print("PASS reproducibility manifest, dependency hashes, source hashes, dataset/model metadata, and pip check")
    return 0

if __name__=="__main__": raise SystemExit(main())
