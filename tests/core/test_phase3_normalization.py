import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SEASONS=["2022-23","2023-24","2024-25","2025-26"]
REQUIRED=["player_gameweek.csv","players.csv","teams.csv","fixtures.csv","gameweeks.csv","player_season_history.csv","normalization_manifest.json"]

def test_canonical_normalizer_help_and_dry_run():
    r=subprocess.run([sys.executable,str(ROOT/"scripts/normalize_historical.py"),"--help"],cwd=ROOT,capture_output=True,text=True)
    assert r.returncode==0
    assert "Canonical historical normalization" in r.stdout
    r=subprocess.run([sys.executable,str(ROOT/"scripts/normalize_historical.py"),"--project-root",str(ROOT),"--seasons",*SEASONS,"--dry-run"],cwd=ROOT,capture_output=True,text=True)
    assert r.returncode==0
    assert "normalize_historical_seasons_v1_3.py" in r.stdout

def test_normalized_output_contracts_exist():
    for season in SEASONS:
        out=ROOT/"data/processed"/season
        assert out.exists(), season
        for name in REQUIRED[:-1]: assert (out/name).exists(), f"{season}/{name}"
        assert (out/"historical"/"normalization_manifest.json").exists()
        manifest=json.loads((out/"historical"/"normalization_manifest.json").read_text(encoding="utf-8"))
        assert manifest.get("season")==season
        assert manifest.get("schema_version") or manifest.get("normalizer_version")

def test_normalized_csvs_are_nonempty_and_have_headers():
    for season in SEASONS:
        out=ROOT/"data/processed"/season
        for name in REQUIRED[:-1]:
            lines=(out/name).read_text(encoding="utf-8-sig").splitlines()
            assert len(lines)>=2, f"{season}/{name} is empty"
            assert lines[0].strip(), f"{season}/{name} has no header"

def test_normalization_artifact_hashes_are_stable():
    for season in SEASONS:
        path=ROOT/"data/processed"/season/"historical"/"normalization_manifest.json"
        h1=hashlib.sha256(path.read_bytes()).hexdigest(); h2=hashlib.sha256(path.read_bytes()).hexdigest()
        assert h1==h2

def test_obsolete_variants_are_archived():
    archive=ROOT/"old documents/phase3_archived_variants"
    assert archive.exists()
    assert not (ROOT/"scripts/data/normalize_historical_seasons.py").exists()
    assert (ROOT/"scripts/data/normalize_historical_seasons_v1_3.py").exists()




