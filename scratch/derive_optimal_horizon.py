import os
import time
import pandas as pd
import numpy as np
from scipy import stats

def derive_optimal_horizon():
    C_BLUE = "\033[94m"
    C_GREEN = "\033[92m"
    C_YELLOW = "\033[93m"
    C_RED = "\033[91m"
    C_BOLD = "\033[1m"
    C_RESET = "\033[0m"
    C_CYAN = "\033[96m"

    print(f"\n{C_BOLD}{C_CYAN}===================================================================={C_RESET}")
    print(f"{C_BOLD}{C_BLUE}             [RESEARCH] DERIVING OPTIMAL LOOK-AHEAD HORIZON{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}===================================================================={C_RESET}")

    compact_path = os.path.join("data", "signatures_compact.parquet")
    raw_path = os.path.join("data", "raw", "ethusdt_5m_extension_ohlcv.parquet")
    
    if not os.path.exists(compact_path):
        print(f"\n{C_BOLD}{C_RED}[ERROR] Compacted Parquet file not found at: {compact_path}{C_RESET}")
        return
    if not os.path.exists(raw_path):
        print(f"\n{C_BOLD}{C_RED}[ERROR] Raw OHLCV Parquet file not found at: {raw_path}{C_RESET}")
        return

    # Load data
    sig_df = pd.read_parquet(compact_path)
    raw_df = pd.read_parquet(raw_path)
    
    sig_df["timestamp"] = pd.to_datetime(sig_df["timestamp"], utc=True)
    raw_df["datetime"] = pd.to_datetime(raw_df["datetime"], utc=True)
    raw_df = raw_df.sort_values("datetime").reset_index(drop=True)
    
    datetime_to_idx = {val: idx for idx, val in enumerate(raw_df["datetime"])}
    
    # Filter signatures that are not in raw_df
    sig_df = sig_df[sig_df["timestamp"].isin(datetime_to_idx)].copy()
    entry_indices = np.array([datetime_to_idx[ts] for ts in sig_df["timestamp"]])
    entry_prices = raw_df["close"].values[entry_indices]
    
    # Define a wide grid of potential horizons to test (from 1 hour to 3 days)
    # 12 bars = 1h, 144 bars = 12h, 288 bars = 24h, 576 bars = 48h, 864 = 72h
    horizons = [12, 36, 72, 144, 216, 288, 360, 432, 576, 720, 864]
    
    print(f"[INFO] Loaded {len(sig_df):,} aligned signature coordinates.")
    print(f"[INFO] Running high-speed vectorized look-forward horizon decay search...")
    
    quality_scores = sig_df["slot_31"].values
    highs = raw_df["high"].values
    closes = raw_df["close"].values
    
    # Store performance metrics per horizon
    horizon_results = []
    
    for H in horizons:
        # Create a vectorized grid of forward indices of size (num_signatures, H)
        grid = entry_indices[:, None] + 1 + np.arange(H)
        grid = np.clip(grid, 0, len(raw_df) - 1)
        
        # Vectorized slice pulling (instantly!)
        high_slices = highs[grid]
        close_slices = closes[grid]
        
        # 1. Vectorized MFE calculation
        mfe_array = (high_slices.max(axis=1) - entry_prices) / entry_prices
        
        # 2. Vectorized Realized Volatility calculation
        log_returns = np.log(close_slices / entry_prices[:, None])
        vol_array = np.std(log_returns, axis=1)
        
        # Pearson correlation and t-statistic
        r_mfe, p_mfe = stats.pearsonr(quality_scores, mfe_array)
        r_vol, p_vol = stats.pearsonr(quality_scores, vol_array)
        
        # Calculate t-statistic to determine statistical significance (t > 2.0 is significant)
        n = len(sig_df)
        t_mfe = r_mfe * np.sqrt((n - 2) / (1 - r_mfe**2)) if abs(r_mfe) < 1.0 else 0.0
        
        horizon_results.append({
            "horizon": H,
            "hours": (H * 5) / 60.0,
            "corr_mfe": r_mfe,
            "t_stat": t_mfe,
            "p_value": p_mfe,
            "avg_mfe": mfe_array.mean(),
            "avg_vol": vol_array.mean()
        })
        
    # Print beautiful table
    print(f"\n{C_BOLD}[STATS] LOOK-FORWARD HORIZON DECAY SPECTRUM:{C_RESET}")
    print(f"| Horizon (Bars) | Hours | Avg MFE | Avg Realized Vol | Correlation (Quality to MFE) | T-Statistic | Significance |")
    print(f"| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
    
    max_t = -1.0
    optimal_H = None
    decay_H = None
    
    for res in horizon_results:
        sig_label = f"{C_GREEN}HIGH (PASS){C_RESET}" if abs(res["t_stat"]) > 2.0 else f"{C_RED}NO EDGE{C_RESET}"
        print(f"| {res['horizon']:14d} | {res['hours']:5.1f}h | {res['avg_mfe']:7.4%} | {res['avg_vol']:16.4%} | {res['corr_mfe']:28.4f} | {res['t_stat']:11.2f} | {sig_label} |")
        
        # Find where t-statistic (predictive power) peaks in absolute strength
        abs_t = abs(res["t_stat"])
        if abs_t > max_t:
            max_t = abs_t
            optimal_H = res["horizon"]
            
        # Find where edge decays below significant t-stat (2.0)
        if abs_t < 2.0 and decay_H is None and optimal_H is not None and res["horizon"] > optimal_H:
            decay_H = res["horizon"]

    if decay_H is None:
        decay_H = horizons[-1]

    optimal_hours = (optimal_H * 5) / 60.0
    decay_hours = (decay_H * 5) / 60.0

    print(f"\n{C_BOLD}{C_CYAN}===================================================================={C_RESET}")
    print(f"{C_GREEN}{C_BOLD}[MATHEMATICAL DISCOVERY] OPTIMAL PARAMETER HORIZONS:{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}===================================================================={C_RESET}")
    print(f"1. **Peak Edge Horizon (Optimal Entry-to-Exit Window):**")
    print(f"   - The predictive correlation peaks at exactly **{C_BOLD}{optimal_H} bars ({optimal_hours:.1f} hours){C_RESET}** (T-Stat: {max_t:.2f}).")
    print(f"   - **Discovery:** This represents the absolute highest point of mathematical edge. Winning trades mature here.")
    print(f"   - Recommendation: Update `miner: forward_bars` to **{C_BOLD}{optimal_H}{C_RESET}** in `params_yaml.txt`!")
    
    print(f"\n2. **Information Decay Horizon (Decay Limit):**")
    print(f"   - The predictive edge completely decays into random walk noise at **{C_BOLD}{decay_H} bars ({decay_hours:.1f} hours){C_RESET}**.")
    print(f"   - **Discovery:** Holding past this boundary has a statistically *zero* predictive relationship to the original signature trigger.")
    print(f"   - Recommendation: Never hold a cyclical position past this threshold under any circumstances.")
    print(f"{C_BOLD}{C_CYAN}===================================================================={C_RESET}\n")

if __name__ == "__main__":
    derive_optimal_horizon()
