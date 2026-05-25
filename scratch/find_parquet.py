import os
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

# We'll search recursively in G:\
root_dir = "G:\\"
target_date = datetime(2026, 5, 12, 0, 0, 0, tzinfo=timezone.utc)

print(f"Scanning G:\\ for Parquet files extending past May 12, 2026...")
print("=" * 60)

for root, dirs, files in os.walk(root_dir):
    # Skip standard system or git folders
    if any(p in root.lower() for p in [".git", "node_modules", "$recycle.bin", "system volume information", "__pycache__"]):
        continue
        
    for file in files:
        if file.endswith(".parquet"):
            path = Path(root) / file
            
            try:
                # Read a small subset of the datetime/timestamp column
                # We try both names
                df = None
                for col in ["datetime", "timestamp", "open_time"]:
                    try:
                        df = pd.read_parquet(path, columns=[col])
                        dt_col = col
                        break
                    except Exception:
                        continue
                        
                if df is not None:
                    times = df[dt_col]
                    if pd.api.types.is_integer_dtype(times):
                        times = pd.to_datetime(times, unit="ms", utc=True)
                    else:
                        times = pd.to_datetime(times, utc=True)
                        
                    max_time = times.max()
                    if max_time > target_date:
                        print(f"[FOUND] {file}")
                        print(f"    Path:  {path}")
                        print(f"    Range: {times.min()} to {max_time}")
                        print("-" * 60)
            except Exception:
                # Ignore unreadable files or files without time columns
                continue
