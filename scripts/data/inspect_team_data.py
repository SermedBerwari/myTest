import pandas as pd

for season in ["2022-23", "2023-24", "2024-25", "2025-26"]:
    df = pd.read_csv(f"data/processed/{season}/historical/player_gameweek.csv")
    tid_nulls = df["team_id"].isna().sum()
    t_nulls = df["team"].isna().sum()
    tid_sample = df["team_id"].dropna().unique()[:5].tolist()
    t_sample = df["team"].dropna().unique()[:5].tolist()
    print(f"=== {season} ===")
    print(f"  team_id nulls: {tid_nulls} / {len(df)}")
    print(f"  team nulls:    {t_nulls} / {len(df)}")
    print(f"  team_id sample: {tid_sample}")
    print(f"  team sample:    {t_sample}")
    print()
