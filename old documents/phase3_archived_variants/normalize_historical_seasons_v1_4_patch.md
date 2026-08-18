# normalize_historical_seasons.py → v1.4 patch

The uploaded source is `normalize_historical_seasons.py` v1.3.0.  
The bug is in `normalize_modern()`: historical `team_h` / `team_a` may be club names, but v1.3 immediately converts them with `pd.to_numeric()`, turning names into `NaN`.

This patch keeps v1.3 architecture and adds a conservative team-name → team_id resolution using the same season's `player_gameweek.csv`.

## 1. Version

Change:

```python
VERSION = "1.3.0"
```

to:

```python
VERSION = "1.4.0"
```

## 2. Add these helpers before `normalize_modern()`

```python
def build_team_id_resolver(pdf: pd.DataFrame) -> dict[str, int]:
    """
    Build team-name -> team_id mappings from the same historical
    player source. No hard-coded club mapping is used.
    """
    pm = mapping(pdf.columns, PLAYER_ALIASES)

    team_id_col = pm.get("team_id")
    team_name_col = pm.get("team")

    if not team_id_col:
        raise RuntimeError(
            "Historical player source has no team_id column; "
            "cannot safely resolve fixture team names."
        )

    resolver: dict[str, int] = {}

    if team_name_col:
        ids = pd.to_numeric(pdf[team_id_col], errors="coerce")
        pairs = pd.DataFrame(
            {
                "team_id": ids,
                "team_name": pdf[team_name_col],
            }
        ).dropna(subset=["team_id", "team_name"])

        for team_id, group in pairs.groupby("team_id", sort=True):
            for raw_name in group["team_name"].astype(str):
                name = norm(raw_name)
                if not name:
                    continue

                resolved = int(team_id)
                existing = resolver.get(name)

                if existing is not None and existing != resolved:
                    raise RuntimeError(
                        f"Conflicting historical team mapping for "
                        f"'{raw_name}': {existing} vs {resolved}"
                    )

                resolver[name] = resolved

    if not resolver:
        raise RuntimeError(
            "Could not construct a historical team-name -> team_id mapping."
        )

    return resolver


def resolve_fixture_team_ids(
    fixtures: pd.DataFrame,
    pdf: pd.DataFrame,
    season: str,
) -> pd.DataFrame:
    """
    Normalize fixture team_h/team_a to canonical numeric team IDs.

    Supports both numeric IDs and historical team names.
    """
    resolver = build_team_id_resolver(pdf)

    for col in ("team_h", "team_a"):
        if col not in fixtures.columns:
            continue

        original = fixtures[col]
        numeric = pd.to_numeric(original, errors="coerce")

        resolved_names = original.map(
            lambda value: (
                resolver.get(norm(value))
                if pd.notna(value)
                else pd.NA
            )
        )

        result = numeric.copy()
        mask = numeric.isna()

        result.loc[mask] = pd.to_numeric(
            resolved_names.loc[mask],
            errors="coerce",
        )

        fixtures[col] = result.astype("Int64")

        unresolved = original[fixtures[col].isna()].dropna()

        if not unresolved.empty:
            sample = (
                unresolved.astype(str)
                .drop_duplicates()
                .tolist()[:20]
            )
            raise RuntimeError(
                f"{season}: unable to resolve {col} team values "
                f"to numeric team IDs; sample: {sample}"
            )

    return fixtures
```

## 3. Replace the fixture numeric-conversion block

In `normalize_modern()`, replace:

```python
for col in [
    "fixture_code",
    "fixture_id",
    "gameweek",
    "team_a",
    "team_a_score",
    "team_h",
    "team_h_score",
    "team_h_difficulty",
    "team_a_difficulty",
    "minutes",
]:
    if col in fixtures.columns:
        fixtures[col] = pd.to_numeric(fixtures[col], errors="coerce")
```

with:

```python
for col in [
    "fixture_code",
    "fixture_id",
    "gameweek",
    "team_a_score",
    "team_h_score",
    "team_h_difficulty",
    "team_a_difficulty",
    "minutes",
]:
    if col in fixtures.columns:
        fixtures[col] = pd.to_numeric(fixtures[col], errors="coerce")

# Historical fixtures can contain team names instead of IDs.
fixtures = resolve_fixture_team_ids(fixtures, pdf, season)
```

## 4. Strengthen fixture validation

Replace:

```python
fixtures = fixtures.dropna(
    subset=["fixture_code", "fixture_id", "gameweek"]
).copy()
```

with:

```python
fixtures = fixtures.dropna(
    subset=[
        "fixture_code",
        "fixture_id",
        "gameweek",
        "team_h",
        "team_a",
    ]
).copy()

if len(fixtures) == 0:
    raise RuntimeError(
        f"{season}: no usable fixtures remain after normalization."
    )

if fixtures["team_h"].isna().any() or fixtures["team_a"].isna().any():
    raise RuntimeError(
        f"{season}: normalized fixtures contain missing team IDs."
    )
```

## 5. Update manifest version

Change:

```python
"schema_version": "1.3.0",
```

to:

```python
"schema_version": "1.4.0",
```

## 6. Add these design notes

Inside `design_notes`, add:

```python
"Fixture team_h/team_a values are normalized to canonical numeric team IDs when source fixtures provide team names.",
"Historical team-name resolution is derived from the season's player team_id/team fields; no hard-coded club-name mapping is used.",
```

## 7. Save

Save as:

```text
scripts/data/normalize_historical_seasons_v1_4.py
```

Do NOT overwrite v1.3 yet.

## 8. Test only 2022-23 first

From project root:

```powershell
python scripts\data\normalize_historical_seasons_v1_4.py --seasons 2022-23 --force --verbose
```

Then verify:

```powershell
python -c "import pandas as pd; p=r'data/processed/2022-23/historical/fixtures.csv'; df=pd.read_csv(p); print('Rows:',len(df)); print(df[['fixture_id','gameweek','team_h','team_a']].head(10).to_string(index=False)); print('team_h numeric:',pd.to_numeric(df['team_h'],errors='coerce').notna().all()); print('team_a numeric:',pd.to_numeric(df['team_a'],errors='coerce').notna().all())"
```

Expected:

```text
Rows: 380
team_h numeric: True
team_a numeric: True
```

Only after that run the feature builder.
