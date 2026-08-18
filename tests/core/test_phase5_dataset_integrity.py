import json
from pathlib import Path
import pandas as pd
import pytest

ROOT=Path(__file__).resolve().parents[2]
DATASET=ROOT/"data/processed/training_dataset_v1.csv"
MANIFEST=ROOT/"data/processed/training_dataset_v1_manifest.json"
SEASONS=["2022-23","2023-24","2024-25","2025-26"]
REQUIRED={"player_id","season","gameweek","target_gw","feature_cutoff_gw"}
TARGETS={"target_minutes","target_points","target_goals","target_assists","target_clean_sheets","target_bonus","target_xg","target_xa"}

@pytest.fixture(scope="module")
def manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))

@pytest.fixture(scope="module")
def columns():
    return list(pd.read_csv(DATASET,nrows=0).columns)

def test_unified_dataset_exists_and_has_required_columns(columns, manifest):
    assert DATASET.exists()
    assert MANIFEST.exists()
    assert REQUIRED.issubset(columns)
    assert TARGETS.issubset(columns)
    assert columns==manifest["columns"]

def test_composite_training_keys_are_unique():
    df=pd.read_csv(DATASET,usecols=["season","player_id","fixture_id"])
    assert not df.duplicated(["season","player_id","fixture_id"]).any()

def test_manifest_row_counts_match_dataset(manifest):
    df=pd.read_csv(DATASET,usecols=["season"])
    assert len(df)==manifest["total_rows"]
    assert df["season"].value_counts().to_dict()==manifest["row_breakdown_by_season"]

def test_feature_cutoffs_are_before_targets():
    df=pd.read_csv(DATASET,usecols=["feature_cutoff_gw","fixture_id"])
    assert (df["feature_cutoff_gw"]<df["fixture_id"]).all()

def test_seasonal_feature_schemas_are_consistent():
    schemas=[]
    for season in SEASONS:
        path=ROOT/"data/features"/season/"player_gameweek_features.csv"
        assert path.exists(), season
        schemas.append(list(pd.read_csv(path,nrows=0).columns))
    assert all(schema==schemas[0] for schema in schemas[1:])
    assert schemas[0]==list(pd.read_csv(DATASET,nrows=0).columns)

def test_manifest_version_and_key_contract_are_present(manifest):
    assert manifest["dataset_name"]=="training_dataset_v1"
    assert manifest["version"]=="1.0.0"
    assert manifest["key_columns"]==["season","player_id","fixture_id"]
    assert manifest["target_column"]=="target_points"



