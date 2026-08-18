from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

REQUIRED_ENTRY_FIELDS={"model_name","model_type","feature_version","dataset_version","training_seasons","artifact_path","artifact_hash","created_at_utc","status","walk_forward_metrics"}
VALID_STATUSES={"candidate","active","retired"}

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""): h.update(chunk)
    return "sha256:"+h.hexdigest()

def validate(registry_path: Path, root: Path) -> list[str]:
    errors=[]
    try: data=json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception as exc: return [f"invalid registry JSON: {exc}"]
    for key in ("registry_version","production_model","production_feature_version","production_dataset_version","xP_formula_version","models","artifact_policy"):
        if key not in data: errors.append(f"missing registry field: {key}")
    models=data.get("models",[])
    if not isinstance(models,list) or not models: errors.append("models must be a non-empty list")
    names=[]; active=[]
    for entry in models:
        missing=REQUIRED_ENTRY_FIELDS-set(entry)
        if missing: errors.append(f"{entry.get("model_name","<unnamed>")} missing fields: {sorted(missing)}")
        name=entry.get("model_name")
        if name in names: errors.append(f"duplicate model name: {name}")
        names.append(name)
        if entry.get("status") not in VALID_STATUSES: errors.append(f"invalid status for {name}")
        artifact=root/entry.get("artifact_path","")
        if not artifact.exists(): errors.append(f"missing artifact for {name}: {artifact}")
        elif entry.get("artifact_hash") != sha256(artifact): errors.append(f"hash mismatch for {name}")
        if entry.get("status")=="active": active.append(name)
    if data.get("production_model") not in names: errors.append("production_model is not registered")
    if data.get("production_model") not in active: errors.append("production_model must have active status")
    if len(active)==0: errors.append("registry has no active model")
    return errors

def main() -> int:
    parser=argparse.ArgumentParser(description="Validate the model and artifact registry.")
    parser.add_argument("--registry",default="data/processed/model_registry.json")
    parser.add_argument("--project-root",default=".")
    args=parser.parse_args()
    errors=validate(Path(args.registry),Path(args.project_root).resolve())
    if errors:
        for error in errors: print(f"FAIL: {error}")
        return 1
    print("PASS model registry schema, artifact existence, active selection, and SHA-256 integrity")
    return 0

if __name__=="__main__": raise SystemExit(main())
