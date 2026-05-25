import pandas as pd
from pathlib import Path

parquet_path = Path("g:/KRONOS HYBRID/data/signatures_compact.parquet")
print(f"Loading compact dataset from: {parquet_path}")

df = pd.read_parquet(parquet_path)
print(f"Dataset contains {len(df)} signatures.\n")

# Check Slot 28
if "slot_28" in df.columns:
    slot_28_col = df["slot_28"]
    print("=== SLOT 28 (Dynamic Phylum Clustering) ===")
    print(f"Data type: {slot_28_col.dtype}")
    print(f"Number of unique values: {slot_28_col.nunique()}")
    print("\nValue counts (Top 20):")
    counts = slot_28_col.value_counts(dropna=False)
    for val, count in counts.head(20).items():
        percentage = (count / len(df)) * 100
        label = "Noise (-1.0)" if val == -1.0 else f"Phylum {val}"
        print(f"  {label:<15}: {count:<8} ({percentage:.2f}%)")
else:
    print("slot_28 column not found!")

# Check Slot 29
if "slot_29" in df.columns:
    slot_29_col = df["slot_29"]
    print("\n=== SLOT 29 (Chronological Timestamp Hash) ===")
    print(f"Data type: {slot_29_col.dtype}")
    print(f"Number of unique values: {slot_29_col.nunique()}")
    print("\nSample values (first 10):")
    for val in slot_29_col.head(10).values:
        print(f"  {val} (hex: {hex(int(val)) if not pd.isna(val) else 'NaN'})")
else:
    print("slot_29 column not found!")
