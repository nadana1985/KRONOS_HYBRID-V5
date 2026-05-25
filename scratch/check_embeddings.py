import pandas as pd
from pathlib import Path

parquet_path = Path("g:/KRONOS HYBRID/data/signatures_compact.parquet")
print(f"Loading compact dataset from: {parquet_path}")

df = pd.read_parquet(parquet_path)
embedding_cols = [f"slot_{i}" for i in range(16, 24)]

print("=== Check Slots 16-23 (Neural Embeddings) ===")
print("Columns checked:", embedding_cols)

# Check if they exist in DataFrame
missing = [c for c in embedding_cols if c not in df.columns]
if missing:
    print(f"Missing columns: {missing}")
else:
    # Summary statistics
    stats = df[embedding_cols].describe().T
    print("\nSummary Statistics for Embedding Slots:")
    print(stats[["mean", "std", "min", "max"]])
    
    print("\nSample values (first 5 rows):")
    print(df[embedding_cols].head(5).to_string())
