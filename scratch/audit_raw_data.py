import pandas as pd
import numpy as np

raw_path = "data/raw/ethusdt_5m_extension_ohlcv.parquet"
try:
    df = pd.read_parquet(raw_path)
except Exception as e:
    print(f"Error reading Parquet file: {e}")
    exit(1)

print("=== KRONOS RAW HISTORICAL DATA AUDIT ===")
print(f"File Path           : {raw_path}")
print(f"Total Rows (Bars)   : {len(df):,}")
print(f"Total Columns       : {len(df.columns)}")
print(f"Columns             : {list(df.columns)}")

print("\n--- Date & Time Coverage ---")
df["datetime"] = pd.to_datetime(df["datetime"])
min_date = df["datetime"].min()
max_date = df["datetime"].max()
print(f"Genesis Timestamp   : {min_date} (UTC)")
print(f"Latest Timestamp    : {max_date} (UTC)")
print(f"Total Days Covered  : {(max_date - min_date).days:.2f} days")

print("\n--- Null and Numeric Integrity ---")
null_counts = df.isnull().sum()
print("Null values per column:")
for col, count in null_counts.items():
    print(f"  - {col}: {count}")
    
# Check for negative prices or volumes
neg_prices = (df[['open', 'high', 'low', 'close']] <= 0).sum()
print("Non-positive prices:")
for col, count in neg_prices.items():
    print(f"  - {col}: {count}")

print("\n--- Time Continuity and Gap Analysis ---")
df_sorted = df.sort_values("datetime").reset_index(drop=True)
time_diffs = df_sorted["datetime"].diff()

# Standard delta is 5 minutes
standard_delta = pd.Timedelta(minutes=5)
gaps = time_diffs[time_diffs > standard_delta]
print(f"Total gaps (> 5 minutes): {len(gaps)}")
if len(gaps) > 0:
    print("Largest 5 gaps:")
    for idx, gap in gaps.nlargest(5).items():
        gap_start = df_sorted["datetime"].iloc[idx - 1]
        gap_end = df_sorted["datetime"].iloc[idx]
        print(f"  - Gap of {gap} between {gap_start} and {gap_end}")
else:
    print("  - Perfect 100% time continuity with zero gaps!")

print("\n=== AUDIT COMPLETE ===")
