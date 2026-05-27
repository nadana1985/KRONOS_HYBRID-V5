"""
KRONOS Slot-15 Relevance Diagnostic Tool (Enhanced)
===================================================
Extracts, parses, and formats the Spearman/Pearson/MI relevance metrics, standard errors,
Bayesian shrinkage adjustments, and alignment metadata for slots S00 to S14.
"""

import sys
import os
import argparse
import numpy as np
import pandas as pd

# Resolve workspace path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from load_sovereign_config import load_sovereign_config
from sovereign_prior_derivation_engine import (
    derive_sovereign_priors,
    _calculate_spearman_correlation,
    _calculate_pearson_correlation,
    _calculate_mutual_information
)
from data_engine import generate_synthetic_trades

def generate_synthetic_shard(bars: int = 6000) -> pd.DataFrame:
    """Generates clean synthetic OHLCV time-series data for testing."""
    np.random.seed(42)  # SOVEREIGN_MATH_CONSTANT
    rng = pd.date_range(start="2026-01-01", periods=bars, freq="5min")
    
    # Random walk close prices
    returns = np.random.normal(loc=0.0001, scale=0.001, size=bars)  # SOVEREIGN_MATH_CONSTANT
    close = 100.0 * np.exp(np.cumsum(returns))  # SOVEREIGN_MATH_CONSTANT
    high = close * (1.0 + np.abs(np.random.normal(0.0, 0.0005, size=bars)))  # SOVEREIGN_MATH_CONSTANT
    low = close * (1.0 - np.abs(np.random.normal(0.0, 0.0005, size=bars)))  # SOVEREIGN_MATH_CONSTANT
    open_p = close.copy()
    open_p[1:] = close[:-1]  # SOVEREIGN_MATH_CONSTANT
    open_p[0] = close[0]  # SOVEREIGN_MATH_CONSTANT
    volume = np.random.exponential(scale=100.0, size=bars)  # SOVEREIGN_MATH_CONSTANT
    
    return pd.DataFrame({
        "open": open_p,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "datetime": rng
    })

def main():
    parser = argparse.ArgumentParser(description="KRONOS Slot-15 Relevance Diagnostic Panel")
    parser.add_argument("--verbose", action="store_true", help="Print verbose details and raw correlations side-by-side.")
    parser.add_argument("--long-history", action="store_true", help="Use a long historical window (10,000 bars) for prior derivation.")
    parser.add_argument("--relevance-metric", type=str, default=None, choices=["spearman", "pearson", "mutual_info"],
                        help="Override YAML choice for relevance metric (spearman, pearson, mutual_info)")
    parser.add_argument("--horizon", type=int, default=None, help="Override return forecast horizon (shift bars).")
    
    args = parser.parse_args()
    
    print("====================================================================")
    print("            KRONOS VETO RELEVANCE & WEIGHT DIAGNOSTIC PANEL          ")
    print("====================================================================")
    
    config = load_sovereign_config("params_yaml.txt")
    const = config["reproducibility"]["constants"]
    
    # Determine sample bars
    bars_to_gen = 10000 if args.long_history else 6000  # SOVEREIGN_MATH_CONSTANT
    print(f"[DIAG] Simulating synthetic shard with {bars_to_gen} bars...")
    df = generate_synthetic_shard(bars=bars_to_gen)
    
    # Force adaptive weights to true to trigger relevance calculation
    config["sovereign_derivation"]["slot_15"]["enable_adaptive_weights"] = True
    
    # Apply overrides
    if args.relevance_metric:
        config["sovereign_derivation"]["slot_15"]["relevance_metric"] = args.relevance_metric
        print(f"[DIAG] Overriding relevance metric to: {args.relevance_metric}")
    if args.horizon:
        config["sovereign_derivation"]["slot_15"]["horizon_bars"] = args.horizon
        print(f"[DIAG] Overriding forecast horizon to: {args.horizon} bars")
        
    print("[DIAG] Generating structural slots on synthetic shard...")
    trades = generate_synthetic_trades(df, config)
    import structural_engine
    precomputed_structural_df = structural_engine.compute_slots_sovereign(
        df, trades,
        config["feature_builder"]["structural"], config
    )
    
    print("[DIAG] Deriving sovereign priors and relevance audit block...")
    priors = derive_sovereign_priors(
        df, config,
        precomputed_structural_df=precomputed_structural_df
    )
    
    audit = priors.get("_audit", {})
    relevance_audit = audit.get("_prior_derivations", {}).get("slot_15_weights", {})
    
    derived_weights = priors.get("slot_15_weights", {})
    static_weights = config["feature_builder"]["structural"]["slot_15"]["weights"]
    
    print("\nRelevance audit information:")
    print(f"  Confidence Floor Multiplier: {relevance_audit.get('confidence_floor_multiplier', 'N/A')}")
    print(f"  Shrinkage Base             : {relevance_audit.get('shrinkage_base', 'N/A')}")
    print(f"  Relevance Metric           : {relevance_audit.get('relevance_metric', 'N/A')}")
    
    align_meta = relevance_audit.get("alignment_metadata", {})
    if align_meta:
        print("\nUnified Alignment Diagnostics:")
        print(f"  Causal Aligned Samples    : {align_meta.get('aligned_sample_count', 0)}")
        print(f"  Alignment Dropped Bars    : {align_meta.get('alignment_dropped_bars', 0)}")
        print(f"  Forecast Horizon Shift    : {align_meta.get('horizon_bars', 0)}")
        print(f"  Regime Stability Factor   : {align_meta.get('regime_stability', 0.0):.6f}")
        print(f"  Shrinkage Beta Coeff      : {align_meta.get('shrinkage_beta', 0.0):.6f}")
    
    details = relevance_audit.get("relevance_details", {})
    
    print("\nSlot Weight Comparison & Relevance Breakdown:")
    print("-" * 115)
    print(f"{'Slot Key':<15} | {'Static Weight':<15} | {'Raw Relevance':<15} | {'Std Error':<12} | {'Floor':<12} | {'Derived Weight':<15} | {'Delta':<10}")
    print("-" * 115)
    
    for slot_key in sorted(static_weights.keys()):
        stat_w = static_weights[slot_key]
        deriv_w = derived_weights.get(slot_key, stat_w)
        delta = deriv_w - stat_w
        
        slot_info = details.get(slot_key, {})
        raw_corr = slot_info.get("raw_correlation", 0.0)
        std_err = slot_info.get("standard_error", 0.0)
        conf_floor = slot_info.get("confidence_floor", 0.0)
        
        print(f"{slot_key:<15} | {stat_w:<15.6f} | {raw_corr:<15.6f} | {std_err:<12.6f} | {conf_floor:<12.6f} | {deriv_w:<15.6f} | {delta:<+10.6f}")
        
    print("-" * 115)
    
    if args.verbose and align_meta:
        # Multi-metric comparisons
        print("\n[VERBOSE] Side-by-Side Multi-Metric Causal Relevance Profiling:")
        print("-" * 90)
        print(f"{'Slot Key':<15} | {'Spearman':<18} | {'Pearson':<18} | {'Mutual Information':<18}")
        print("-" * 90)
        
        # Prepare shifted data causally for comparison
        horizon = align_meta.get("horizon_bars", 12)  # SOVEREIGN_MATH_CONSTANT
        shifted_data = pd.DataFrame(index=df.index)
        
        for slot_key in static_weights.keys():
            if slot_key in precomputed_structural_df.columns:
                shifted_data[slot_key] = precomputed_structural_df[slot_key].shift(horizon)
                
        close = df["close"].astype(float)
        log_ret = np.log(close / close.shift(1) + 1e-9).fillna(0.0)  # SOVEREIGN_MATH_CONSTANT
        y_raw = log_ret.rolling(horizon, min_periods=horizon).sum().shift(-horizon)
        shifted_data["target_return"] = y_raw.shift(horizon)
        
        clean_data = shifted_data.dropna()
        y_arr = clean_data["target_return"].to_numpy(dtype=float)
        
        for slot_key in sorted(static_weights.keys()):
            if slot_key not in clean_data.columns:
                print(f"{slot_key:<15} | {'N/A':<18} | {'N/A':<18} | {'N/A':<18}")
                continue
            x_arr = clean_data[slot_key].to_numpy(dtype=float)
            
            # Compute Spearman
            spearman_val = _calculate_spearman_correlation(x_arr, y_arr, const)
            # Compute Pearson
            pearson_val = _calculate_pearson_correlation(x_arr, y_arr, const)
            # Compute MI
            mi_bins = int(np.ceil(np.log2(len(x_arr)) + 1.0))  # SOVEREIGN_MATH_CONSTANT
            mi_val = _calculate_mutual_information(x_arr, y_arr, mi_bins, const)
            
            print(f"{slot_key:<15} | {spearman_val:<18.6f} | {pearson_val:<18.6f} | {mi_val:<18.6f}")
        print("-" * 90)
        
    print("[OK] Relevance diagnostics complete.")

if __name__ == "__main__":
    main()
