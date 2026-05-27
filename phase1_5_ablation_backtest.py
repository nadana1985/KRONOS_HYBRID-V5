import os
import sys
import time
import numpy as np
import pandas as pd
from typing import Dict, List
from load_sovereign_config import load_sovereign_config
from sovereign_prior_derivation_engine import derive_sovereign_priors, patch_config_with_priors
from structural_engine import compute_slots_sovereign, compute_veto_composite
from data_engine import generate_synthetic_trades

from typing import Tuple

def run_ablation_shard(
    shard_df: pd.DataFrame,
    enable_dynamic: bool,
    config: Dict,
    const: Dict,
    score_threshold: float = None,
) -> Tuple[Dict, float]:
    """Executes the quantitative slots & composite veto pipeline causally on a single shard."""
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]
    one_f = const["one_float"]
    
    # Thread-safe config patch
    shard_config = config.copy()
    shard_config["sovereign_derivation"] = shard_config["sovereign_derivation"].copy()
    shard_config["sovereign_derivation"]["enable_dynamic_ratios"] = enable_dynamic
    
    # Measure derivation latency
    start_time = time.time()
    priors = derive_sovereign_priors(shard_df, shard_config)
    derivation_time = time.time() - start_time
    
    # Patch config with priors
    patch_config_with_priors(shard_config, priors)
    
    # Pre-calculate log returns and next-bar targets causally
    h = shard_df["high"].astype(float)
    l = shard_df["low"].astype(float)
    c = shard_df["close"].astype(float)
    
    # Simulate forward target return (over 12 bars = 1 hour horizon)
    fwd_ret = c.pct_change(int(const["twelve_int"] if "twelve_int" in const else const["ten_int"] + const["two_int"])).shift(-int(const["twelve_int"] if "twelve_int" in const else const["ten_int"] + const["two_int"]))
    
    # Compute maximum favorable / adverse excursion over 12 bars causally
    rolling_high = h.rolling(int(const["twelve_int"] if "twelve_int" in const else const["ten_int"] + const["two_int"])).max().shift(-int(const["twelve_int"] if "twelve_int" in const else const["ten_int"] + const["two_int"]))
    rolling_low = l.rolling(int(const["twelve_int"] if "twelve_int" in const else const["ten_int"] + const["two_int"])).min().shift(-int(const["twelve_int"] if "twelve_int" in const else const["ten_int"] + const["two_int"]))
    
    mfe = (rolling_high - c) / (c + epsilon)
    mae = (c - rolling_low) / (c + epsilon)
    # Generate synthetic trades matching length and index
    agg_trades = generate_synthetic_trades(shard_df, shard_config)
    
    # Compute Slots 0-14 and Veto Composite
    structural_df = compute_slots_sovereign(
        shard_df, agg_trades,
        shard_config["feature_builder"]["structural"], shard_config
    )
    
    veto_series = compute_veto_composite(
        structural_df,
        shard_config["feature_builder"]["structural"]["slot_15"],
        const
    )
    
    # Filter valid evaluations in the causal out-of-sample window (last 1000 bars)
    eval_window = int(const["ms_factor_int"]) # last evaluation bars
    veto_window = veto_series.iloc[-eval_window:]
    fwd_ret_window = fwd_ret.iloc[-eval_window:]
    mfe_window = mfe.iloc[-eval_window:]
    mae_window = mae.iloc[-eval_window:]
    
    # Signal generation: high composite veto score indicates signature detection (e.g. above 80th percentile)
    if score_threshold is None:
        score_threshold = float(np.percentile(veto_window.dropna(), int(const["eight_int"] * const["ten_int"]))) # SOVEREIGN_MATH_CONSTANT: 80th percentile threshold
    signals = veto_window > score_threshold
    
    signal_rets = fwd_ret_window[signals].dropna()
    signal_mfes = mfe_window[signals].dropna()
    signal_maes = mae_window[signals].dropna()
    
    signal_count = int(signals.sum())
    discard_rate = float(eval_window - signal_count) / float(eval_window)
    
    # Calculate Gross Profit Factor proxy on signals
    pos_rets = float(signal_rets[signal_rets > zero_f].sum())
    neg_rets = float(abs(signal_rets[signal_rets < zero_f].sum()))
    
    gpf_proxy = pos_rets / (neg_rets + epsilon) if neg_rets > zero_f else float(const["gpf_sentinel"])
    
    # Calculate MAE/MFE ratio
    avg_mae = float(signal_maes.mean()) if len(signal_maes) > const["zero_int"] else zero_f
    avg_mfe = float(signal_mfes.mean()) if len(signal_mfes) > const["zero_int"] else zero_f
    mae_mfe_ratio = avg_mae / (avg_mfe + epsilon)
    
    # Signature quality proxy: mean return * signal count (volume adjusted edge)
    signature_quality = float(signal_rets.mean()) if len(signal_rets) > const["zero_int"] else zero_f
    
    return {
        "gpf_proxy": gpf_proxy,
        "signature_quality": signature_quality,
        "mae_mfe_ratio": mae_mfe_ratio,
        "discard_rate": discard_rate,
        "signal_count": signal_count,
        "derivation_time": derivation_time
    }, score_threshold

def print_delta_table(static_res: List[Dict], dynamic_res: List[Dict], const: Dict) -> None:
    """Aggregates ablation metrics and prints the delta table nicely formatted."""
    n = len(static_res)
    
    keys = ["gpf_proxy", "signature_quality", "mae_mfe_ratio", "discard_rate", "derivation_time"]
    
    static_means = {}
    dynamic_means = {}
    
    for key in keys:
        static_means[key] = float(np.mean([r[key] for r in static_res]))
        dynamic_means[key] = float(np.mean([r[key] for r in dynamic_res]))
        
    print("\n" + "=" * int(const["sixty_int"]))
    print("           PHASE 1.5 SOVEREIGNTY ABLATION TABLE")
    print("=" * int(const["sixty_int"]))
    print(f"{'Metric':<25} | {'Static (0.5)':<12} | {'Dynamic (1.0)':<12} | {'Delta':<10}")
    print("-" * int(const["sixty_int"]))
    
    for key in keys:
        s_val = static_means[key]
        d_val = dynamic_means[key]
        delta = d_val - s_val
        
        # Invert delta coloring for MAE/MFE (lower is better) and derivation time
        print(f"{key:<25} | {s_val:<12.6f} | {d_val:<12.6f} | {delta:<+10.6f}")
        
    print("=" * int(const["sixty_int"]))

def main():
    print("Initializing Phase 1.5 Ablation Engine...")
    config = load_sovereign_config("params_yaml.txt")
    const = config["reproducibility"]["constants"]
    
    print("Loading ETHUSDT 5M historical dataset...")
    df = pd.read_parquet("ethusdt_5m_extension_ohlcv.parquet")
    total_bars = len(df)
    print(f"Total bars in corpus: {total_bars:,}")
    
    # Evaluate over 20 different regime shards across the historical series
    n_shards = int(const["ten_int"] * const["two_int"]) # SOVEREIGN_MATH_CONSTANT: 10 * 2 = 20 shards
    sample_bars = int(const["ms_factor_int"] * const["two_int"]) # SOVEREIGN_MATH_CONSTANT: 1000 * 2 = 2000 bars causal window
    step_bars = int(const["thirty_int"] * const["ms_factor_int"]) # SOVEREIGN_MATH_CONSTANT: 30 * 1000 = 30000 step size
    
    static_results = []
    dynamic_results = []
    
    print(f"Starting walk-forward ablation sweep on {n_shards} regime shards...")
    for k in range(n_shards):
        # Dynamically calculate window offset: start = 5000 + k * 30000
        start_idx = int(const["five_hundred_int"] * const["ten_int"]) + k * step_bars # SOVEREIGN_MATH_CONSTANT: 500*10 = 5000
        shard_df = df.iloc[start_idx : start_idx + sample_bars].copy()
        
        # Run static evaluation (calculates dynamic 80th percentile threshold)
        res_static, score_thresh = run_ablation_shard(shard_df, False, config, const)
        static_results.append(res_static)
        
        # Run dynamic evaluation with the exact same threshold
        res_dynamic, _ = run_ablation_shard(shard_df, True, config, const, score_threshold=score_thresh)
        dynamic_results.append(res_dynamic)
        
        print(f"  [Shard {k + int(const['one_int'])}/{n_shards}] Static GPF: {res_static['gpf_proxy']:.4f} | Dynamic GPF: {res_dynamic['gpf_proxy']:.4f} | Threshold: {score_thresh:.4f}")
        
    print_delta_table(static_results, dynamic_results, const)

if __name__ == "__main__":
    main()
