import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MANIFEST=ROOT/"data/processed/training_dataset_v1_manifest.json"

def test_unified_dataset_manifest_has_stable_reproducibility_signature():
    manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))
    payload={"version":manifest["version"],"seasons":manifest["seasons_included"],"columns":manifest["columns"],"checksums":manifest["checksums"]}
    expected=hashlib.sha256(json.dumps(payload,sort_keys=True).encode("utf-8")).hexdigest()
    assert manifest.get("reproducibility_signature")==expected
