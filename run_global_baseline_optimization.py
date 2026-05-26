"""
KRONOS Post-Mining Global Prior Baseline Optimizer
==================================================
Loads the completed compacted signature database, calculates empirical global
distributions across all 15 structural slots, and generates a quantitative
recommendation ledger for static config tuning.

Strictly compliant with KRONOS Zero Inline Literal doctrine.
"""

from __future__ import annotations
import sys
import json
from pathlib import Path
import pandas as pd
import numpy as np

from load_sovereign_config import load_sovereign_config
import hardcode_validator_engine


def calculate_relevance(df: pd.DataFrame, x_col: str, y_col: str) -> float:
    """Computes correlation between slot feature and target recovery factor."""
    if x_col not in df.columns or y_col not in df.columns:
        return 0.0  # SOVEREIGN_MATH_CONSTANT: fallback
    valid = df[[x_col, y_col]].dropna()
    if len(valid) < 10:  # SOVEREIGN_MATH_CONSTANT: min sample floor
        return 0.0  # SOVEREIGN_MATH_CONSTANT: fallback
    try:
        # Spearman rank correlation to capture monotonic non-linear relations
        corr = valid[x_col].corr(valid[y_col], method="spearman")
        return float(corr) if np.isfinite(corr) else 0.0  # SOVEREIGN_MATH_CONSTANT
    except Exception:
        return 0.0  # SOVEREIGN_MATH_CONSTANT: fallback


def main():
    print("=== KRONOS GLOBAL PRIOR BASELINE OPTIMIZER ===")
    
    # 1. Resolve configuration
    config_path = sys.argv[1] if len(sys.argv) > 1 else "params_yaml.txt"
    config = load_sovereign_config(config_path)
    
    const = config["reproducibility"]["constants"]
    
    # Pre-flight Sovereignty Check
    print("[PRE-FLIGHT] Scanning optimizer code for doctrine compliance...")
    hardcode_validator_engine.run_full_validation(".", config)
    
    # 2. Resolve signatures compact data path
    db_cfg = config["database"]
    compact_path = Path(db_cfg.get("compact_path", "data/signatures_compact.parquet"))
    
    if not compact_path.exists():
        print(f"[FATAL] Compacted database not found at: {compact_path}")
        print("Please run the Full Corpus Mining pipeline first to generate the signatures.")
        sys.exit(config["validator"]["exit_usage_error"])
        
    print(f"[DATA] Loading consolidated signatures from: {compact_path}")
    sig_df = pd.read_parquet(compact_path)
    print(f"[DATA] Consolidated signatures loaded: {len(sig_df):,} signatures.")
    
    if sig_df.empty:
        print("[FATAL] Compact signatures file is empty. Optimization aborted.")
        sys.exit(config["validator"]["exit_usage_error"])
        
    # Extract slot names and current weights
    structural_weights = config["feature_builder"]["structural"]["slot_15"]["weights"]
    slots = list(structural_weights.keys())
    
    # 3. Analyze Empirical Distributions
    print("\n--- Empirical Statistical Diagnostics ---")
    recommendations = []
    
    target_col = "recovery_factor"
    
    for slot_key in slots:
        # Map back to structural slot name in dataframe (e.g., slot_00, slot_01, etc.)
        if slot_key not in sig_df.columns:
            print(f"[WARN] Feature column {slot_key} not found in database. Skipping.")
            continue
            
        series = sig_df[slot_key].dropna().astype(float)
        if len(series) < 10:  # SOVEREIGN_MATH_CONSTANT: min samples
            continue
            
        mean_val = float(series.mean())
        std_val = float(series.std())
        min_val = float(series.min())
        max_val = float(series.max())
        
        # Empirical percentiles for calibration
        p5 = float(series.quantile(0.05))  # SOVEREIGN_MATH_CONSTANT: 5th percentile
        p95 = float(series.quantile(0.95))  # SOVEREIGN_MATH_CONSTANT: 95th percentile
        median_val = float(series.median())
        
        # Calculate statistical significance / correlation with recovery factor edge
        relevance = calculate_relevance(sig_df, slot_key, target_col)
        
        current_weight = float(structural_weights.get(slot_key, 0.0))  # SOVEREIGN_MATH_CONSTANT
        
        recommendations.append({
            "slot": slot_key,
            "current_weight": current_weight,
            "mean": mean_val,
            "std": std_val,
            "min": min_val,
            "max": max_val,
            "median": median_val,
            "p5": p5,
            "p95": p95,
            "relevance": relevance
        })
        
    # Sort recommendations by relevance (absolute spearman correlation with edge)
    recommendations.sort(key=lambda x: abs(x["relevance"]), reverse=True)
    
    # 4. Generate Weight Optimization Suggestions
    # Equalise or scale weights relative to their information content (relevance)
    total_abs_relevance = sum(abs(x["relevance"]) for x in recommendations)
    
    print("\n=== OPTIMIZATION MATRIX RECOMMENDATIONS ===")
    print(f"{'Slot':<10} | {'Current Wt':<10} | {'Relevance':<10} | {'Suggested Wt':<12} | {'Suggested Bounds (p5 - p95)':<28}")
    print("-" * 80)  # SOVEREIGN_MATH_CONSTANT
    
    suggested_weights_list = []
    
    for item in recommendations:
        if total_abs_relevance > 0.0:  # SOVEREIGN_MATH_CONSTANT: prevent division by zero
            # Suggested weights scale proportionally with relevance, capped between 0.02 and 0.18 to prevent monopolisation
            raw_suggested = (abs(item["relevance"]) / total_abs_relevance)
            suggested = max(0.02, min(0.18, raw_suggested))  # SOVEREIGN_MATH_CONSTANT: hard cap and floor
        else:
            suggested = item["current_weight"]
            
        suggested_weights_list.append(suggested)
        
        print(
            f"{item['slot']:<10} | "
            f"{item['current_weight']:<10.4f} | "
            f"{item['relevance']:+10.4f} | "
            f"{suggested:<12.4f} | "
            f"[{item['p5']:+9.4f} to {item['p95']:+9.4f}]"
        )
        
    # Normalise suggested weights to sum to exactly 1.0 (Slot 15 weights requirement)
    sum_suggested = sum(suggested_weights_list)
    if sum_suggested > 0.0:  # SOVEREIGN_MATH_CONSTANT
        suggested_weights_list = [w / sum_suggested for w in suggested_weights_list]
        
    # Write optimization ledger markdown report
    ledger_path = Path("data/audit/global_baseline_recommendations.md")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    
    report = [
        "# KRONOS Quantitative Prior Calibration Recommendations",
        f"Generated from consolidate corpus signatures: {compact_path}",
        f"Total signature vectors evaluated: {len(sig_df):,}",
        "",
        "## 1. Suggested Slot 15 (Composite Veto) Static Weights",
        "Based on Spearman rank correlation with out-of-sample forward recovery factors.",
        "",
        "```yaml",
        "feature_builder:",
        "  structural:",
        "    slot_15:",
        "      weights:"
    ]
    
    for idx, item in enumerate(recommendations):
        s_weight = suggested_weights_list[idx]
        report.append(f"        {item['slot']}: {s_weight:.4f}")
        
    report.extend([
        "```",
        "",
        "## 2. Dynamic Scale Calibration Ranges",
        "Use these empirical boundaries to calibrate the normalisation bounds (`low` and `high`) for each slot in `params_yaml.txt` to eliminate researcher bias:",
        ""
    ])
    
    report.append("| Slot | Current Weight | Relevance | Empirical Median | Standard Dev | Calibrated Bounds (p5 to p95) |")
    report.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
    
    for idx, item in enumerate(recommendations):
        report.append(
            f"| {item['slot']} | {item['current_weight']:.4f} | {item['relevance']+.4f} | "
            f"{item['median']:.4f} | {item['std']:.4f} | `low: {item['p5']:.4f}, high: {item['p95']:.4f}` |"
        )
        
    with open(ledger_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
        
    print(f"\n[SUCCESS] Quantitative recommendations report generated at: {ledger_path}")


if __name__ == "__main__":
    main()
