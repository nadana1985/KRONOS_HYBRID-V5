import pandas as pd
from pathlib import Path

files = {
    "sovereign_master_v45": r"g:\KRONOS try 13may2026\ETHreverseEngineer\data\processed\data_processed_ethusdt_5m_features_sovereign_master_v45.parquet",
    "sovereign_master_v45_FINAL": r"g:\KRONOS try 13may2026\ETHreverseEngineer\data\processed\ethusdt_5m_features_sovereign_master_v45_FINAL.parquet",
    "truth_extended": r"g:\KRONOS try 13may2026\ETHreverseEngineer\data\processed\ethusdt_5m_features_truth_extended.parquet",
    "walk_forward_regimes_v45": r"g:\KRONOS try 13may2026\ETHreverseEngineer\data\processed\walk_forward_regimes_v45.parquet",
    "raw_extension_ohlcv": r"g:\KRONOS HYBRID\data\raw\ethusdt_5m_extension_ohlcv.parquet"
}

print("Checking Parquet file ranges:")
print("=" * 60)

for name, path in files.items():
    p = Path(path)
    if not p.exists():
        print(f"[-] {name} does not exist at {path}")
        continue
    
    try:
        # Just read a single column or sample to check schema/ranges
        df = pd.read_parquet(p)
        
        # Determine datetime column
        dt_col = None
        for c in ["datetime", "timestamp", "open_time", "fundingTime"]:
            if c in df.columns:
                dt_col = c
                break
        
        if dt_col is None:
            print(f"[!] {name}: No time column found. Columns: {list(df.columns[:5])}")
            continue
            
        times = df[dt_col]
        
        # If integer timestamp, try to convert to datetime
        if pd.api.types.is_integer_dtype(times):
            # Assume epoch milliseconds
            times = pd.to_datetime(times, unit="ms", utc=True)
        else:
            times = pd.to_datetime(times, utc=True)
            
        print(f"[+] {name}:")
        print(f"    Path:  {path}")
        print(f"    Rows:  {len(df)}")
        print(f"    Range: {times.min()} to {times.max()}")
    except Exception as e:
        print(f"[x] Error reading {name}: {e}")
    print("-" * 60)
