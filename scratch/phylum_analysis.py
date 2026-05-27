"""
Post-Run Phylum Analyser
Run this AFTER run_sharded_pipeline.py completes and compaction finishes.
Analyses data/signatures_compact.parquet for phylum MFE/MAE performance.
"""

import sys
import os
import duckdb
import pandas as pd

compact_path = os.path.abspath("data/signatures_compact.parquet")
partition_pattern = os.path.abspath("data/signatures")

def load_data():
    """Load signatures from compact file or partitioned parquets."""
    import glob

    con = duckdb.connect()

    if os.path.exists(compact_path):
        print(f"[INFO] Loading from compact file: {compact_path}")
        df = con.execute(f"SELECT * FROM read_parquet('{compact_path}')").fetchdf()
        con.close()
        return df

    shards = glob.glob("data/signatures/**/*.parquet", recursive=True)
    if shards:
        print(f"[INFO] Loading {len(shards)} shard parquet(s)")
        dfs = []
        for s in shards:
            p = os.path.abspath(s)
            dfs.append(con.execute(f"SELECT * FROM read_parquet('{p}')").fetchdf())
        con.close()
        return pd.concat(dfs, ignore_index=True)

    con.close()
    print("[ERROR] No signature data found. Ensure pipeline has completed.")
    sys.exit(1)


def analyse(df: pd.DataFrame):
    print(f"\n[INFO] Total signatures loaded  : {len(df):,}")
    print(f"[INFO] Columns: {list(df.columns)}")

    # Filter to mined only
    if "signature_flag" in df.columns:
        mined = df[df["signature_flag"] == 1].copy()
        print(f"[INFO] Mined signatures (flag=1) : {len(mined):,}")
    else:
        mined = df.copy()

    # Require phylum column
    if "slot_28" not in mined.columns:
        print("[WARN] slot_28 (phylum) column not found. Phylum labels are assigned post-run.")
        print("       Run this script after pipeline + compaction completes.")
        # Fall back to no-phylum analysis
        if "mfe" in mined.columns and "mae" in mined.columns:
            print(f"\n  Overall  MFE mean : {mined['mfe'].mean():.4f}")
            print(f"  Overall  MAE mean : {mined['mae'].mean():.4f}")
            print(f"  MFE/MAE ratio     : {mined['mfe'].mean() / (abs(mined['mae'].mean()) + 1e-9):.4f}")
        return

    # ── Group by phylum ──────────────────────────────────────────────────────
    agg = (
        mined.groupby("slot_28")
        .agg(
            count     = ("mfe", "count"),
            mean_mfe  = ("mfe", "mean"),
            med_mfe   = ("mfe", "median"),
            mean_mae  = ("mae", "mean"),
            med_mae   = ("mae", "median"),
            max_mfe   = ("mfe", "max"),
            min_mae   = ("mae", "min"),
        )
        .reset_index()
    )

    agg["mfe_mae_ratio"] = agg["mean_mfe"] / (agg["mean_mae"].abs() + 1e-9)
    agg = agg.sort_values("mfe_mae_ratio", ascending=False)

    pd.set_option("display.float_format", lambda x: f"{x:.4f}")
    pd.set_option("display.width", 180)

    print("\n" + "=" * 90)
    print("  PHYLUM PERFORMANCE REPORT  (sorted by MFE/MAE Ratio  desc)")
    print("=" * 90)
    print(agg.rename(columns={
        "slot_28"      : "Phylum",
        "count"        : "N",
        "mean_mfe"     : "MFE_mean",
        "med_mfe"      : "MFE_med",
        "mean_mae"     : "MAE_mean",
        "med_mae"      : "MAE_med",
        "max_mfe"      : "MFE_max",
        "min_mae"      : "MAE_min",
        "mfe_mae_ratio": "Ratio",
    }).to_string(index=False))

    best = agg.iloc[0]
    print("\n" + "=" * 90)
    print(f"  WINNER  ->  Phylum {int(best['slot_28'])}")
    print(f"              N            : {int(best['count'])}")
    print(f"              Mean MFE     : {best['mean_mfe']:.4f}")
    print(f"              Mean MAE     : {best['mean_mae']:.4f}")
    print(f"              MFE/MAE Ratio: {best['mfe_mae_ratio']:.4f}")
    print(f"              Max MFE      : {best['max_mfe']:.4f}")
    print("=" * 90)

    # Save summary CSV
    out = "scratch/phylum_summary.csv"
    agg.to_csv(out, index=False)
    print(f"\n[INFO] Summary saved -> {out}")


if __name__ == "__main__":
    df = load_data()
    analyse(df)
