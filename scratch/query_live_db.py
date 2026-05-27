"""
Query signatures directly from DuckDB (live, during pipeline run).
The pipeline writes via store_signatures_batch() which appends to tables in DuckDB.
"""
import duckdb
import os

# Try read-only connection to the live DuckDB
db_path = os.path.abspath("data/signatures.duckdb")
print(f"[INFO] Connecting to: {db_path}")

try:
    con = duckdb.connect(db_path, read_only=True)
    
    # List all tables / views
    tables = con.execute("SHOW TABLES").fetchdf()
    print(f"[INFO] Tables/Views:\n{tables}")
    
    # Try reading directly from the underlying table (not the view)
    try:
        sample = con.execute("SELECT * FROM signatures_raw LIMIT 2").fetchdf()
        print("signatures_raw columns:", list(sample.columns))
    except Exception as e:
        print(f"No signatures_raw: {e}")
    
    # Try reading from whatever tables exist
    for t in tables["name"].tolist():
        try:
            row = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()
            print(f"  Table '{t}': {row[0]} rows")
        except Exception as e:
            print(f"  Table '{t}': ERROR -> {e}")
    
    con.close()

except Exception as e:
    print(f"[ERROR] Cannot open DuckDB: {e}")
    # The writer holds an exclusive lock during batches
    # Let's try the parquet pattern directly
    import glob
    shards = glob.glob("data/signatures/**/*.parquet", recursive=True)
    print(f"[INFO] Parquet shards found: {len(shards)}")
    for s in shards:
        print(f"  {s}")
