"""
KRONOS Feature Builder Engine
================================
Orchestrates the complete causal thirty-two-slot DNA vector pipeline:
  raw_candles + agg_trades
    → causal slice (iloc[:t + one_int])
    → structural_engine.compute_slots_sovereign(...)
    → veto composite
    → neural gate (if veto passes and kronos enabled)
    → aux slots + metadata slots
    → full DNA vector assembly

ALL parameters resolve exclusively from cfg dicts. No inline literals.
"""

from __future__ import annotations

import hashlib
import numpy as np
import pandas as pd
from typing import Dict, Optional


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def build_full_dna_vector(
    raw_candles: pd.DataFrame,
    agg_trades_df: pd.DataFrame,
    current_idx: int,
    recent_convictions,
    config: Dict,
    precomputed_structural_df: Optional[pd.DataFrame] = None,
    precomputed_veto_composite: Optional[pd.Series] = None,
    precomputed_vol_forecast: Optional[pd.Series] = None,
) -> pd.Series:
    """
    Builds the complete DNA vector for bar at current_idx.
    Returns a pd.Series containing all slot values + gate outputs.

    Causal guarantee: only rows 0..current_idx (inclusive) are accessed.
    """
    const = config["reproducibility"]["constants"]
    one_i = const["one_int"]
    zero_f = const["zero_float"]

    # ── CAUSAL SLICE ──────────────────────────────────────────────────────
    causal_candles = raw_candles.iloc[: current_idx + one_i]
    causal_trades = agg_trades_df.iloc[: current_idx + one_i]

    # ── STRUCTURAL SOVEREIGN CORE & VETO COMPOSITE ─────────────────────────
    if precomputed_structural_df is not None and precomputed_veto_composite is not None:
        # High-performance optimization: use precomputed data to bypass O(N^2) loops
        structural_row = precomputed_structural_df.iloc[current_idx]
        current_veto_score = float(precomputed_veto_composite.iloc[current_idx])
    else:
        import structural_engine
        structural_df = structural_engine.compute_slots_sovereign(
            causal_candles,
            causal_trades,
            config["feature_builder"]["structural"],
            config,
        )
        veto_composite = structural_engine.compute_veto_composite(
            structural_df,
            config["feature_builder"]["structural"]["slot_15"],
            const,
        )
        structural_row = structural_df.iloc[-one_i]
        current_veto_score = float(veto_composite.iloc[-one_i])

    veto_threshold = config["feature_builder"]["structural"]["veto_threshold"]
    veto_passed = current_veto_score >= veto_threshold

    # ── NEURAL ORTHOGONAL GATE & EMBEDDINGS ───────────────────────────────
    enable_kronos = config["miner"]["enable_kronos"]
    emb_dim = config["kronos_mini"]["embedding_dim"]
    neural_conviction = zero_f
    dynamic_threshold = zero_f
    neural_passed = False
    pooled_emb = np.zeros(emb_dim, dtype=np.float32)

    if veto_passed and enable_kronos:
        import neural_integration_engine
        neural_conviction, dynamic_threshold, neural_passed, pooled_emb = (
            neural_integration_engine.compute_neural_gate(
                causal_candles,
                current_idx,
                recent_convictions,
                config["kronos_mini"],
                config["feature_builder"]["gate"],
                const,
            )
        )

    # ── SIGNATURE FLAG ────────────────────────────────────────────────────
    flag_key = config["feature_builder"]["gate"]["signature_flag_key"]
    conv_key = config["feature_builder"]["gate"]["neural_conviction_key"]
    thresh_key = config["feature_builder"]["gate"]["conviction_threshold_key"]
    veto_key = config["feature_builder"]["structural"]["slot_15"]["key_name"]
    signature_flag = veto_passed and (neural_passed or not enable_kronos)

    # ── AUXILIARY SLOTS ───────────────────────────────────────────────────
    aux_row = _compute_aux_slots(
        causal_candles, current_veto_score, neural_conviction, config,
        current_idx=current_idx, precomputed_vol_forecast=precomputed_vol_forecast,
        recent_convictions=recent_convictions
    )

    # ── METADATA SLOTS ────────────────────────────────────────────────────
    meta_row = _compute_metadata_slots(
        current_veto_score, neural_conviction, config, causal_candles
    )

    # ── ASSEMBLY ──────────────────────────────────────────────────────────
    row = structural_row.copy()

    # Add timestamp for rolling conviction updates
    row["timestamp"] = str(causal_candles["datetime"].iloc[current_idx])

    # Add veto composite score
    row[veto_key] = current_veto_score

    # Add Slots S_16 to S_23 (Neural Bottleneck Embeddings)
    slot_prefix = config["kronos_mini"].get("slot_key_prefix", "slot_")
    start_idx = config["kronos_mini"].get("slot_start_idx", 16)
    for i in range(emb_dim):
        col_name = f"{slot_prefix}{start_idx + i}"
        row[col_name] = float(pooled_emb[i])

    # Add gate outputs
    row[flag_key] = signature_flag
    row[conv_key] = neural_conviction
    row[thresh_key] = dynamic_threshold

    # Merge aux and metadata
    for k, v in aux_row.items():
        row[k] = v
    for k, v in meta_row.items():
        row[k] = v

    return row


def init_conviction_buffer(config: Dict) -> pd.Series:
    """
    Initialises an empty rolling conviction history buffer.
    """
    return pd.Series(dtype=float)


def update_conviction_buffer(
    buffer: pd.Series,
    dna_row: pd.Series,
    config: Dict,
) -> pd.Series:
    """
    Appends latest conviction score indexed by timestamp, and filters by time-based window from config.
    """
    conv_key = config["feature_builder"]["gate"]["neural_conviction_key"]
    const = config["reproducibility"]["constants"]
    zero_f = const["zero_float"]
    gate_cfg = config["feature_builder"]["gate"]
    time_window_days = float(gate_cfg["conviction_time_window_days"])

    ts_val = dna_row.get("timestamp")
    if ts_val is None:
        return buffer

    ts = pd.Timestamp(ts_val)
    new_score = float(dna_row.get(conv_key, zero_f))
    new_entry = pd.Series([new_score], index=[ts])

    if buffer.empty:
        updated = new_entry
    else:
        updated = pd.concat([buffer, new_entry])

    # Filter buffer by timestamp: keep only entries within the last time_window_days
    cutoff = ts - pd.Timedelta(days=time_window_days)
    filtered = updated[updated.index >= cutoff]
    return filtered


# ─────────────────────────────────────────────────────────────────────────────
# AUXILIARY SLOTS (24–27)
# ─────────────────────────────────────────────────────────────────────────────

def _compute_aux_slots(
    causal_candles: pd.DataFrame,
    veto_score: float,
    neural_conviction: float,
    config: Dict,
    current_idx: Optional[int] = None,
    precomputed_vol_forecast: Optional[pd.Series] = None,
    recent_convictions: Optional[pd.Series] = None,
) -> Dict:
    """
    Computes auxiliary slots. All parameter keys from config["feature_builder"]["aux"].
    Implementations are heuristic proxies; full stochastic versions in aux_engine.py.
    """
    aux_cfg = config["feature_builder"]["aux"]
    const = config["reproducibility"]["constants"]
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]

    result = {}

    # Slot vol_forecast: fast path if precomputed
    vol_cfg = aux_cfg["vol_forecast"]
    vol_lb = vol_cfg["lookback_bars"]
    if precomputed_vol_forecast is not None and current_idx is not None and len(precomputed_vol_forecast) > current_idx:
        vol_delta = float(precomputed_vol_forecast.iloc[current_idx])
    else:
        # FLAW 11 FIX: slice only the minimum required tail before computing rolling std.
        tail = causal_candles["close"].iloc[-(vol_lb + const["two_int"]):]
        log_ret_tail = np.log(tail / tail.shift(const["one_int"]) + epsilon)
        vol_series_tail = log_ret_tail.rolling(vol_lb).std()
        vol_now = float(vol_series_tail.iloc[-const["one_int"]]) if len(vol_series_tail) >= const["one_int"] else zero_f
        vol_prev = float(vol_series_tail.iloc[-const["two_int"]]) if len(vol_series_tail) >= const["two_int"] else zero_f
        vol_delta = vol_now - vol_prev

    result[vol_cfg["key_name"]] = vol_delta

    # Slot mfe_projection: structural veto score scaled by volatility-adjusted excursion projection
    mfe_cfg = aux_cfg["mfe_projection"]
    horizon = mfe_cfg["horizon_bars"]
    tail_len = horizon + const["one_int"]
    mfe_tail = causal_candles["close"].iloc[-tail_len:]
    mfe_returns = np.log(mfe_tail / mfe_tail.shift(const["one_int"]) + epsilon)
    vol_rolling = float(mfe_returns.std())
    if np.isnan(vol_rolling):
        vol_rolling = zero_f
    mfe_proj_val = veto_score * (const["one_float"] + vol_rolling * np.sqrt(float(horizon)))
    result[mfe_cfg["key_name"]] = float(mfe_proj_val)

    # Slot neural_regime: neural conviction percentile as regime strength intensity
    nr_cfg = aux_cfg["neural_regime"]
    if recent_convictions is not None and len(recent_convictions) > const["zero_int"]:
        count_less = (recent_convictions <= neural_conviction).sum()
        intensity = float(count_less) / float(len(recent_convictions) + epsilon)
    else:
        intensity = neural_conviction
    result[nr_cfg["key_name"]] = float(intensity)

    # Slot residual: Euclidean residual (veto_score - neural_conviction)
    res_cfg = aux_cfg["residual"]
    result[res_cfg["key_name"]] = abs(veto_score - neural_conviction)

    if const.get("finite_check_enabled", True):
        z_clip = const.get("z_clip_default", 10.0)
        for k, v in result.items():
            if not np.isfinite(v):
                result[k] = zero_f

    return result


# ─────────────────────────────────────────────────────────────────────────────
# METADATA SLOTS (28–31)
# ─────────────────────────────────────────────────────────────────────────────

def _compute_metadata_slots(
    veto_score: float,
    neural_conviction: float,
    config: Dict,
    causal_candles: pd.DataFrame,
) -> Dict:
    """
    Computes metadata slots: phylum placeholder, timestamp hash,
    recovery proxy, and quality score.
    Phylum assignment (HDBSCAN) is performed post-hoc in miner_engine.
    """
    meta_cfg = config["feature_builder"]["metadata"]
    const = config["reproducibility"]["constants"]
    zero_f = const["zero_float"]
    one_f = const["one_float"]
    epsilon = const["epsilon"]
    keys = meta_cfg["keys"]

    result = {}

    # Phylum: placeholder — assigned by miner_engine.assign_phylum()
    result[keys["phylum_id"]] = zero_f

    # Timestamp hash: deterministic SHA-256 of last bar timestamp bounded in [0, 1]
    ts_str = str(causal_candles.index[-const["one_int"]])
    eight_int = const["eight_int"]
    sixteen_int = const["sixteen_int"]
    ts_hash = int(hashlib.sha256(ts_str.encode()).hexdigest()[:eight_int], sixteen_int)
    max_hash = float(const["max_timestamp_hash"])
    result[keys["timestamp_hash"]] = float(ts_hash) / (max_hash + epsilon)

    # Recovery proxy: veto * neural_conviction normalised
    result[keys["recovery_proxy"]] = float(
        min(veto_score * neural_conviction / (one_f + epsilon), one_f)
    )

    # Signature quality: mean of veto and conviction
    result[keys["signature_quality"]] = float(
        (veto_score + neural_conviction) / float(const["two_int"])
    )

    return result
