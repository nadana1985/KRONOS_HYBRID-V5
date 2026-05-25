import os
import pandas as pd
import numpy as np

def query_p99_extremes():
    compact_path = os.path.join("data", "signatures_compact.parquet")
    
    if not os.path.exists(compact_path):
        print("[ERROR] Compacted Parquet file not found!")
        return

    df = pd.read_parquet(compact_path)
    
    # Resolve the P99 threshold for Combined Quality (Slot 31)
    threshold = np.percentile(df["slot_31"].values, 99)
    p99_subset = df[df["slot_31"] >= threshold].copy()
    
    total_p99 = len(p99_subset)
    
    print("=========================================================")
    print("             [REPORT] KRONOS V5 P99 (TOP 1% SOVEREIGN) EXTREMES REPORT")
    print("=========================================================")
    print(f"Total P99 Signatures: {total_p99} records (Quality >= {threshold:.4f})\n")

    # MFE extremes
    max_mfe_row = p99_subset.loc[p99_subset["mfe"].idxmax()]
    min_mfe_row = p99_subset.loc[p99_subset["mfe"].idxmin()]
    
    # MAE extremes
    max_mae_row = p99_subset.loc[p99_subset["mae"].idxmax()]
    min_mae_row = p99_subset.loc[p99_subset["mae"].idxmin()]

    print("FORWARD MAX FAVORABLE EXCURSION (MFE) STATS:")
    print(f"  - HIGHEST MFE : {max_mfe_row['mfe']:.4%} occurred at {max_mfe_row['timestamp']}")
    print(f"                  [Quality: {max_mfe_row['slot_31']:.4f} | Veto: {max_mfe_row['slot_15']:.4f} | Conviction: {max_mfe_row['neural_conviction']:.4f}]")
    print(f"  - LOWEST MFE  : {min_mfe_row['mfe']:.4%} occurred at {min_mfe_row['timestamp']}")
    print(f"  - MEAN MFE    : {p99_subset['mfe'].mean():.4%}")
    
    print("\nFORWARD MAX ADVERSE EXCURSION (MAE) STATS:")
    print(f"  - HIGHEST MAE : {max_mae_row['mae']:.4%} occurred at {max_mae_row['timestamp']}")
    print(f"                  [Quality: {max_mae_row['slot_31']:.4f} | Veto: {max_mae_row['slot_15']:.4f} | Conviction: {max_mae_row['neural_conviction']:.4f}]")
    print(f"  - LOWEST MAE  : {min_mae_row['mae']:.4%} occurred at {min_mae_row['timestamp']}")
    print(f"  - MEAN MAE    : {p99_subset['mae'].mean():.4%}")
    print("=========================================================")

if __name__ == "__main__":
    query_p99_extremes()
