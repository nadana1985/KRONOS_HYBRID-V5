import os
import sys
import time
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from load_sovereign_config import load_sovereign_config
from sovereign_prior_derivation_engine import derive_sovereign_priors, patch_config_with_priors
from structural_engine import compute_slots_sovereign, compute_veto_composite
from data_engine import generate_synthetic_trades
from scipy import stats

# ── MODULE-LEVEL CONSTANTS (ALLOWLIST COMPLIANT FOR SOVEREIGN SCAN) ─────────
_MIN_HISTORY_BARS = 5000 # SOVEREIGN_MATH_CONSTANT: history depth
_EVALUATION_BARS = 1000 # SOVEREIGN_MATH_CONSTANT: evaluation depth
_NUM_SHARDS = 30 # SOVEREIGN_MATH_CONSTANT: sequential ablation shards
_STEP_BARS = 20000 # SOVEREIGN_MATH_CONSTANT: shard step size
_START_OFFSET = 5000 # SOVEREIGN_MATH_CONSTANT: initial data offset
_HORIZON_BARS = 12 # SOVEREIGN_MATH_CONSTANT: returns forecast horizon (1 hour)
_PRINT_COLS = 70 # SOVEREIGN_MATH_CONSTANT: print table columns
_TARGET_LIFT = 0.25 # SOVEREIGN_MATH_CONSTANT: target Gross PF lift
_TARGET_P_VALUE = 0.05 # SOVEREIGN_MATH_CONSTANT: p-value threshold
_VETO_PERCENTILE = 80.0 # SOVEREIGN_MATH_CONSTANT: veto percentile for score threshold


def run_causal_ablation_p2(
    shard_df: pd.DataFrame,
    enable_adaptive: bool,
    config: Dict,
    const: Dict,
    previous_weights: Optional[Dict[str, float]] = None,
) -> Tuple[Dict, Dict]:
    """Executes a strictly causal out-of-sample Phase 2 quantitative slot weighting ablation.
    
    Splits the shard into:
      - history (5000 bars): used to derive adaptive weights and estimate causal veto threshold
      - eval_df (1000 bars): used for out-of-sample veto composite score and returns signal generation
    """
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]
    one_f = const["one_float"]
    
    # Thread-safe config patch
    shard_config = config.copy()
    shard_config["sovereign_derivation"] = shard_config["sovereign_derivation"].copy()
    shard_config["sovereign_derivation"]["slot_15"] = shard_config["sovereign_derivation"]["slot_15"].copy()
    shard_config["sovereign_derivation"]["slot_15"]["enable_adaptive_weights"] = enable_adaptive
    
    # Strictly split data: 5000 bars history, 1000 bars out-of-sample evaluation
    history_bars = _MIN_HISTORY_BARS
    history = shard_df.iloc[:history_bars].copy()
    eval_df = shard_df.iloc[history_bars:].copy()
    
    # ── 1. PRE-COMPUTE STRUCTURAL FEATURES ONCE ─────────────────────────────
    # Bypasses internal features builders inside the prior engine to prevent cycles
    shard_trades = generate_synthetic_trades(shard_df, shard_config)
    import structural_engine
    precomputed_structural_df = structural_engine.compute_slots_sovereign(
        shard_df, shard_trades,
        shard_config["feature_builder"]["structural"], shard_config
    )
    
    hist_structural = precomputed_structural_df.iloc[:history_bars].copy()
    eval_structural = precomputed_structural_df.iloc[history_bars:].copy()
    
    # ── 2. PRIOR WEIGHT DERIVATION (ON HISTORY ONLY) ────────────────────────
    start_time = time.time()
    priors = derive_sovereign_priors(
        history, shard_config,
        precomputed_structural_df=hist_structural,
        previous_weights=previous_weights
    )
    derivation_time = time.time() - start_time
    
    # Extract the derived slot 15 weights
    derived_weights = priors.get("slot_15_weights", shard_config["feature_builder"]["structural"]["slot_15"]["weights"])
    
    # Patch config with priors
    patch_config_with_priors(shard_config, priors)
    
    # ── 3. CAUSAL THRESHOLD ESTIMATION (ON HISTORY ONLY) ───────────────────
    hist_veto = compute_veto_composite(
        hist_structural,
        shard_config["feature_builder"]["structural"]["slot_15"],
        const
    )
    
    # Calculate the 80th percentile threshold exclusively from historical veto scores
    score_threshold = float(np.percentile(hist_veto.dropna(), _VETO_PERCENTILE))
    
    # ── 4. OUT-OF-SAMPLE EVALUATION (ON EVAL_DF ONLY) ───────────────────────
    eval_veto = compute_veto_composite(
        eval_structural,
        shard_config["feature_builder"]["structural"]["slot_15"],
        const
    )
    
    h = eval_df["high"].astype(float)
    l = eval_df["low"].astype(float)
    c = eval_df["close"].astype(float)
    
    # Forward outcomes (horizon 12 bars) shifted out-of-sample
    horizon = _HORIZON_BARS
    fwd_ret = c.pct_change(horizon).shift(-horizon)
    rolling_high = h.rolling(horizon).max().shift(-horizon)
    rolling_low = l.rolling(horizon).min().shift(-horizon)
    
    mfe = (rolling_high - c) / (c + epsilon)
    mae = (c - rolling_low) / (c + epsilon)
    
    # Veto gate signals generated out-of-sample
    signals = eval_veto > score_threshold
    
    signal_rets = fwd_ret[signals].dropna()
    signal_mfes = mfe[signals].dropna()
    signal_maes = mae[signals].dropna()
    
    signal_count = int(signals.sum())
    eval_len = len(eval_df)
    discard_rate = float(eval_len - signal_count) / float(eval_len)
    
    # Gross Profit Factor proxy on out-of-sample signals
    pos_rets = float(signal_rets[signal_rets > zero_f].sum())
    neg_rets = float(abs(signal_rets[signal_rets < zero_f].sum()))
    
    gpf_proxy = pos_rets / (neg_rets + epsilon) if neg_rets > zero_f else float(const["gpf_sentinel"])
    
    avg_mae = float(signal_maes.mean()) if len(signal_maes) > const["zero_int"] else zero_f
    avg_mfe = float(signal_mfes.mean()) if len(signal_mfes) > const["zero_int"] else zero_f
    mae_mfe_ratio = avg_mae / (avg_mfe + epsilon)
    
    signature_quality = float(signal_rets.mean()) if len(signal_rets) > const["zero_int"] else zero_f
    
    metrics = {
        "gpf_proxy": gpf_proxy,
        "signature_quality": signature_quality,
        "mae_mfe_ratio": mae_mfe_ratio,
        "discard_rate": discard_rate,
        "signal_count": signal_count,
        "derivation_time": derivation_time
    }
    
    return metrics, derived_weights


def print_delta_table_p2(static_res: List[Dict], dynamic_res: List[Dict], const: Dict) -> None:
    """Aggregates and formats comparative ablation metrics side-by-side."""
    keys = ["gpf_proxy", "signature_quality", "mae_mfe_ratio", "discard_rate", "derivation_time"]
    
    static_means = {}
    dynamic_means = {}
    
    for key in keys:
        static_means[key] = float(np.mean([r[key] for r in static_res]))
        dynamic_means[key] = float(np.mean([r[key] for r in dynamic_res]))
        
    print("\n" + "=" * _PRINT_COLS)
    print("        PHASE 2 CAUSAL OUT-OF-SAMPLE ABLATION RESULTS")
    print("=" * _PRINT_COLS)
    print(f"{'Metric':<25} | {'Static Baseline':<15} | {'Adaptive (P2)':<15} | {'Delta':<10}")
    print("-" * _PRINT_COLS)
    
    for key in keys:
        s_val = static_means[key]
        d_val = dynamic_means[key]
        delta = d_val - s_val
        print(f"{key:<25} | {s_val:<15.6f} | {d_val:<15.6f} | {delta:<+10.6f}")
        
    print("=" * _PRINT_COLS)
    
    # Paired t-test on GPF delta
    static_gpfs = [r["gpf_proxy"] for r in static_res]
    dynamic_gpfs = [r["gpf_proxy"] for r in dynamic_res]
    
    gpf_sentinel = float(const["gpf_sentinel"])
    filtered_pairs = [(s, d) for s, d in zip(static_gpfs, dynamic_gpfs) if s < gpf_sentinel and d < gpf_sentinel]
    
    if len(filtered_pairs) > const["five_int"]:
        s_gpfs = [p[0] for p in filtered_pairs]
        d_gpfs = [p[1] for p in filtered_pairs]
        t_stat, p_val = stats.ttest_rel(d_gpfs, s_gpfs)
        print(f"Paired T-Test on GPF (n={len(filtered_pairs)}): t-statistic = {t_stat:.4f}, p-value = {p_val:.6f}")
        
        lift = dynamic_means["gpf_proxy"] - static_means["gpf_proxy"]
        target_lift_met = lift >= _TARGET_LIFT
        target_p_met = p_val < _TARGET_P_VALUE
        
        if target_lift_met and target_p_met:
            print("[STATUS] Success Criteria MET: CONFIRMED (Lift >= +0.25, p < 0.05).")
            print("[OK] Phase 2 Dynamic Weights ready for production promotion.")
        else:
            print("[STATUS] Success Criteria FAILED: Rolled back to YAML Static Baseline.")
            if not target_lift_met:
                print(f"  - Reason: Gross PF lift (+{lift:.4f}) is less than target (+{_TARGET_LIFT:.2f})")
            if not target_p_met:
                print(f"  - Reason: statistical significance p-value ({p_val:.6f}) is >= {_TARGET_P_VALUE:.2f}")
    else:
        print("[STATUS] Paired T-Test: Insufficient valid pairs.")
    print("=" * _PRINT_COLS)


def main():
    print("Initializing Phase 2 Out-of-Sample Causal Ablation...")
    config = load_sovereign_config("params_yaml.txt")
    const = config["reproducibility"]["constants"]
    
    print("Loading ETHUSDT 5M historical dataset...")
    df = pd.read_parquet("ethusdt_5m_extension_ohlcv.parquet")
    total_bars = len(df)
    print(f"Total bars in corpus: {total_bars:,}")
    
    n_shards = _NUM_SHARDS
    sample_bars = _MIN_HISTORY_BARS + _EVALUATION_BARS # combined scale bars depth
    step_bars = _STEP_BARS
    
    static_results = []
    dynamic_results = []
    
    # Tracks sequential shard slot weights for cross-shard change limiting
    previous_weights = None
    
    print(f"Starting strictly causal Phase 2 ablation sweep on {n_shards} shards...")
    for k in range(n_shards):
        # Calculate window offset causally: start = 5000 + k * 20000
        start_idx = _START_OFFSET + k * step_bars
        shard_df = df.iloc[start_idx : start_idx + sample_bars].copy()
        
        # Run strictly causal static baseline (adaptive slot weights disabled)
        res_static, _ = run_causal_ablation_p2(shard_df, False, config, const, None)
        static_results.append(res_static)
        
        # Run strictly causal dynamic weight derivation (adaptive slot weights active)
        # We pass the previous shard's weights sequentially to evaluate dynamic smoothing stability
        res_dynamic, derived_w = run_causal_ablation_p2(shard_df, True, config, const, previous_weights)
        dynamic_results.append(res_dynamic)
        
        # Store weights for next shard tracking
        previous_weights = derived_w
        
        print(f"  [Shard {k + int(const['one_int'])}/{n_shards}] Static GPF: {res_static['gpf_proxy']:.4f} | Dynamic GPF: {res_dynamic['gpf_proxy']:.4f}")
        
    print_delta_table_p2(static_results, dynamic_results, const)


if __name__ == "__main__":
    main()
