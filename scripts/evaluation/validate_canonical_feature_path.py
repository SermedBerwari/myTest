from __future__ import annotations
import argparse
import json
from pathlib import Path

def main()->int:
    ap=argparse.ArgumentParser(description="Validate the canonical Phase 4 feature-generation path.")
    ap.add_argument("--project-root",default="."); a=ap.parse_args(); root=Path(a.project_root).resolve()
    checks=[
      {"check":"canonical_wrapper","pass":(root/"scripts/build_features.py").exists(),"evidence":"scripts/build_features.py"},
      {"check":"v13_builder","pass":(root/"scripts/features/build_features_v1_3.py").exists(),"evidence":"scripts/features/build_features_v1_3.py"},
      {"check":"legacy_archived","pass":all((root/"old documents/phase4_archived_feature_builders"/n).exists() for n in ["build_features.py","build_features_v1_1.py","build_features_v1_2.py"]),"evidence":"old documents/phase4_archived_feature_builders"},
      {"check":"canonical_policy","pass":(root/"data/processed/PHASE4_CANONICAL_FEATURE_PATH.md").exists(),"evidence":"data/processed/PHASE4_CANONICAL_FEATURE_PATH.md"},
      {"check":"registry_version","pass":False,"evidence":"model_registry.json feature versions"}]
    registry=json.loads((root/"data/processed/model_registry.json").read_text(encoding="utf-8")); versions=[]
    for model in registry.get("models",registry.get("entries",[])) if isinstance(registry,dict) else []:
        if isinstance(model,dict) and model.get("feature_version"): versions.append(model["feature_version"])
    checks[-1]["pass"]=bool(versions) and all(v=="builder-1.3.0" for v in versions); checks[-1]["evidence"]=versions
    result={"canonical":"scripts/features/build_features_v1_3.py","checks":checks,"pass":all(c["pass"] for c in checks)}
    (root/"data/processed/canonical_feature_path_report.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8"); print(json.dumps(result,indent=2)); return 0 if result["pass"] else 2
if __name__=="__main__": raise SystemExit(main())
