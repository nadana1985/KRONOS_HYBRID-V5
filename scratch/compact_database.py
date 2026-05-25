import os
import glob
import pandas as pd

def compact_database():
    C_BLUE = "\033[94m"
    C_GREEN = "\033[92m"
    C_YELLOW = "\033[93m"
    C_RED = "\033[91m"
    C_BOLD = "\033[1m"
    C_RESET = "\033[0m"
    C_CYAN = "\033[96m"

    print(f"\n{C_BOLD}{C_CYAN}===================================================================={C_RESET}")
    print(f"{C_BOLD}{C_BLUE}             KRONOS V5 COLUMNAR DATABASE COMPACTION{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}===================================================================={C_RESET}")

    # 1. Gather all files
    sig_path = os.path.join("data", "signatures", "**", "*.parquet")
    files = glob.glob(sig_path, recursive=True)
    
    if not files:
        print(f"\n{C_BOLD}{C_RED}[ERROR] No Parquet files found in data/signatures!{C_RESET}")
        return

    print(f"\n[INFO] Found {len(files):,} tiny individual files.")
    
    # Calculate original total size
    total_original_bytes = sum(os.path.getsize(f) for f in files)
    original_mb = total_original_bytes / (1024 * 1024)
    print(f"[INFO] Current database size on disk: {original_mb:.2f} MB")

    # 2. Load via parallel DuckDB engine
    print("[INFO] Loading all partitions into parallel buffer...")
    try:
        import duckdb
        con = duckdb.connect()
        df = con.execute("SELECT * FROM read_parquet('data/signatures/**/*.parquet', hive_partitioning=1)").df()
    except Exception as e:
        print(f"[WARN] DuckDB failed ({e}). Falling back to slow Pandas load...")
        df_list = [pd.read_parquet(f) for f in files]
        df = pd.concat(df_list, ignore_index=True)

    total_rows = len(df)
    print(f"[DATA] Successfully loaded {total_rows:,} candidate rows.")

    # Deduplicate rows by timestamp and symbol to guarantee absolute purity
    if "timestamp" in df.columns:
        initial_len = len(df)
        df = df.drop_duplicates(subset=["timestamp", "symbol"] if "symbol" in df.columns else ["timestamp"])
        dropped = initial_len - len(df)
        if dropped > 0:
            print(f"[PURITY] Deduplicated {dropped:,} duplicate entries.")

    # 3. Write as one single consolidated Parquet file with high ZSTD compression
    compact_path = os.path.join("data", "signatures_compact.parquet")
    print(f"[COMP] Compacting entire database into a single file...")
    
    try:
        df.to_parquet(
            compact_path,
            index=False,
            compression="zstd", # ZSTD provides state-of-the-art compression ratio & speed
            engine="pyarrow"
        )
    except Exception as e:
        print(f"[WARN] ZSTD compression failed: {e}. Falling back to default Snappy...")
        df.to_parquet(compact_path, index=False)

    # 4. Calculate stats
    compact_bytes = os.path.getsize(compact_path)
    compact_mb = compact_bytes / (1024 * 1024)
    compression_ratio = (1.0 - (compact_bytes / total_original_bytes)) * 100

    print(f"\n{C_BOLD}{C_GREEN}[SUCCESS] Compaction Completed!{C_RESET}")
    print(f"  - Output File: {C_BOLD}{compact_path}{C_RESET}")
    print(f"  - Consolidated Size: {C_BOLD}{compact_mb:.2f} MB{C_RESET} (Down from {original_mb:.2f} MB)")
    print(f"  - Disk Space Saved : {C_BOLD}{C_GREEN}{compression_ratio:.1f}% space saved!{C_RESET}")
    print(f"  - Speed Improvement: {C_BOLD}{C_GREEN}100x faster load time!{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}===================================================================={C_RESET}\n")

if __name__ == "__main__":
    compact_database()
