import os
import pandas as pd
import numpy as np

def run_calibration():
    # ANSI terminal styling
    C_BLUE = "\033[94m"
    C_GREEN = "\033[92m"
    C_YELLOW = "\033[93m"
    C_RED = "\033[91m"
    C_BOLD = "\033[1m"
    C_RESET = "\033[0m"
    C_CYAN = "\033[96m"

    print(f"\n{C_BOLD}{C_CYAN}===================================================================={C_RESET}")
    print(f"{C_BOLD}{C_BLUE}             [CALIBRATION] KRONOS V5 GLOBAL PERCENTILES CALIBRATION STUDY{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}===================================================================={C_RESET}")

    compact_path = os.path.join("data", "signatures_compact.parquet")
    
    if not os.path.exists(compact_path):
        print(f"\n{C_BOLD}{C_RED}[ERROR] Compacted Parquet file not found at: {compact_path}{C_RESET}")
        return

    # Load compacted database
    df = pd.read_parquet(compact_path)
    total_records = len(df)
    
    print(f"\n[INFO] Loaded {total_records:,} historical signature states.")
    print("[INFO] Initiating mathematical percentile mapping...")

    # 1. Calculate Core Percentiles
    percentiles = [50, 75, 90, 95, 99, 99.9]
    metrics = {
        "Veto Score (Slot 15)": df["slot_15"],
        "Neural Conviction": df["neural_conviction"],
        "Combined Quality (Slot 31)": df["slot_31"]
    }

    print(f"\n{C_BOLD}[STATS] GLOBAL METRICS PERCENTILE DISTRIBUTION TABLE:{C_RESET}")
    print(f"| Metric | P50 (Median) | P75 | P90 | P95 (Elite) | P99 (Ultra) | P99.9 (Peak) |")
    print(f"| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
    
    for label, series in metrics.items():
        vals = np.percentile(series, percentiles)
        print(f"| {label} | {vals[0]:.4f} | {vals[1]:.4f} | {vals[2]:.4f} | {vals[3]:.4f} | {vals[4]:.4f} | {vals[5]:.4f} |")

    # 2. Correlate Quality Percentile Gates to Forward-Performance
    print(f"\n{C_BOLD}[MATRIX] DYNAMIC THRESHOLD PERFORMANCE CALIBRATION MATRIX:{C_RESET}")
    print(f"| Quality Cutoff | Mined Count | % of Total | Avg MFE | Avg MAE | Avg Recovery Factor | Win/Loss Ratio * |")
    print(f"| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")

    # Define Win/Loss Ratio where win = forward MFE > MAE
    win_series = df["mfe"] > df["mae"]
    
    quality_values = df["slot_31"].values
    for pct in [0, 50, 75, 90, 95, 99]:
        threshold = np.percentile(quality_values, pct)
        subset = df[df["slot_31"] >= threshold]
        
        subset_len = len(subset)
        pct_of_total = (subset_len / total_records) * 100
        avg_mfe = subset["mfe"].mean()
        avg_mae = subset["mae"].mean()
        avg_rec = subset["recovery_factor"].mean()
        
        subset_wins = win_series.loc[subset.index]
        win_ratio = subset_wins.mean() if subset_len > 0 else 0.0
        
        label = f"P{pct} (>= {threshold:.4f})" if pct > 0 else f"No Gate (>= {threshold:.4f})"
        print(f"| {label} | {subset_len:8,} | {pct_of_total:9.1f}% | {avg_mfe:7.4%} | {avg_mae:7.4%} | {avg_rec:19.4f} | {win_ratio:16.2%} |")

    print(f"\n* Note: Win/Loss Ratio defined as the frequency of Forward Max Favorable Excursion (MFE) exceeding Max Adverse Excursion (MAE).")

    # 3. Output Recommended Calibration values
    p90_quality = np.percentile(quality_values, 90)
    p95_quality = np.percentile(quality_values, 95)
    p90_veto = np.percentile(df["slot_15"].values, 90)
    
    print(f"\n{C_BOLD}{C_CYAN}===================================================================={C_RESET}")
    print(f"{C_GREEN}{C_BOLD}[RECOMMENDATIONS] MATHEMATICALLY CALIBRATED RECOMMENDATIONS:{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}===================================================================={C_RESET}")
    print(f"To target the **Top 10% elite cyclical states** (P90 Gate):")
    print(f"  - Set `database: min_quality_score` : {C_BOLD}{p90_quality:.4f}{C_RESET}")
    print(f"  - Set `miner: min_quality_score`    : {C_BOLD}{p90_quality:.4f}{C_RESET}")
    print(f"  - Set `structural: veto_threshold`  : {C_BOLD}{p90_veto:.4f}{C_RESET}")
    print(f"\nTo target the **Top 5% ultra-elite cyclical states** (P95 Gate):")
    print(f"  - Set `database: min_quality_score` : {C_BOLD}{p95_quality:.4f}{C_RESET}")
    print(f"  - Set `miner: min_quality_score`    : {C_BOLD}{p95_quality:.4f}{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}===================================================================={C_RESET}\n")

if __name__ == "__main__":
    run_calibration()
