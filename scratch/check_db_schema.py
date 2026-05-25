import duckdb
import pandas as pd
from pathlib import Path

db_path = Path("g:/KRONOS HYBRID/data/signatures.duckdb")
print(f"Connecting to database at {db_path}...")
con = duckdb.connect(str(db_path))

# Check available tables/views
tables = con.execute("SHOW TABLES").fetchall()
print("Tables:", tables)

# Describe the signatures table/view if it exists
try:
    cols = con.execute("DESCRIBE signatures").fetchall()
    print("Signatures columns:")
    for col in cols:
        print(f"  {col[0]}: {col[1]}")
except Exception as e:
    print("Error describing signatures:", e)

# Also let's inspect the columns of one parquet file
try:
    parquet_files = list(Path("g:/KRONOS HYBRID/data/signatures").glob("**/*.parquet"))
    if parquet_files:
        df = pd.read_parquet(parquet_files[0])
        print("Parquet columns:")
        for col in df.columns:
            print(f"  {col}")
        print("First row values:")
        print(df.iloc[0].to_dict())
    else:
        print("No parquet files found.")
except Exception as e:
    print("Error reading parquet:", e)
