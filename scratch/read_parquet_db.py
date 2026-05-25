import os
from pathlib import Path
import pandas as pd

possible_roots = [
    Path("g:/KRONOS try 13may2026/"),
    Path("g:/KRONOS HYBRID/"),
]

parquet_files = []
print("Searching for Parquet files...")
for root_path in possible_roots:
    try:
        for r, d, f in os.walk(str(root_path)):
            if any(p in r for p in [".git", ".venv", "__pycache__", "node_modules"]):
                continue
            for filename in f:
                if filename.endswith(".parquet"):
                    p = Path(r) / filename
                    if any(term in filename.lower() for term in ["phylum", "archetype", "behavioral", "exit", "failure", "signatures_compact"]):
                        print(f"Found Parquet: {p}")
                        parquet_files.append(p)
    except Exception as e:
        print(f"Error scanning {root_path}: {e}")

# Process found files
for p in parquet_files:
    try:
        print(f"\n=======================================================")
        print(f"Reading Parquet file: {p.name}")
        print(f"Path: {p}")
        print(f"=======================================================")
        df = pd.read_parquet(p)
        print(f"Rows: {len(df)}, Columns: {list(df.columns)}")
        
        # Check if archetype and phylum columns exist
        arch_col = [c for c in df.columns if "archetype" in c.lower()]
        phylum_col = [c for c in df.columns if "phylum" in c.lower() or "slot_28" in c.lower()]
        
        print(f"Archetype cols: {arch_col}")
        print(f"Phylum cols: {phylum_col}")
        
        if arch_col:
            unique_archs = df[arch_col[0]].unique()
            print(f"Unique Archetypes in this file: {list(unique_archs)}")
            
            for target in ["Alpha Trend Builder", "Compression Snap"]:
                # Match case-insensitively or partially
                matches = df[df[arch_col[0]].astype(str).str.contains(target, case=False, na=False)]
                if len(matches) > 0:
                    print(f"\nFound {len(matches)} matches for '{target}':")
                    if phylum_col:
                        print(matches[[phylum_col[0], arch_col[0]] + [c for c in df.columns if c not in [phylum_col[0], arch_col[0]]][:3]].head(10).to_string())
                    else:
                        print(matches[arch_col[0] + [c for c in df.columns if c != arch_col[0]][:4]].head(10).to_string())
                else:
                    print(f"No matches for '{target}' in this file.")
        elif phylum_col:
            # Just print the first 5 rows to understand the structure
            print("\nFirst 5 rows:")
            print(df.head(5).to_string())
            
    except Exception as e:
        print(f"Error reading {p}: {e}")
