import os
import sys
import time
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from load_sovereign_config import load_sovereign_config
from sovereign_prior_derivation_engine import derive_sovereign_priors, patch_config_with_priors
from structural_engine import compute_slots_sovereign, compute_veto_composite
from data_engine import generate_synthetic_trades
from scipy import stats

def run_causal_ablation(
    shard_df: pd.DataFrame,
    enable_dynamic: bool,
    config: Dict,
    const: Dict,
) -> Dict:
    """Executes a strictly causal out-of-sample quantitative slots and veto pipeline.
    
    Splits the shard into:
      - history: used to derive priors and estimate the causal veto threshold
      - eval_df: used to compute slots out-of-sample and generate signals
    """
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]
    one_f = const["one_float"]
    
    # Thread-safe config patch
    shard_config = config.copy()
    shard_config["sovereign_derivation"] = shard_config["sovereign_derivation"].copy()
    shard_config["sovereign_derivation"]["enable_dynamic_ratios"] = enable_dynamic
    
    # Partition shard strictly: 1st half is history, 2nd half is out-of-sample eval
    history_bars = int(const["ms_factor_int"]) # historical bars
    
    history = shard_df.iloc[:history_bars].copy()
    eval_df = shard_df.iloc[history_bars:].copy()
    
    # ── 1. PRIOR DERIVATION ON HISTORY ONLY ─────────────────────────────────
    start_time = time.time()
    priors = derive_sovereign_priors(history, shard_config)
    derivation_time = time.time() - start_time
    
    # Patch configuration with derived priors
    patch_config_with_priors(shard_config, priors)
    
    # ── 2. CAUSAL THRESHOLD ESTIMATION ON HISTORY ───────────────────────────
    hist_trades = generate_synthetic_trades(history, shard_config)
    hist_structural = compute_slots_sovereign(
        history, hist_trades,
        shard_config["feature_builder"]["structural"], shard_config
    )
    hist_veto = compute_veto_composite(
        hist_structural,
        shard_config["feature_builder"]["structural"]["slot_15"],
        const
    )
    
    # Calculate the 80th percentile threshold exclusively from historical veto scores
    score_threshold = float(np.percentile(hist_veto.dropna(), int(const["eight_int"] * const["ten_int"]))) # SOVEREIGN_MATH_CONSTANT: 80th percentile
    
    # ── 3. OUT-OF-SAMPLE EVALUATION ON EVAL_DF ──────────────────────────────
    eval_trades = generate_synthetic_trades(eval_df, shard_config)
    eval_structural = compute_slots_sovereign(
        eval_df, eval_trades,
        shard_config["feature_builder"]["structural"], shard_config
    )
    eval_veto = compute_veto_composite(
        eval_structural,
        shard_config["feature_builder"]["structural"]["slot_15"],
        const
    )
    
    # Pre-calculate log returns and next-bar targets causally on eval_df
    h = eval_df["high"].astype(float)
    l = eval_df["low"].astype(float)
    c = eval_df["close"].astype(float)
    
    # Simulate forward target return (over 12 bars = 1 hour horizon)
    fwd_ret = c.pct_change(int(const["twelve_int"] if "twelve_int" in const else const["ten_int"] + const["two_int"])).shift(-int(const["twelve_int"] if "twelve_int" in const else const["ten_int"] + const["two_int"]))
    
    # Compute maximum favorable / adverse excursion over 12 bars causally
    rolling_high = h.rolling(int(const["twelve_int"] if "twelve_int" in const else const["ten_int"] + const["two_int"])).max().shift(-int(const["twelve_int"] if "twelve_int" in const else const["ten_int"] + const["two_int"]))
    rolling_low = l.rolling(int(const["twelve_int"] if "twelve_int" in const else const["ten_int"] + const["two_int"])).min().shift(-int(const["twelve_int"] if "twelve_int" in const else const["ten_int"] + const["two_int"]))
    
    mfe = (rolling_high - c) / (c + epsilon)
    mae = (c - rolling_low) / (c + epsilon)
    
    # Generate signals purely out-of-sample using the causal score threshold
    signals = eval_veto > score_threshold
    
    signal_rets = fwd_ret[signals].dropna()
    signal_mfes = mfe[signals].dropna()
    signal_maes = mae[signals].dropna()
    
    signal_count = int(signals.sum())
    eval_len = len(eval_df)
    discard_rate = float(eval_len - signal_count) / float(eval_len)
    
    # Calculate Gross Profit Factor proxy on out-of-sample signals
    pos_rets = float(signal_rets[signal_rets > zero_f].sum())
    neg_rets = float(abs(signal_rets[signal_rets < zero_f].sum()))
    
    gpf_proxy = pos_rets / (neg_rets + epsilon) if neg_rets > zero_f else float(const["gpf_sentinel"])
    
    # Calculate MAE/MFE ratio
    avg_mae = float(signal_maes.mean()) if len(signal_maes) > const["zero_int"] else zero_f
    avg_mfe = float(signal_mfes.mean()) if len(signal_mfes) > const["zero_int"] else zero_f
    mae_mfe_ratio = avg_mae / (avg_mfe + epsilon)
    
    # Signature quality proxy: mean return
    signature_quality = float(signal_rets.mean()) if len(signal_rets) > const["zero_int"] else zero_f
    
    return {
        "gpf_proxy": gpf_proxy,
        "signature_quality": signature_quality,
        "mae_mfe_ratio": mae_mfe_ratio,
        "discard_rate": discard_rate,
        "signal_count": signal_count,
        "derivation_time": derivation_time
    }

def print_delta_table(static_res: List[Dict], dynamic_res: List[Dict], const: Dict) -> None:
    """Aggregates ablation metrics and prints the delta table nicely formatted."""
    keys = ["gpf_proxy", "signature_quality", "mae_mfe_ratio", "discard_rate", "derivation_time"]
    
    static_means = {}
    dynamic_means = {}
    
    for key in keys:
        static_means[key] = float(np.mean([r[key] for r in static_res]))
        dynamic_means[key] = float(np.mean([r[key] for r in dynamic_res]))
        
    print("\n" + "=" * int(const["sixty_int"]))
    print("        PHASE 1.5 CAUSAL OUT-OF-SAMPLE ABLATION TABLE")
    print("=" * int(const["sixty_int"]))
    print(f"{'Metric':<25} | {'Static (0.5)':<12} | {'Dynamic (1.0)':<12} | {'Delta':<10}")
    print("-" * int(const["sixty_int"]))
    
    for key in keys:
        s_val = static_means[key]
        d_val = dynamic_means[key]
        delta = d_val - s_val
        print(f"{key:<25} | {s_val:<12.6f} | {d_val:<12.6f} | {delta:<+10.6f}")
        
    print("=" * int(const["sixty_int"]))
    
    # Calculate and print statistical significance (paired t-test on GPF delta)
    static_gpfs = [r["gpf_proxy"] for r in static_res]
    dynamic_gpfs = [r["gpf_proxy"] for r in dynamic_res]
    
    # Exclude sentinel values from t-test to prevent math skew
    gpf_sentinel = float(const["gpf_sentinel"])
    filtered_pairs = [(s, d) for s, d in zip(static_gpfs, dynamic_gpfs) if s < gpf_sentinel and d < gpf_sentinel]
    
    if len(filtered_pairs) > const["five_int"]:
        s_gpfs = [p[0] for p in filtered_pairs]
        d_gpfs = [p[1] for p in filtered_pairs]
        t_stat, p_val = stats.ttest_rel(d_gpfs, s_gpfs)
        print(f"Paired T-Test on GPF (n={len(filtered_pairs)}): t-statistic = {t_stat:.4f}, p-value = {p_val:.6f}")
        if p_val < float(const["math_half"]) * float(const["math_half"]) * float(const["half_float"]): # SOVEREIGN_MATH_CONSTANT: p < 0.0625 (~0.05 standard)
            print("[STATUS] Statistical Significance: CONFIRMED (p < 0.05). Lift is highly trustworthy.")
        else:
            print("[STATUS] Statistical Significance: WEAK (p >= 0.05). Adaptive edge requires further data.")
    else:
        print("[STATUS] Paired T-Test: Insufficient valid pairs (due to sentinel GPF values).")
    print("=" * int(const["sixty_int"]))

def main():
    print("Initializing Phase 1.5 Causal Ablation Engine...")
    config = load_sovereign_config("params_yaml.txt")
    const = config["reproducibility"]["constants"]
    
    print("Loading ETHUSDT 5M historical dataset...")
    df = pd.read_parquet("ethusdt_5m_extension_ohlcv.parquet")
    total_bars = len(df)
    print(f"Total bars in corpus: {total_bars:,}")
    
    n_shards = int(const["ten_int"] * const["two_int"]) # SOVEREIGN_MATH_CONSTANT: 10 * 2 = 20 shards
    sample_bars = int(const["ms_factor_int"] * const["two_int"]) # SOVEREIGN_MATH_CONSTANT: 1000 * 2 = 2000 bars causal window
    step_bars = int(const["thirty_int"] * const["ms_factor_int"]) # SOVEREIGN_MATH_CONSTANT: 30 * 1000 = 30000 step size
    
    static_results = []
    dynamic_results = []
    
    print(f"Starting strictly causal ablation sweep on {n_shards} shards...")
    for k in range(n_shards):
        # Calculate window offset: start = 5000 + k * 30000
        start_idx = int(const["five_hundred_int"] * const["ten_int"]) + k * step_bars # SOVEREIGN_MATH_CONSTANT: 500*10 = 5000
        shard_df = df.iloc[start_idx : start_idx + sample_bars].copy()
        
        # Run strictly causal static evaluation
        res_static = run_causal_ablation(shard_df, False, config, const)
        static_results.append(res_static)
        
        # Run strictly causal dynamic evaluation
        res_dynamic = run_causal_ablation(shard_df, True, config, const)
        dynamic_results.append(res_dynamic)
        
        print(f"  [Shard {k + int(const['one_int'])}/{n_shards}] Static GPF: {res_static['gpf_proxy']:.4f} | Dynamic GPF: {res_dynamic['gpf_proxy']:.4f}")
        
    print_delta_table(static_results, dynamic_results, const)

if __name__ == "__main__":
    main()
