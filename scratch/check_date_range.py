import pandas as pd
from pathlib import Path

parquet_path = Path("g:/KRONOS HYBRID/data/signatures_compact.parquet")
print(f"Loading compact dataset from: {parquet_path}")

df = pd.read_parquet(parquet_path)
print(f"Dataset loaded. Rows: {len(df)}")

if "timestamp" in df.columns:
    df["dt"] = pd.to_datetime(df["timestamp"])
    min_date = df["dt"].min()
    max_date = df["dt"].max()
    print(f"Date Range of signatures in this file:")
    print(f"  Start: {min_date}")
    print(f"  End:   {max_date}\n")
    
    # Check signature count per year
    if "year" in df.columns:
        print("Signature Count per Year:")
        year_counts = df["year"].value_counts().sort_index()
        for y, count in year_counts.items():
            print(f"  Year {y}: {count} signatures")
    else:
        # derive year from dt
        print("Signature Count per Year (derived):")
        year_counts = df["dt"].dt.year.value_counts().sort_index()
        for y, count in year_counts.items():
            print(f"  Year {y}: {count} signatures")
else:
    print("timestamp column not found!")
