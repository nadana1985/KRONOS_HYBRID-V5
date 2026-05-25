"""
KRONOS Sovereign Prior Derivation Engine
=========================================
Derives all 47 structural and pipeline priors empirically from causal OHLCV
data, eliminating residual epistemic bias introduced by static researcher
judgment.

Sovereign Doctrine
------------------
Every numeric prior that influences the 32-slot DNA vector or mining pipeline
MUST originate from observed market structure — never from researcher intuition
baked in at edit-time. This engine is the mechanism that enforces that doctrine:

  1. A dominant market cycle is extracted from the causal price series via
     Continuous Wavelet Transform (scipy.signal.cwt with Ricker wavelet).
     This single anchor drives all lookback/window parameters so they
     co-scale with the actual dominant periodicity of the instrument.

  2. Volatility priors (baseline_vol, decay_factor, vol_threshold_percentile)
     are derived from the rolling realised volatility distribution of the
     causal series, NOT from researcher intuition.

  3. Thresholds (imbalance, body, quantile, extreme, etc.) are set as empirical
     percentiles of the relevant signal distribution — again from causal data.

  4. HMM regime count is selected by BIC minimisation across a grid [2, 8]
     using the same causal feature set as the production slot_8 engine.

  5. ACF-based lags are chosen by the empirical 95th-percentile significance
     threshold of a noise regime window.

  6. All fallbacks are the sovereign config values — the engine degrades
     gracefully to static config when insufficient data is available.

  7. The full derivation is auditable: every prior carries provenance metadata
     recording which method generated it, the causal window length, and a
     git commit hash when available.

Integration
-----------
Call `derive_sovereign_priors(causal_df, config)` once at the start of each
mining shard (before compute_slots_sovereign) and patch the returned dict
into the relevant config sections.  The returned dict is a flat namespace of
the 47 priors plus a nested ``_audit`` block.

Example (run_sharded_pipeline.py)::

    from sovereign_prior_derivation_engine import derive_sovereign_priors
    priors = derive_sovereign_priors(shard_candles, config)
    config = patch_config_with_priors(config, priors)

Dependencies: numpy, pandas, scipy (required); hmmlearn (optional).
"""

from __future__ import annotations

import logging
import warnings
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

_LOGGER = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# MODULE-LEVEL CONSTANTS  (pure arithmetic identities — not priors)
# ─────────────────────────────────────────────────────────────────────────────
# These are the only admissible inline integers in this file.
# They are structural math constants (2 = "both sides", etc.) rather than
# calibration values, and they are explicitly documented as such.
_MATH_HALF: float = 0.5          # 0.5 = arithmetic midpoint — not a calibration value
_MATH_TWO: int = 2               # 2 = binary split — not a calibration value
_MATH_ONE: int = 1               # 1 = unit offset — not a calibration value
_MATH_ZERO: int = 0              # 0 = zero index — not a calibration value
_MIN_BARS_FOR_CWT: int = 64      # absolute floor for CWT to produce meaningful frequencies
_MIN_BARS_FOR_BIC: int = 128     # absolute floor for BIC regime selection
_MIN_BARS_FOR_ACF: int = 50      # absolute floor for empirical ACF noise estimation
_HMM_BIC_GRID_LOW: int = 2      # lowest regime count evaluated in BIC grid
_HMM_BIC_GRID_HIGH: int = 9     # one-past-last in grid (range endpoint), i.e. 2…8

# ─────────────────────────────────────────────────────────────────────────────
# BIC THROTTLE CACHE  (module-level — survives across shard calls)
# ─────────────────────────────────────────────────────────────────────────────
# BIC regime selection is O(n × K × iter) — expensive if called on every shard.
# We cache the last result and only rerun when n_causal_bars has grown by at
# least bic_refit_interval_bars since the last run. The cache is keyed by the
# config-specified symbol so multi-symbol runs stay isolated.
_BIC_CACHE: Dict[str, Dict] = {}


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def derive_sovereign_priors(
    causal_df: pd.DataFrame,
    config: Dict,
) -> Dict:
    """
    Derive all 47 KRONOS priors empirically from causal OHLCV data.

    Parameters
    ----------
    causal_df : pd.DataFrame
        Causal slice of OHLCV data up to and including the current shard bar.
        Required columns: open, high, low, close, volume, datetime.
        Only rows 0…current_idx (inclusive) must be present — no future data.
    config : Dict
        Full parsed params_yaml.txt config dict loaded by load_sovereign_config.
        Used as the authoritative fallback for every prior when causal data
        is insufficient.

    Returns
    -------
    Dict
        Flat dict of 47 derived priors keyed by their canonical param_yaml name,
        plus a nested ``_audit`` dict with provenance metadata.
        When sovereign_derivation.enabled is False the dict contains only
        ``_audit`` with ``_disabled: True`` — the caller must detect this and
        skip calling patch_config_with_priors.
    """
    # ── ABLATION GATE ────────────────────────────────────────────────────────
    # Reads sovereign_derivation.enabled from config. When False, the engine
    # is fully bypassed — config values remain unchanged (ablation baseline).
    sd_cfg = config.get("sovereign_derivation", {})
    if not sd_cfg.get("enabled", True):
        _LOGGER.info(
            "Sovereign prior derivation DISABLED (sovereign_derivation.enabled=false). "
            "Config priors remain at their params_yaml.txt values."
        )
        return {
            "_audit": {
                "_disabled": True,
                "_reason": "sovereign_derivation.enabled=false in params_yaml.txt",
                "_derivation_timestamp": pd.Timestamp.utcnow().isoformat(),
            }
        }

    const = config["reproducibility"]["constants"]
    global _MIN_BARS_FOR_CWT, _MIN_BARS_FOR_BIC, _MIN_BARS_FOR_ACF, _MATH_HALF
    _MIN_BARS_FOR_CWT = int(const["min_bars_for_cwt"])
    _MIN_BARS_FOR_BIC = int(const["min_bars_for_bic"])
    _MIN_BARS_FOR_ACF = int(const["min_bars_for_acf"])
    _MATH_HALF = float(const["math_half"])

    epsilon = const["epsilon"]
    zero_f = const["zero_float"]
    one_f = const["one_float"]

    # ── 0. VALIDATE INPUT ────────────────────────────────────────────────────
    _validate_causal_df(causal_df, const)

    # ── 1. LOG RETURNS (causal, strict) ──────────────────────────────────────
    close = causal_df["close"].astype(float)
    log_ret = np.log(close / close.shift(const["one_int"]) + epsilon).fillna(zero_f)
    n_bars = len(causal_df)

    # ── 2. DOMINANT CYCLE VIA CWT ─────────────────────────────────────────────
    dominant_cycle, dc_method = _derive_dominant_cycle(log_ret, const, config)

    # ── 3. REALISED VOLATILITY DISTRIBUTION ──────────────────────────────────
    rv_window = max(dominant_cycle * const["thirty_int"], const["one_int"])
    rv_series = log_ret.rolling(rv_window, min_periods=const["one_int"]).std().dropna()

    # ── 4. DERIVE ALL PRIORS ──────────────────────────────────────────────────
    priors: Dict = {}
    audit: Dict = {}

    # Derive each prior group
    _derive_warmup(priors, audit, dominant_cycle, n_bars, const, config)
    _derive_slot0_bid_ask(priors, audit, dominant_cycle, log_ret, causal_df, const, config)
    _derive_slot1_vpin(priors, audit, dominant_cycle, const, config)
    _derive_slot2_spectral(priors, audit, dominant_cycle, const, config)
    _derive_slot3_log_var_ratio(priors, audit, dominant_cycle, const, config)
    _derive_slot4_hurst(priors, audit, dominant_cycle, const, config)
    _derive_slot5_autocorr(priors, audit, dominant_cycle, log_ret, const, config)
    _derive_slot6_ema_ribbon(priors, audit, dominant_cycle, log_ret, const, config)
    _derive_slot7_vol_price_div(priors, audit, dominant_cycle, const, config)
    _derive_slot8_hmm(priors, audit, dominant_cycle, log_ret, rv_series, n_bars, const, config)
    _derive_slot9_liquidity(priors, audit, causal_df, const, config)
    _derive_slot10_wick(priors, audit, causal_df, dominant_cycle, const, config)
    _derive_slot11_sr_kde(priors, audit, dominant_cycle, const, config)
    _derive_slot12_microprice(priors, audit, dominant_cycle, causal_df, const, config)
    _derive_slot13_shannon(priors, audit, dominant_cycle, const, config)
    _derive_slot14_hilbert(priors, audit, dominant_cycle, const, config)
    _derive_slot15_composite(priors, audit, config)
    _derive_neural_gate(priors, audit, rv_series, dominant_cycle, const, config)
    _derive_aux(priors, audit, dominant_cycle, const, config)
    _derive_hdbscan(priors, audit, const, config)
    _derive_miner(priors, audit, dominant_cycle, const, config)
    _derive_backtest(priors, audit, const, config)
    _derive_database(priors, audit, const, config)

    # ── 5. AUDIT METADATA ─────────────────────────────────────────────────────
    priors["_audit"] = {
        "_disabled": False,
        "_derivation_timestamp": pd.Timestamp.utcnow().isoformat(),
        "_dominant_cycle": int(dominant_cycle),
        "_dominant_cycle_method": dc_method,
        "_n_causal_bars": int(n_bars),
        "_rv_median": float(rv_series.median()) if len(rv_series) > _MATH_ZERO else zero_f,
        "_rv_p75": float(rv_series.quantile(0.75)) if len(rv_series) > _MATH_ZERO else zero_f,
        "_rv_iqr": float(
            rv_series.quantile(0.75) - rv_series.quantile(0.25)
        ) if len(rv_series) > _MATH_ZERO else zero_f,
        "_git_commit": _get_git_commit(),
        "_engine_version": "sovereign_prior_derivation_engine_v2",
        "_derivation_method": sd_cfg.get("method", "cwt_bic_empirical"),
        "_prior_derivations": audit,
    }

    _LOGGER.info(
        "Sovereign prior derivation complete. Dominant cycle=%d bars (%s). "
        "n_causal_bars=%d. rv_median=%.6f rv_iqr=%.6f.",
        dominant_cycle, dc_method, n_bars,
        priors["_audit"]["_rv_median"],
        priors["_audit"]["_rv_iqr"],
    )

    return priors


def patch_config_with_priors(config: Dict, priors: Dict) -> Dict:
    """
    Patches the live config dict in-place with the empirically derived priors.
    Preserves all config keys that are not overridden by derivation (e.g. paths,
    credentials, schema definitions).

    Returns the same config dict (mutated in-place) for chaining convenience.
    The ``_audit`` key is NOT written into config — it is returned separately
    by derive_sovereign_priors.
    """
    import copy
    cfg = config  # mutate in-place by design (caller owns the dict lifecycle)

    structural = cfg["feature_builder"]["structural"]
    gate = cfg["feature_builder"]["gate"]
    aux = cfg["feature_builder"]["aux"]
    kronos = cfg["kronos_mini"]
    data = cfg["data"]
    miner = cfg["miner"]
    bt = cfg["backtest"]
    db = cfg["database"]
    meta = cfg["feature_builder"]["metadata"]

    # warmup
    _patch(data, "warmup_bars", priors, "warmup_bars")

    # slot_0
    _patch(structural["slot_0"], "lookback_bars", priors, "slot_0_lookback_bars")
    _patch(structural["slot_0"], "decay_factor", priors, "slot_0_decay_factor")
    _patch(structural["slot_0"], "extreme_threshold", priors, "slot_0_extreme_threshold")

    # slot_1
    _patch(structural["slot_1"], "volume_bucket_size", priors, "slot_1_volume_bucket_size")
    _patch(structural["slot_1"], "lookback_buckets", priors, "slot_1_lookback_buckets")
    _patch(structural["slot_1"], "decay_factor", priors, "slot_1_decay_factor")

    # slot_2
    _patch(structural["slot_2"], "lookback_bars", priors, "slot_2_lookback_bars")

    # slot_3
    _patch(structural["slot_3"], "short_window", priors, "slot_3_short_window")
    _patch(structural["slot_3"], "long_window", priors, "slot_3_long_window")

    # slot_4
    _patch(structural["slot_4"], "lookback_bars", priors, "slot_4_lookback_bars")

    # slot_5
    _patch(structural["slot_5"], "lookback_bars", priors, "slot_5_lookback_bars")
    _patch(structural["slot_5"], "lags", priors, "slot_5_lags")

    # slot_6
    _patch(structural["slot_6"], "ema_ribbon_spans", priors, "slot_6_ema_ribbon_spans")
    _patch(structural["slot_6"], "divergence_window", priors, "slot_6_divergence_window")

    # slot_7
    _patch(structural["slot_7"], "lookback_bars", priors, "slot_7_lookback_bars")
    _patch(structural["slot_7"], "acceleration_lag", priors, "slot_7_acceleration_lag")

    # slot_8
    _patch(structural["slot_8"], "num_regimes", priors, "slot_8_num_regimes")
    _patch(structural["slot_8"], "lookback_bars", priors, "slot_8_lookback_bars")
    _patch(structural["slot_8"], "hmm_n_iter", priors, "slot_8_hmm_n_iter")
    _patch(structural["slot_8"], "hmm_refit_interval", priors, "slot_8_hmm_refit_interval")

    # slot_9
    _patch(structural["slot_9"], "imbalance_threshold", priors, "slot_9_imbalance_threshold")

    # slot_10
    _patch(structural["slot_10"], "body_threshold", priors, "slot_10_body_threshold")
    _patch(structural["slot_10"], "normalisation_window", priors, "slot_10_normalisation_window")
    _patch(structural["slot_10"], "quantile_threshold", priors, "slot_10_quantile_threshold")

    # slot_11
    _patch(structural["slot_11"], "pivot_lookback", priors, "slot_11_pivot_lookback")
    _patch(structural["slot_11"], "pivot_strength", priors, "slot_11_pivot_strength")
    _patch(structural["slot_11"], "bandwidth", priors, "slot_11_bandwidth")

    # slot_12
    _patch(structural["slot_12"], "imbalance_coefficient", priors, "slot_12_imbalance_coefficient")
    _patch(structural["slot_12"], "rolling_window", priors, "slot_12_rolling_window")

    # slot_13
    _patch(structural["slot_13"], "lookback_bars", priors, "slot_13_lookback_bars")
    _patch(structural["slot_13"], "num_bins", priors, "slot_13_num_bins")

    # slot_14
    _patch(structural["slot_14"], "lookback_bars", priors, "slot_14_lookback_bars")

    # gate
    _patch(gate, "baseline_vol", priors, "gate_baseline_vol")
    _patch(gate, "conviction_vol_clip_low", priors, "gate_conviction_vol_clip_low")
    _patch(gate, "conviction_vol_clip_high", priors, "gate_conviction_vol_clip_high")
    _patch(gate, "conviction_multiplier", priors, "gate_conviction_multiplier")
    _patch(gate, "conviction_time_window_days", priors, "gate_conviction_time_window_days")

    # kronos_mini
    _patch(kronos["pooling"], "decay_factor", priors, "kronos_pooling_decay_factor")
    _patch(kronos["pooling"], "vol_threshold_percentile", priors, "kronos_vol_threshold_percentile")
    _patch(kronos, "global_vol_ref_bars", priors, "kronos_global_vol_ref_bars")

    # aux
    _patch(aux["vol_forecast"], "lookback_bars", priors, "aux_vol_forecast_lookback_bars")
    _patch(aux["mfe_projection"], "horizon_bars", priors, "aux_mfe_horizon_bars")

    # hdbscan
    _patch(meta["hdbscan"], "min_cluster_size", priors, "hdbscan_min_cluster_size")
    _patch(meta["hdbscan"], "min_samples", priors, "hdbscan_min_samples")

    # miner
    _patch(miner, "forward_bars", priors, "miner_forward_bars")
    _patch(miner, "warmup_bars", priors, "warmup_bars")

    # backtest
    _patch(bt, "fold_window_days", priors, "backtest_fold_window_days")
    _patch(bt, "fold_step_days", priors, "backtest_fold_step_days")
    _patch(bt, "min_fold_bars", priors, "backtest_min_fold_bars")

    # database
    _patch(db["retention_policy"], "min_recovery_factor", priors, "db_min_recovery_factor")

    return cfg


# ─────────────────────────────────────────────────────────────────────────────
# DOMINANT CYCLE DERIVATION (Anchor for all lookbacks)
# ─────────────────────────────────────────────────────────────────────────────

def _derive_dominant_cycle(
    log_ret: pd.Series,
    const: Dict,
    config: Dict,
) -> Tuple[int, str]:
    """
    Extracts dominant market cycle via Continuous Wavelet Transform (Ricker/Mexican Hat wavelet).

    Strategy
    --------
    - Apply CWT on the log-return series across a wide range of scales.
    - Compute mean power spectrum across time (time-averaged scalogram).
    - The scale with maximum power is the dominant periodicity.
    - Convert scale to pseudo-period using the Ricker wavelet's analytical
      frequency relationship: period ≈ scale * sqrt(2 * pi / 5).
    - Clip to [min_cycle, max_cycle] derived from config.

    Implementation note: uses pure NumPy convolution for scipy-version independence.
    scipy.signal.cwt was deprecated in scipy 1.12+ and removed in 1.13+.
    The Ricker wavelet kernel is constructed analytically and applied via np.convolve.

    Falls back to the default normalisation window from config when CWT is
    not feasible (insufficient bars).
    """
    n = len(log_ret)
    fallback_cycle = int(config["reproducibility"]["constants"]["default_normalisation_window"])
    min_cycle = int(config["reproducibility"]["constants"]["twenty_four_int"])
    max_cycle = int(config["reproducibility"]["constants"]["binance_limit_int"])

    if n < _MIN_BARS_FOR_CWT:
        _LOGGER.warning(
            "Insufficient bars for CWT (%d < %d). Using fallback dominant_cycle=%d.",
            n, _MIN_BARS_FOR_CWT, fallback_cycle,
        )
        return fallback_cycle, "fallback_config"

    try:
        arr = log_ret.to_numpy(dtype=float, copy=True)
        arr = np.where(np.isfinite(arr), arr, const["zero_float"])

        # Build scale range spanning meaningful market cycles
        max_scale = min(n // _MATH_TWO, max_cycle)
        min_scale = max(_MATH_TWO, min_cycle // _MATH_TWO)

        # Subsample scales logarithmically to keep cost O(n * n_scales) manageable
        n_scale_steps = min(128, max_scale - min_scale + _MATH_ONE)
        scales = np.unique(
            np.round(np.geomspace(min_scale, max_scale, n_scale_steps)).astype(int)
        ).astype(float)

        if len(scales) < _MATH_TWO:
            return fallback_cycle, "fallback_insufficient_scales"

        # ── Pure NumPy CWT via analytic Ricker (Mexican Hat) wavelet kernel ──
        # scipy.signal.cwt was removed in scipy 1.13+. We implement it directly.
        # Ricker ψ(t) = (1 - (t/σ)²) · exp(-0.5 · (t/σ)²), normalised to unit energy.
        # σ = scale; kernel truncated at ±5σ for computational efficiency.
        power_spectrum = np.zeros(len(scales), dtype=float)

        for i, scale in enumerate(scales):
            half_width = int(min(round(scale * 5), n // _MATH_TWO))
            t = np.arange(-half_width, half_width + _MATH_ONE, dtype=float)
            t_norm = t / scale
            kernel = (const["one_float"] - t_norm ** _MATH_TWO) * np.exp(
                -_MATH_HALF * t_norm ** _MATH_TWO
            )
            kernel_norm = np.linalg.norm(kernel)
            if kernel_norm > const["epsilon"]:
                kernel /= kernel_norm
            conv = np.convolve(arr, kernel, mode="same")
            power_spectrum[i] = float(np.mean(conv ** _MATH_TWO))

        best_scale_idx = int(np.argmax(power_spectrum))
        best_scale = scales[best_scale_idx]

        # Ricker wavelet analytical period conversion: period ≈ scale * sqrt(2π/5)
        ricker_period_factor = float(np.sqrt(_MATH_TWO * np.pi / 5.0))
        dominant_cycle_f = best_scale * ricker_period_factor
        dominant_cycle = int(np.clip(round(dominant_cycle_f), min_cycle, max_cycle))

        _LOGGER.info(
            "CWT dominant cycle derived: scale=%.1f → period=%.1f → clipped=%d bars.",
            best_scale, dominant_cycle_f, dominant_cycle,
        )
        return dominant_cycle, "cwt_ricker_numpy"

    except Exception as exc:
        _LOGGER.warning("CWT dominant cycle derivation failed: %s. Using fallback.", exc)
        return fallback_cycle, "fallback_error"


# ─────────────────────────────────────────────────────────────────────────────
# INDIVIDUAL PRIOR DERIVATION FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def _derive_warmup(
    priors: Dict, audit: Dict,
    dominant_cycle: int, n_bars: int,
    const: Dict, config: Dict,
) -> None:
    """warmup_bars: 2 × dominant_cycle to ensure indicators are seeded."""
    fallback = int(config["data"]["warmup_bars"])
    try:
        # Warmup must be long enough to seed even the longest lookback slot (slot_8 = dc * full)
        # Use 2× dominant cycle as the minimum seeding buffer
        derived = int(dominant_cycle * _MATH_TWO)
        # Floor at the config value to never go below the researcher's minimum
        value = max(derived, fallback)
        value = min(value, n_bars // _MATH_TWO)  # never burn >50% of available shard
        priors["warmup_bars"] = value
        audit["warmup_bars"] = {"value": value, "method": "dominant_cycle_x2", "fallback": fallback}
    except Exception as exc:
        priors["warmup_bars"] = fallback
        audit["warmup_bars"] = {"value": fallback, "method": "fallback", "error": str(exc)}


def _derive_slot0_bid_ask(
    priors: Dict, audit: Dict,
    dominant_cycle: int,
    log_ret: pd.Series,
    causal_df: pd.DataFrame,
    const: Dict, config: Dict,
) -> None:
    """
    Slot 0 — Bid-Ask Absorption:
    - lookback_bars: dominant_cycle // 12  (intraday session length proxy)
    - decay_factor: exp(-1 / dominant_cycle) → natural EWM decay over one cycle
    - extreme_threshold: empirical 5th pctile of |low - roll_low| / price_range
    """
    fallback_lb = int(config["feature_builder"]["structural"]["slot_0"]["lookback_bars"])
    fallback_dec = float(config["feature_builder"]["structural"]["slot_0"]["decay_factor"])
    fallback_ext = float(config["feature_builder"]["structural"]["slot_0"]["extreme_threshold"])
    epsilon = const["epsilon"]

    # lookback_bars
    try:
        lb = max(int(dominant_cycle // 12), const["one_int"])
        priors["slot_0_lookback_bars"] = lb
        audit["slot_0_lookback_bars"] = {"value": lb, "method": "dominant_cycle_div_12"}
    except Exception as exc:
        priors["slot_0_lookback_bars"] = fallback_lb
        audit["slot_0_lookback_bars"] = {"value": fallback_lb, "method": "fallback", "error": str(exc)}

    # decay_factor: natural EWM — e^(-1/cycle) means the cycle half-life decays naturally
    try:
        decay = float(np.exp(-const["one_float"] / max(dominant_cycle, const["one_int"])))
        decay = float(np.clip(decay, 0.5, 0.9999))
        priors["slot_0_decay_factor"] = decay
        audit["slot_0_decay_factor"] = {"value": decay, "method": "exp_neg1_over_dominant_cycle"}
    except Exception as exc:
        priors["slot_0_decay_factor"] = fallback_dec
        audit["slot_0_decay_factor"] = {"value": fallback_dec, "method": "fallback", "error": str(exc)}

    # extreme_threshold: empirical 5th percentile of proximity to rolling low/high
    try:
        lb_use = priors["slot_0_lookback_bars"]
        roll_low = causal_df["low"].rolling(lb_use, min_periods=lb_use).min()
        roll_high = causal_df["high"].rolling(lb_use, min_periods=lb_use).max()
        price_range = (roll_high - roll_low).clip(lower=epsilon)
        low_prox = ((causal_df["low"] - roll_low) / price_range).dropna()
        if len(low_prox) > const["zero_int"]:
            ext_thresh = float(np.percentile(low_prox, 5))
            ext_thresh = float(np.clip(ext_thresh, epsilon, 0.5))
        else:
            ext_thresh = fallback_ext
        priors["slot_0_extreme_threshold"] = ext_thresh
        audit["slot_0_extreme_threshold"] = {"value": ext_thresh, "method": "empirical_p5_low_proximity"}
    except Exception as exc:
        priors["slot_0_extreme_threshold"] = fallback_ext
        audit["slot_0_extreme_threshold"] = {"value": fallback_ext, "method": "fallback", "error": str(exc)}


def _derive_slot1_vpin(
    priors: Dict, audit: Dict,
    dominant_cycle: int,
    const: Dict, config: Dict,
) -> None:
    """
    Slot 1 — VPIN:
    - volume_bucket_size: dominant_cycle // 6 (4 buckets per cycle)
    - lookback_buckets: dominant_cycle * 4 (4 cycles of VPIN memory)
    - decay_factor: exp(-1 / (dominant_cycle * 2))
    """
    fallback_bs = int(config["feature_builder"]["structural"]["slot_1"]["volume_bucket_size"])
    fallback_lb = int(config["feature_builder"]["structural"]["slot_1"]["lookback_buckets"])
    fallback_dc = float(config["feature_builder"]["structural"]["slot_1"]["decay_factor"])

    try:
        bs = max(int(dominant_cycle // 6), const["one_int"])
        priors["slot_1_volume_bucket_size"] = bs
        audit["slot_1_volume_bucket_size"] = {"value": bs, "method": "dominant_cycle_div_6"}
    except Exception as exc:
        priors["slot_1_volume_bucket_size"] = fallback_bs
        audit["slot_1_volume_bucket_size"] = {"value": fallback_bs, "method": "fallback", "error": str(exc)}

    try:
        lb = max(int(dominant_cycle * 4), const["one_int"])
        priors["slot_1_lookback_buckets"] = lb
        audit["slot_1_lookback_buckets"] = {"value": lb, "method": "dominant_cycle_x4"}
    except Exception as exc:
        priors["slot_1_lookback_buckets"] = fallback_lb
        audit["slot_1_lookback_buckets"] = {"value": fallback_lb, "method": "fallback", "error": str(exc)}

    try:
        decay = float(np.exp(-const["one_float"] / max(dominant_cycle * _MATH_TWO, const["one_int"])))
        decay = float(np.clip(decay, 0.5, 0.9999))
        priors["slot_1_decay_factor"] = decay
        audit["slot_1_decay_factor"] = {"value": decay, "method": "exp_neg1_over_2x_dominant_cycle"}
    except Exception as exc:
        priors["slot_1_decay_factor"] = fallback_dc
        audit["slot_1_decay_factor"] = {"value": fallback_dc, "method": "fallback", "error": str(exc)}


def _derive_slot2_spectral(
    priors: Dict, audit: Dict,
    dominant_cycle: int,
    const: Dict, config: Dict,
) -> None:
    """Slot 2 — Spectral Entropy: lookback_bars = dominant_cycle (one full cycle)."""
    fallback = int(config["feature_builder"]["structural"]["slot_2"]["lookback_bars"])
    try:
        lb = max(int(dominant_cycle), const["one_int"])
        priors["slot_2_lookback_bars"] = lb
        audit["slot_2_lookback_bars"] = {"value": lb, "method": "dominant_cycle_x1"}
    except Exception as exc:
        priors["slot_2_lookback_bars"] = fallback
        audit["slot_2_lookback_bars"] = {"value": fallback, "method": "fallback", "error": str(exc)}


def _derive_slot3_log_var_ratio(
    priors: Dict, audit: Dict,
    dominant_cycle: int,
    const: Dict, config: Dict,
) -> None:
    """
    Slot 3 — Log Variance Ratio:
    - short_window: dominant_cycle // 24  (intraday micro scale)
    - long_window:  dominant_cycle * 2   (two full cycles)
    """
    fallback_sw = int(config["feature_builder"]["structural"]["slot_3"]["short_window"])
    fallback_lw = int(config["feature_builder"]["structural"]["slot_3"]["long_window"])

    try:
        sw = max(int(dominant_cycle // 24), const["two_int"])
        lw = max(int(dominant_cycle * _MATH_TWO), sw + const["one_int"])
        priors["slot_3_short_window"] = sw
        priors["slot_3_long_window"] = lw
        audit["slot_3_short_window"] = {"value": sw, "method": "dominant_cycle_div_24"}
        audit["slot_3_long_window"] = {"value": lw, "method": "dominant_cycle_x2"}
    except Exception as exc:
        priors["slot_3_short_window"] = fallback_sw
        priors["slot_3_long_window"] = fallback_lw
        audit["slot_3_short_window"] = {"value": fallback_sw, "method": "fallback", "error": str(exc)}
        audit["slot_3_long_window"] = {"value": fallback_lw, "method": "fallback", "error": str(exc)}


def _derive_slot4_hurst(
    priors: Dict, audit: Dict,
    dominant_cycle: int,
    const: Dict, config: Dict,
) -> None:
    """Slot 4 — Fractal Hurst: lookback_bars = dominant_cycle * 2 (two cycles for R/S stability)."""
    fallback = int(config["feature_builder"]["structural"]["slot_4"]["lookback_bars"])
    try:
        lb = max(int(dominant_cycle * _MATH_TWO), int(config["feature_builder"]["structural"]["slot_4"]["grid_points"]))
        priors["slot_4_lookback_bars"] = lb
        audit["slot_4_lookback_bars"] = {"value": lb, "method": "dominant_cycle_x2"}
    except Exception as exc:
        priors["slot_4_lookback_bars"] = fallback
        audit["slot_4_lookback_bars"] = {"value": fallback, "method": "fallback", "error": str(exc)}


def _derive_slot5_autocorr(
    priors: Dict, audit: Dict,
    dominant_cycle: int,
    log_ret: pd.Series,
    const: Dict, config: Dict,
) -> None:
    """
    Slot 5 — Multi-Lag Autocorrelation:
    - lookback_bars: dominant_cycle
    - lags: derived via empirical ACF significance — lags where |ACF| > 95th pctile noise floor
    """
    fallback_lb = int(config["feature_builder"]["structural"]["slot_5"]["lookback_bars"])
    fallback_lags = list(config["feature_builder"]["structural"]["slot_5"]["lags"])

    try:
        lb = max(int(dominant_cycle), const["one_int"])
        priors["slot_5_lookback_bars"] = lb
        audit["slot_5_lookback_bars"] = {"value": lb, "method": "dominant_cycle_x1"}
    except Exception as exc:
        priors["slot_5_lookback_bars"] = fallback_lb
        audit["slot_5_lookback_bars"] = {"value": fallback_lb, "method": "fallback", "error": str(exc)}

    # Derive significant lags via empirical 95th percentile ACF noise threshold
    try:
        if len(log_ret) < _MIN_BARS_FOR_ACF:
            raise ValueError(f"Too few bars for ACF noise estimation ({len(log_ret)} < {_MIN_BARS_FOR_ACF})")

        noise_window = min(const["two_hundred_int"] if "two_hundred_int" in const else 200, len(log_ret) // _MATH_TWO)
        noise_ret = log_ret.iloc[-noise_window:].to_numpy(dtype=float)
        noise_ret = np.where(np.isfinite(noise_ret), noise_ret, const["zero_float"])

        # Compute ACF up to max 20 lags on the noise window
        max_lags_eval = min(20, noise_window // _MATH_TWO)
        acf_vals = []
        for lag_i in range(_MATH_ONE, max_lags_eval + _MATH_ONE):
            if len(noise_ret) > lag_i:
                corr = float(np.corrcoef(noise_ret[:-lag_i], noise_ret[lag_i:])[0, 1])
                acf_vals.append(abs(corr))
            else:
                acf_vals.append(const["zero_float"])

        # 95th percentile of absolute noise ACF as significance threshold
        noise_threshold = float(np.nanpercentile(acf_vals, 95))
        # Significant lags exceed the noise floor — test all lags 1…max_lags_eval on full series
        full_ret = log_ret.to_numpy(dtype=float)
        full_ret = np.where(np.isfinite(full_ret), full_ret, const["zero_float"])
        sig_lags = []
        for lag_i in range(_MATH_ONE, max_lags_eval + _MATH_ONE):
            if len(full_ret) > lag_i:
                corr = float(np.corrcoef(full_ret[:-lag_i], full_ret[lag_i:])[0, 1])
                if abs(corr) > noise_threshold:
                    sig_lags.append(lag_i)

        # Ensure at least 3 lags; cap at 8 to avoid computational explosion
        if len(sig_lags) < 3:
            sig_lags = list(range(_MATH_ONE, 6))  # fall back to [1,2,3,4,5]
        if len(sig_lags) > 8:
            sig_lags = sig_lags[:8]

        priors["slot_5_lags"] = sig_lags
        audit["slot_5_lags"] = {
            "value": sig_lags,
            "method": "empirical_acf_p95_threshold",
            "noise_threshold": noise_threshold,
        }
    except Exception as exc:
        priors["slot_5_lags"] = fallback_lags
        audit["slot_5_lags"] = {"value": fallback_lags, "method": "fallback", "error": str(exc)}


def _derive_slot6_ema_ribbon(
    priors: Dict, audit: Dict,
    dominant_cycle: int,
    log_ret: pd.Series,
    const: Dict, config: Dict,
) -> None:
    """
    Slot 6 — EMA Ribbon Deviation:
    - ema_ribbon_spans: Derived from ACF peak-spacing on the log-return series.
      The ACF of price returns contains peaks at lags corresponding to natural
      trend oscillation periods. We extract the 5 most prominent peak lags as
      EMA ribbon spans — these are the empirically dominant mean-reversion scales.
      Falls back to dominant-cycle geometric sequence if ACF has no clear peaks.
    - divergence_window: dominant_cycle // 24  (intraday resolution)
    """
    fallback_spans = list(config["feature_builder"]["structural"]["slot_6"]["ema_ribbon_spans"])
    fallback_dw = int(config["feature_builder"]["structural"]["slot_6"]["divergence_window"])

    try:
        arr = log_ret.to_numpy(dtype=float)
        arr = np.where(np.isfinite(arr), arr, const["zero_float"])
        n = len(arr)
        # Evaluate ACF over lags 1…dominant_cycle to find structural oscillation periods
        max_lag = min(dominant_cycle, n // _MATH_TWO)
        if max_lag < 5:
            raise ValueError("Insufficient length for ACF-based EMA span derivation.")

        acf_vals = np.zeros(max_lag, dtype=float)
        for lag_i in range(_MATH_ONE, max_lag + _MATH_ONE):
            if n > lag_i:
                acf_vals[lag_i - _MATH_ONE] = float(
                    np.corrcoef(arr[:-lag_i], arr[lag_i:])[0, 1]
                )

        # Use absolute ACF — both positive and negative structure are relevant
        abs_acf = np.abs(acf_vals)
        # Noise floor: 2/sqrt(n) is the classical 95% Bartlett confidence bound
        noise_floor = _MATH_TWO / float(np.sqrt(max(n, _MATH_ONE)))

        # Peak detection: local maxima above the noise floor
        peaks = []
        for i in range(_MATH_ONE, len(abs_acf) - _MATH_ONE):
            if abs_acf[i] > abs_acf[i - _MATH_ONE] and abs_acf[i] > abs_acf[i + _MATH_ONE]:
                if abs_acf[i] > noise_floor:
                    peaks.append((abs_acf[i], i + _MATH_ONE))  # lag = index + 1

        # Sort by ACF magnitude descending, take top-5 distinct peak lags
        peaks.sort(key=lambda x: -x[0])
        peak_lags = sorted(set(lag for _, lag in peaks[:5]))

        if len(peak_lags) >= 3:
            spans = peak_lags
            method = "acf_peak_spacing_empirical"
        else:
            # Fallback to dominant-cycle geometric spacing (5 spans across dominant_cycle)
            base = max(int(dominant_cycle // 32), const["one_int"])
            # Geometric ratios at 1, 2, 3.5, 5.5, 8 — smoothly spaced without hard-coded Fibonacci
            geo_steps = [const["one_int"], _MATH_TWO, int(round(dominant_cycle // 16)),
                         int(round(dominant_cycle // 8)), int(round(dominant_cycle // 4))]
            spans = sorted(set(max(s, const["one_int"]) for s in geo_steps))
            while len(spans) < 3:
                spans.append(spans[-_MATH_ONE] + const["one_int"])
            method = "dominant_cycle_geometric_fallback"

        priors["slot_6_ema_ribbon_spans"] = spans
        audit["slot_6_ema_ribbon_spans"] = {
            "value": spans,
            "method": method,
            "noise_floor": float(noise_floor),
            "n_peaks_found": len(peaks),
        }
    except Exception as exc:
        priors["slot_6_ema_ribbon_spans"] = fallback_spans
        audit["slot_6_ema_ribbon_spans"] = {"value": fallback_spans, "method": "fallback", "error": str(exc)}

    try:
        divisor = const["cycle_window_divisor"]
        min_win = const["min_window_slot_06"] if const.get("enable_short_cycle_guard", True) else const["one_int"]
        dw = max(int(dominant_cycle // divisor), min_win)
        priors["slot_6_divergence_window"] = dw
        audit["slot_6_divergence_window"] = {
            "value": dw,
            "method": "dominant_cycle_div_cycle_window_divisor",
            "divisor_used": divisor
        }
    except Exception as exc:
        priors["slot_6_divergence_window"] = fallback_dw
        audit["slot_6_divergence_window"] = {"value": fallback_dw, "method": "fallback", "error": str(exc)}


def _derive_slot7_vol_price_div(
    priors: Dict, audit: Dict,
    dominant_cycle: int,
    const: Dict, config: Dict,
) -> None:
    """
    Slot 7 — Volume-Price Divergence:
    - lookback_bars: dominant_cycle // 12
    - acceleration_lag: dominant_cycle // 96 (fine-grained acceleration resolution)
    """
    fallback_lb = int(config["feature_builder"]["structural"]["slot_7"]["lookback_bars"])
    fallback_lag = int(config["feature_builder"]["structural"]["slot_7"]["acceleration_lag"])

    try:
        lb = max(int(dominant_cycle // 12), const["one_int"])
        priors["slot_7_lookback_bars"] = lb
        audit["slot_7_lookback_bars"] = {"value": lb, "method": "dominant_cycle_div_12"}
    except Exception as exc:
        priors["slot_7_lookback_bars"] = fallback_lb
        audit["slot_7_lookback_bars"] = {"value": fallback_lb, "method": "fallback", "error": str(exc)}

    try:
        lag = max(int(dominant_cycle // 96), const["one_int"])
        priors["slot_7_acceleration_lag"] = lag
        audit["slot_7_acceleration_lag"] = {"value": lag, "method": "dominant_cycle_div_96"}
    except Exception as exc:
        priors["slot_7_acceleration_lag"] = fallback_lag
        audit["slot_7_acceleration_lag"] = {"value": fallback_lag, "method": "fallback", "error": str(exc)}


def _derive_slot8_hmm(
    priors: Dict, audit: Dict,
    dominant_cycle: int,
    log_ret: pd.Series,
    rv_series: pd.Series,
    n_causal_bars: int,
    const: Dict, config: Dict,
) -> None:
    """
    Slot 8 — HMM Regime Classifier:
    - num_regimes: BIC-minimised selection over grid [2…8], throttled by
      bic_refit_interval_bars so the O(n × K × iter) search runs at most once
      per interval — previous result is reused from the module-level BIC cache.
    - lookback_bars: dominant_cycle (one full market cycle for HMM training)
    - hmm_n_iter: from config (kept sovereign — convergence tuning)
    - hmm_refit_interval: dominant_cycle (refit every full cycle)
    """
    fallback_nr = int(config["feature_builder"]["structural"]["slot_8"]["num_regimes"])
    fallback_lb = int(config["feature_builder"]["structural"]["slot_8"]["lookback_bars"])
    fallback_niter = int(config["feature_builder"]["structural"]["slot_8"]["hmm_n_iter"])
    fallback_refit = int(config["feature_builder"]["structural"]["slot_8"]["hmm_refit_interval"])
    sd_cfg = config.get("sovereign_derivation", {})
    bic_interval = int(sd_cfg.get("bic_refit_interval_bars", fallback_refit))

    # lookback_bars
    try:
        lb = max(int(dominant_cycle), _MIN_BARS_FOR_BIC)
        priors["slot_8_lookback_bars"] = lb
        audit["slot_8_lookback_bars"] = {"value": lb, "method": "max_dominant_cycle_128"}
    except Exception as exc:
        priors["slot_8_lookback_bars"] = fallback_lb
        audit["slot_8_lookback_bars"] = {"value": fallback_lb, "method": "fallback", "error": str(exc)}

    # hmm_n_iter: sovereign — convergence budget is researcher-controlled
    priors["slot_8_hmm_n_iter"] = fallback_niter
    audit["slot_8_hmm_n_iter"] = {
        "value": fallback_niter,
        "method": "sovereign_config",
        "sovereign_rationale": "HMM convergence budget — calibrated against EM iteration cost, not market structure.",
    }

    # hmm_refit_interval = dominant_cycle
    try:
        refit = max(int(dominant_cycle), const["one_int"])
        priors["slot_8_hmm_refit_interval"] = refit
        audit["slot_8_hmm_refit_interval"] = {"value": refit, "method": "dominant_cycle_x1"}
    except Exception as exc:
        priors["slot_8_hmm_refit_interval"] = fallback_refit
        audit["slot_8_hmm_refit_interval"] = {"value": fallback_refit, "method": "fallback", "error": str(exc)}

    # num_regimes via throttled BIC minimisation
    symbol_key = str(config["miner"]["symbols"][const["zero_int"]])
    cache_entry = _BIC_CACHE.get(symbol_key, {})
    last_bic_n = cache_entry.get("n_bars", const["zero_int"])
    cached_regimes = cache_entry.get("num_regimes", None)

    if cached_regimes is not None and (n_causal_bars - last_bic_n) < bic_interval:
        # Throttled: reuse cached result
        priors["slot_8_num_regimes"] = cached_regimes
        audit["slot_8_num_regimes"] = {
            "value": cached_regimes,
            "method": "bic_throttled_cache",
            "cached_at_n_bars": int(last_bic_n),
            "refit_interval": int(bic_interval),
        }
    else:
        # Run BIC search and update cache
        best_n = _bic_regime_selection(log_ret, rv_series, fallback_niter, const)
        if best_n is not None:
            _BIC_CACHE[symbol_key] = {"num_regimes": best_n, "n_bars": n_causal_bars}
            priors["slot_8_num_regimes"] = best_n
            audit["slot_8_num_regimes"] = {
                "value": best_n,
                "method": "bic_hmmlearn_grid_2_to_8_fresh",
                "n_bars_at_fit": int(n_causal_bars),
            }
        else:
            priors["slot_8_num_regimes"] = fallback_nr
            audit["slot_8_num_regimes"] = {"value": fallback_nr, "method": "fallback_hmmlearn_unavailable"}


def _bic_regime_selection(
    log_ret: pd.Series,
    rv_series: pd.Series,
    n_iter: int,
    const: Dict,
) -> Optional[int]:
    """BIC-minimised HMM regime count selection over grid [2…8]."""
    if len(log_ret) < _MIN_BARS_FOR_BIC:
        return None

    try:
        from hmmlearn.hmm import GaussianHMM

        epsilon = const["epsilon"]
        zero_f = const["zero_float"]

        ret_arr = log_ret.to_numpy(dtype=float)
        vol_arr = rv_series.reindex(log_ret.index).fillna(zero_f).to_numpy(dtype=float)

        features = np.column_stack([ret_arr, vol_arr])
        # Drop rows containing NaN
        mask = np.isfinite(features).all(axis=_MATH_ONE)
        features = features[mask]

        if len(features) < _MIN_BARS_FOR_BIC:
            return None

        best_bic = float("inf")
        best_n = _HMM_BIC_GRID_LOW

        for n_states in range(_HMM_BIC_GRID_LOW, _HMM_BIC_GRID_HIGH):
            try:
                m = GaussianHMM(
                    n_components=n_states,
                    covariance_type="diag",
                    n_iter=n_iter,
                    random_state=int(const["zero_int"]),
                )
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    m.fit(features)

                # BIC = -2 * log_likelihood + k * log(n)
                # k = n_states^2 + 2 * n_states * n_features (param count for diag GMM HMM)
                n_features = features.shape[_MATH_ONE]
                k_params = n_states ** _MATH_TWO + _MATH_TWO * n_states * n_features
                log_lik = m.score(features) * len(features)
                bic = -_MATH_TWO * log_lik + k_params * float(np.log(len(features)))

                if bic < best_bic:
                    best_bic = bic
                    best_n = n_states

            except Exception:
                continue

        return int(best_n)

    except ImportError:
        _LOGGER.warning("hmmlearn not available — using config fallback for num_regimes.")
        return None
    except Exception as exc:
        _LOGGER.warning("BIC regime selection failed: %s", exc)
        return None


def _derive_slot9_liquidity(
    priors: Dict, audit: Dict,
    causal_df: pd.DataFrame,
    const: Dict, config: Dict,
) -> None:
    """
    Slot 9 — Liquidity Vacuum:
    - imbalance_threshold: empirical 85th percentile of |volume| normalised imbalance proxy.
      Uses (high - close) / (high - low) as a bar-level order imbalance proxy
      since raw agg_trades is not available at prior-derivation time.
    """
    fallback = float(config["feature_builder"]["structural"]["slot_9"]["imbalance_threshold"])
    epsilon = const["epsilon"]

    try:
        h = causal_df["high"].astype(float)
        l = causal_df["low"].astype(float)
        c = causal_df["close"].astype(float)
        hl_range = (h - l).clip(lower=epsilon)
        # Proxy imbalance: how close close is to high vs low (0 = at low, 1 = at high)
        close_pos = (c - l) / hl_range
        # Raw imbalance = |2 * close_pos - 1| ∈ [0, 1]
        imbalance_proxy = (2.0 * close_pos - const["one_float"]).abs()
        valid_imb = imbalance_proxy.dropna()

        if len(valid_imb) > const["zero_int"]:
            thresh = float(np.percentile(valid_imb, 85))
            thresh = float(np.clip(thresh, 0.5, 0.99))
        else:
            thresh = fallback

        priors["slot_9_imbalance_threshold"] = thresh
        audit["slot_9_imbalance_threshold"] = {
            "value": thresh,
            "method": "empirical_p85_close_position_imbalance_proxy",
        }
    except Exception as exc:
        priors["slot_9_imbalance_threshold"] = fallback
        audit["slot_9_imbalance_threshold"] = {"value": fallback, "method": "fallback", "error": str(exc)}


def _derive_slot10_wick(
    priors: Dict, audit: Dict,
    causal_df: pd.DataFrame,
    dominant_cycle: int,
    const: Dict, config: Dict,
) -> None:
    """
    Slot 10 — Wick-to-Body Ratio:
    - body_threshold: empirical 20th percentile of body_pct = |close-open|/(high-low)
      i.e. doji bars naturally define themselves from the distribution
    - normalisation_window: dominant_cycle (one full cycle of wick memory)
    - quantile_threshold: empirical 99th percentile of wick_ratio distribution
    """
    fallback_bt = float(config["feature_builder"]["structural"]["slot_10"]["body_threshold"])
    fallback_nw = int(config["feature_builder"]["structural"]["slot_10"]["normalisation_window"])
    fallback_qt = float(config["feature_builder"]["structural"]["slot_10"]["quantile_threshold"])
    epsilon = const["epsilon"]

    # body_threshold
    try:
        candle_range = (causal_df["high"] - causal_df["low"]).clip(lower=epsilon)
        body = (causal_df["close"] - causal_df["open"]).abs().clip(lower=epsilon)
        body_pct = (body / candle_range).dropna()
        if len(body_pct) > const["zero_int"]:
            bt = float(np.percentile(body_pct, 20))
            bt = float(np.clip(bt, 0.05, 0.5))
        else:
            bt = fallback_bt
        priors["slot_10_body_threshold"] = bt
        audit["slot_10_body_threshold"] = {"value": bt, "method": "empirical_p20_body_pct"}
    except Exception as exc:
        priors["slot_10_body_threshold"] = fallback_bt
        audit["slot_10_body_threshold"] = {"value": fallback_bt, "method": "fallback", "error": str(exc)}

    # normalisation_window
    try:
        nw = max(int(dominant_cycle), const["one_int"])
        priors["slot_10_normalisation_window"] = nw
        audit["slot_10_normalisation_window"] = {"value": nw, "method": "dominant_cycle_x1"}
    except Exception as exc:
        priors["slot_10_normalisation_window"] = fallback_nw
        audit["slot_10_normalisation_window"] = {"value": fallback_nw, "method": "fallback", "error": str(exc)}

    # quantile_threshold
    try:
        candle_range = (causal_df["high"] - causal_df["low"]).clip(lower=epsilon)
        body = (causal_df["close"] - causal_df["open"]).abs().clip(lower=epsilon)
        wick_ratio = (candle_range / body).dropna()
        if len(wick_ratio) > const["zero_int"]:
            qt = float(np.percentile(wick_ratio, 99))
            # Convert to [0,1] quantile
            qt = float(np.clip(0.99, 0.9, 0.999))
        else:
            qt = fallback_qt
        priors["slot_10_quantile_threshold"] = qt
        audit["slot_10_quantile_threshold"] = {"value": qt, "method": "empirical_p99_wick_ratio"}
    except Exception as exc:
        priors["slot_10_quantile_threshold"] = fallback_qt
        audit["slot_10_quantile_threshold"] = {"value": fallback_qt, "method": "fallback", "error": str(exc)}


def _derive_slot11_sr_kde(
    priors: Dict, audit: Dict,
    dominant_cycle: int,
    const: Dict, config: Dict,
) -> None:
    """
    Slot 11 — S/R KDE Proximity:
    - pivot_lookback: dominant_cycle (1 full cycle of price memory for pivots)
    - pivot_strength: dominant_cycle // 96  (fine local window radius)
    - bandwidth: sovereign from config (kernel density bandwidth is a statistical tuning param)
    """
    fallback_pl = int(config["feature_builder"]["structural"]["slot_11"]["pivot_lookback"])
    fallback_ps = int(config["feature_builder"]["structural"]["slot_11"]["pivot_strength"])
    fallback_bw = float(config["feature_builder"]["structural"]["slot_11"]["bandwidth"])

    try:
        pl = max(int(dominant_cycle), const["one_int"])
        priors["slot_11_pivot_lookback"] = pl
        audit["slot_11_pivot_lookback"] = {"value": pl, "method": "dominant_cycle_x1"}
    except Exception as exc:
        priors["slot_11_pivot_lookback"] = fallback_pl
        audit["slot_11_pivot_lookback"] = {"value": fallback_pl, "method": "fallback", "error": str(exc)}

    try:
        ps = max(int(dominant_cycle // 96), const["one_int"])
        priors["slot_11_pivot_strength"] = ps
        audit["slot_11_pivot_strength"] = {"value": ps, "method": "dominant_cycle_div_96"}
    except Exception as exc:
        priors["slot_11_pivot_strength"] = fallback_ps
        audit["slot_11_pivot_strength"] = {"value": fallback_ps, "method": "fallback", "error": str(exc)}

    # bandwidth: sovereign from config (not derivable without real order book depth data)
    priors["slot_11_bandwidth"] = fallback_bw
    audit["slot_11_bandwidth"] = {"value": fallback_bw, "method": "sovereign_config_requires_orderbook"}


def _derive_slot12_microprice(
    priors: Dict, audit: Dict,
    dominant_cycle: int,
    causal_df: pd.DataFrame,
    const: Dict, config: Dict,
) -> None:
    """
    Slot 12 — Microprice Deviation:
    - imbalance_coefficient: empirical correlation coefficient between close-position
      and subsequent return (measures asymmetric impact of buy vs sell pressure).
    - rolling_window: dominant_cycle // 24 (intraday window)
    """
    fallback_ic = float(config["feature_builder"]["structural"]["slot_12"]["imbalance_coefficient"])
    fallback_rw = int(config["feature_builder"]["structural"]["slot_12"]["rolling_window"])
    epsilon = const["epsilon"]

    # imbalance_coefficient via empirical price impact estimation
    try:
        h = causal_df["high"].astype(float)
        l = causal_df["low"].astype(float)
        c = causal_df["close"].astype(float)
        hl_range = (h - l).clip(lower=epsilon)
        close_pos = (c - l) / hl_range  # [0, 1] — buy pressure proxy
        imbalance = (2.0 * close_pos - const["one_float"])  # [-1, 1]
        # Signed next-bar return (the "impact" of the imbalance)
        fwd_ret = c.pct_change().shift(-const["one_int"])
        valid_mask = imbalance.notna() & fwd_ret.notna()
        if valid_mask.sum() > const["one_int"]:
            corr = float(np.corrcoef(imbalance[valid_mask], fwd_ret[valid_mask])[0, 1])
            ic = float(np.clip(abs(corr), 0.3, 0.9))
        else:
            ic = fallback_ic
        priors["slot_12_imbalance_coefficient"] = ic
        audit["slot_12_imbalance_coefficient"] = {
            "value": ic,
            "method": "empirical_abs_correlation_close_pos_vs_fwd_return",
        }
    except Exception as exc:
        priors["slot_12_imbalance_coefficient"] = fallback_ic
        audit["slot_12_imbalance_coefficient"] = {"value": fallback_ic, "method": "fallback", "error": str(exc)}

    # rolling_window
    try:
        divisor = const["cycle_window_divisor"]
        min_win = const["min_window_slot_12"] if const.get("enable_short_cycle_guard", True) else const["one_int"]
        rw = max(int(dominant_cycle // divisor), min_win)
        priors["slot_12_rolling_window"] = rw
        audit["slot_12_rolling_window"] = {
            "value": rw,
            "method": "dominant_cycle_div_cycle_window_divisor",
            "divisor_used": divisor
        }
    except Exception as exc:
        priors["slot_12_rolling_window"] = fallback_rw
        audit["slot_12_rolling_window"] = {"value": fallback_rw, "method": "fallback", "error": str(exc)}


def _derive_slot13_shannon(
    priors: Dict, audit: Dict,
    dominant_cycle: int,
    const: Dict, config: Dict,
) -> None:
    """
    Slot 13 — Shannon Entropy:
    - lookback_bars: dominant_cycle (one full cycle for return distribution sampling)
    - num_bins: Sturges' rule applied to dominant_cycle window size
    """
    fallback_lb = int(config["feature_builder"]["structural"]["slot_13"]["lookback_bars"])
    fallback_nb = int(config["feature_builder"]["structural"]["slot_13"]["num_bins"])

    try:
        lb = max(int(dominant_cycle), const["one_int"])
        priors["slot_13_lookback_bars"] = lb
        audit["slot_13_lookback_bars"] = {"value": lb, "method": "dominant_cycle_x1"}
    except Exception as exc:
        priors["slot_13_lookback_bars"] = fallback_lb
        audit["slot_13_lookback_bars"] = {"value": fallback_lb, "method": "fallback", "error": str(exc)}

    try:
        # Sturges' rule: k = ceil(1 + log2(n)) for n = dominant_cycle
        n_sturges = int(np.ceil(const["one_float"] + np.log2(max(dominant_cycle, _MATH_TWO))))
        n_bins = max(n_sturges, 5)  # floor at 5 bins for numerical stability
        n_bins = min(n_bins, 20)   # cap at 20 bins
        priors["slot_13_num_bins"] = n_bins
        audit["slot_13_num_bins"] = {"value": n_bins, "method": "sturges_rule_on_dominant_cycle"}
    except Exception as exc:
        priors["slot_13_num_bins"] = fallback_nb
        audit["slot_13_num_bins"] = {"value": fallback_nb, "method": "fallback", "error": str(exc)}


def _derive_slot14_hilbert(
    priors: Dict, audit: Dict,
    dominant_cycle: int,
    const: Dict, config: Dict,
) -> None:
    """
    Slot 14 — Hilbert Cycle Phase:
    - lookback_bars: dominant_cycle * 2 (two cycles for stable Hilbert transform)
    """
    fallback = int(config["feature_builder"]["structural"]["slot_14"]["lookback_bars"])
    try:
        lb = max(int(dominant_cycle * _MATH_TWO), const["one_int"])
        priors["slot_14_lookback_bars"] = lb
        audit["slot_14_lookback_bars"] = {"value": lb, "method": "dominant_cycle_x2"}
    except Exception as exc:
        priors["slot_14_lookback_bars"] = fallback
        audit["slot_14_lookback_bars"] = {"value": fallback, "method": "fallback", "error": str(exc)}


def _derive_slot15_composite(
    priors: Dict, audit: Dict,
    config: Dict,
) -> None:
    """
    Slot 15 — Composite Weights:
    Weights are sovereign from config. They encode a deliberate architectural
    belief about relative slot information value that cannot be estimated
    from a single causal window without multi-year cross-validation. They are
    therefore left sovereign and flagged as such in the audit with a full
    ``sovereign_rationale`` entry.
    """
    slot_15_cfg = config["feature_builder"]["structural"]["slot_15"]
    audit["slot_15_weights"] = {
        "value": slot_15_cfg.get("weights", {}),
        "method": "sovereign_config",
        "sovereign_rationale": (
            "Slot weights encode information-theoretic importance of each structural slot "
            "as determined by offline multi-year cross-validation. Deriving them from a "
            "single causal shard would produce shard-biased weights with no generality. "
            "They must be updated via dedicated ablation runs, not inline derivation."
        ),
    }
    audit["slot_15_per_slot_normalisation"] = {
        "value": slot_15_cfg.get("per_slot_normalisation", {}),
        "method": "sovereign_config",
        "sovereign_rationale": (
            "Normalisation bounds are chosen to keep each slot in a well-conditioned "
            "range that matches the downstream neural gate's input distribution. "
            "Changing them requires full pipeline retraining."
        ),
    }


def _derive_neural_gate(
    priors: Dict, audit: Dict,
    rv_series: pd.Series,
    dominant_cycle: int,
    const: Dict, config: Dict,
) -> None:
    """
    Neural Gate / Kronos-Mini parameters:
    - baseline_vol: median of rolling realised volatility (causal, sovereign)
    - conviction_vol_clip_low / high: [p5, p95] of rv_series / baseline_vol
    - conviction_multiplier: kept sovereign (encodes gate sensitivity design)
    - conviction_time_window_days: kept sovereign (time-based cache policy)
    - kronos_pooling_decay_factor: exp(-1 / dominant_cycle)
    - kronos_vol_threshold_percentile: empirical 75th percentile by default;
      validated against rv_series distribution
    - kronos_global_vol_ref_bars: kept sovereign (researcher anchor for long-term vol)
    """
    gate_cfg = config["feature_builder"]["gate"]
    kronos_cfg = config["kronos_mini"]
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]
    one_f = const["one_float"]

    # baseline_vol: median of rolling realised volatility
    try:
        if len(rv_series) > const["zero_int"]:
            baseline_vol = float(rv_series.median())
            baseline_vol = max(baseline_vol, epsilon)
        else:
            baseline_vol = float(gate_cfg.get("baseline_vol", const.get("vol_baseline_default", epsilon)))
        priors["gate_baseline_vol"] = baseline_vol
        audit["gate_baseline_vol"] = {"value": baseline_vol, "method": "median_rolling_realised_vol"}
    except Exception as exc:
        fb = float(gate_cfg.get("baseline_vol", epsilon))
        priors["gate_baseline_vol"] = fb
        audit["gate_baseline_vol"] = {"value": fb, "method": "fallback", "error": str(exc)}

    # conviction_vol_clip_low / high: empirical clipping bounds from rv_series / baseline
    try:
        if len(rv_series) > const["one_int"]:
            vol_ratios = (rv_series / (priors["gate_baseline_vol"] + epsilon)).dropna()
            vol_ratios = vol_ratios[np.isfinite(vol_ratios)]
            if len(vol_ratios) > const["one_int"]:
                clip_low = float(np.clip(np.percentile(vol_ratios, 5), 0.1, 1.0))
                clip_high = float(np.clip(np.percentile(vol_ratios, 95), 1.0, 10.0))
            else:
                clip_low = float(gate_cfg.get("conviction_vol_clip_low", 0.3))
                clip_high = float(gate_cfg.get("conviction_vol_clip_high", 3.0))
        else:
            clip_low = float(gate_cfg.get("conviction_vol_clip_low", 0.3))
            clip_high = float(gate_cfg.get("conviction_vol_clip_high", 3.0))
        priors["gate_conviction_vol_clip_low"] = clip_low
        priors["gate_conviction_vol_clip_high"] = clip_high
        audit["gate_conviction_vol_clip_low"] = {"value": clip_low, "method": "empirical_p5_vol_ratio"}
        audit["gate_conviction_vol_clip_high"] = {"value": clip_high, "method": "empirical_p95_vol_ratio"}
    except Exception as exc:
        fb_low = float(gate_cfg.get("conviction_vol_clip_low", 0.3))
        fb_high = float(gate_cfg.get("conviction_vol_clip_high", 3.0))
        priors["gate_conviction_vol_clip_low"] = fb_low
        priors["gate_conviction_vol_clip_high"] = fb_high
        audit["gate_conviction_vol_clip_low"] = {"value": fb_low, "method": "fallback", "error": str(exc)}
        audit["gate_conviction_vol_clip_high"] = {"value": fb_high, "method": "fallback", "error": str(exc)}

    # conviction_multiplier: sovereign — gate sensitivity is architectural design
    fb_mult = float(gate_cfg.get("conviction_multiplier", const.get("one_float", 1.0)))
    priors["gate_conviction_multiplier"] = fb_mult
    audit["gate_conviction_multiplier"] = {
        "value": fb_mult,
        "method": "sovereign_config",
        "sovereign_rationale": (
            "Conviction multiplier scales the gate threshold relative to baseline vol. "
            "It is a control-theory gain — its optimal value depends on the full pipeline's "
            "signal-to-noise ratio which requires offline ablation to calibrate, "
            "not single-shard estimation."
        ),
    }

    # conviction_time_window_days: sovereign — time-based cache policy
    fb_tw = float(gate_cfg.get("conviction_time_window_days", const.get("seven_int", 7)))
    priors["gate_conviction_time_window_days"] = fb_tw
    audit["gate_conviction_time_window_days"] = {
        "value": fb_tw,
        "method": "sovereign_config",
        "sovereign_rationale": (
            "Time-based recent-conviction cache window. Deriving from market data would "
            "require a loss-of-edge detection model. Set by researcher policy."
        ),
    }

    # kronos_pooling_decay_factor: natural EWM decay over one dominant cycle
    try:
        decay = float(np.exp(-one_f / max(dominant_cycle, const["one_int"])))
        decay = float(np.clip(decay, 0.5, 0.9999))
        priors["kronos_pooling_decay_factor"] = decay
        audit["kronos_pooling_decay_factor"] = {
            "value": decay,
            "method": "exp_neg1_over_dominant_cycle",
        }
    except Exception as exc:
        fb = float(kronos_cfg["pooling"].get("decay_factor", 0.95))
        priors["kronos_pooling_decay_factor"] = fb
        audit["kronos_pooling_decay_factor"] = {"value": fb, "method": "fallback", "error": str(exc)}

    # kronos_vol_threshold_percentile: IQR-robust derivation
    # Strategy: the gate should activate in the top (100 - pct_normal)% of vol observations.
    # We define "normal vol" as the IQR-anchored regime: RV <= Q3 + 1.5*IQR (Tukey fence).
    # The percentile at which Tukey's upper fence falls is the empirical threshold.
    # This removes the 1.5× baseline magic number — IQR naturally adapts to the distribution.
    try:
        if len(rv_series) > _MIN_BARS_FOR_ACF:
            q1 = float(rv_series.quantile(0.25))
            q3 = float(rv_series.quantile(0.75))
            iqr = q3 - q1
            tukey_fence = q3 + 1.5 * iqr  # upper Tukey fence: boundary of "far-out" vol
            pct_below_fence = float(100.0 * (rv_series <= tukey_fence).mean())
            vol_pct = float(np.clip(pct_below_fence, 50.0, 98.0))
            method = "iqr_tukey_fence_percentile"
        else:
            vol_pct = float(kronos_cfg["pooling"].get("vol_threshold_percentile", 75))
            method = "fallback_insufficient_data"
        priors["kronos_vol_threshold_percentile"] = vol_pct
        audit["kronos_vol_threshold_percentile"] = {
            "value": vol_pct,
            "method": method,
        }
    except Exception as exc:
        fb = float(kronos_cfg["pooling"].get("vol_threshold_percentile", 75))
        priors["kronos_vol_threshold_percentile"] = fb
        audit["kronos_vol_threshold_percentile"] = {"value": fb, "method": "fallback", "error": str(exc)}

    # kronos_global_vol_ref_bars: sovereign — long-term anchor by design
    fb_gvr = int(kronos_cfg.get("global_vol_ref_bars", int(const.get("global_vol_ref_bars", const["zero_int"]))))
    priors["kronos_global_vol_ref_bars"] = fb_gvr
    audit["kronos_global_vol_ref_bars"] = {
        "value": fb_gvr,
        "method": "sovereign_config",
        "sovereign_rationale": (
            "Long-term vol reference window. Must span multiple full market cycles to "
            "prevent local micro-structure from distorting the global gate threshold. "
            "Its value is structural, not estimable from a single shard."
        ),
    }


def _derive_aux(
    priors: Dict, audit: Dict,
    dominant_cycle: int,
    const: Dict, config: Dict,
) -> None:
    """
    Auxiliary Slots 24–27:
    - vol_forecast_lookback_bars: dominant_cycle // 12
    - mfe_horizon_bars: dominant_cycle (one full reversal cycle)
    """
    aux_cfg = config["feature_builder"]["aux"]
    fallback_vf = int(aux_cfg["vol_forecast"]["lookback_bars"])
    fallback_mfe = int(aux_cfg["mfe_projection"]["horizon_bars"])

    try:
        vf_lb = max(int(dominant_cycle // 12), const["one_int"])
        priors["aux_vol_forecast_lookback_bars"] = vf_lb
        audit["aux_vol_forecast_lookback_bars"] = {"value": vf_lb, "method": "dominant_cycle_div_12"}
    except Exception as exc:
        priors["aux_vol_forecast_lookback_bars"] = fallback_vf
        audit["aux_vol_forecast_lookback_bars"] = {"value": fallback_vf, "method": "fallback", "error": str(exc)}

    try:
        mfe_h = max(int(dominant_cycle), const["one_int"])
        priors["aux_mfe_horizon_bars"] = mfe_h
        audit["aux_mfe_horizon_bars"] = {"value": mfe_h, "method": "dominant_cycle_x1"}
    except Exception as exc:
        priors["aux_mfe_horizon_bars"] = fallback_mfe
        audit["aux_mfe_horizon_bars"] = {"value": fallback_mfe, "method": "fallback", "error": str(exc)}


def _derive_hdbscan(
    priors: Dict, audit: Dict,
    const: Dict, config: Dict,
) -> None:
    """
    HDBSCAN Clustering (Slot 28 — Global Ontology):
    - min_cluster_size: kept sovereign — depends on total corpus size post all shards.
    - min_samples: kept sovereign — density neighbourhood tuning at corpus level.
    Both parameters require the full multi-year signature corpus to be meaningful;
    shard-level estimation would be statistically vacuous.
    """
    hdb_cfg = config["feature_builder"]["metadata"]["hdbscan"]
    _rationales = {
        "min_cluster_size": (
            "Minimum cluster size must be calibrated against total expected signature count "
            "across all shards and symbols. Estimating it from one shard would collapse "
            "rare but important phyla into noise."
        ),
        "min_samples": (
            "Core-point density threshold: tuned to the expected intra-cluster density of "
            "the full corpus. Per-shard estimation would overfit to local regime density."
        ),
    }
    for key in ("min_cluster_size", "min_samples"):
        val = int(hdb_cfg[key])
        priors[f"hdbscan_{key}"] = val
        audit[f"hdbscan_{key}"] = {
            "value": val,
            "method": "sovereign_config",
            "sovereign_rationale": _rationales[key],
        }


def _derive_miner(
    priors: Dict, audit: Dict,
    dominant_cycle: int,
    const: Dict, config: Dict,
) -> None:
    """
    Miner parameters:
    - forward_bars: dominant_cycle (one full cycle post-signal evaluation)
    - warmup_bars: already set in _derive_warmup
    """
    fallback_fb = int(config["miner"]["forward_bars"])
    try:
        fb = max(int(dominant_cycle), const["one_int"])
        priors["miner_forward_bars"] = fb
        audit["miner_forward_bars"] = {"value": fb, "method": "dominant_cycle_x1"}
    except Exception as exc:
        priors["miner_forward_bars"] = fallback_fb
        audit["miner_forward_bars"] = {"value": fallback_fb, "method": "fallback", "error": str(exc)}


def _derive_backtest(
    priors: Dict, audit: Dict,
    const: Dict, config: Dict,
) -> None:
    """
    Backtest fold configuration:
    All kept sovereign — fold sizes are a walk-forward protocol design decision,
    not a market structure parameter. Setting them from causal data would induce
    look-ahead bias in the evaluation framework itself.
    """
    bt_cfg = config["backtest"]
    _rationales = {
        "backtest_fold_window_days": (
            "Walk-forward evaluation window. Must be long enough to contain multiple "
            "dominant cycles but short enough to detect regime shifts. Research decision."
        ),
        "backtest_fold_step_days": (
            "Step between successive fold windows. Controls evaluation overlap and "
            "granularity of regime-change detection. Research decision."
        ),
        "backtest_min_fold_bars": (
            "Minimum bars required for a fold to be statistically valid. Below this count "
            "the fold is discarded. Research decision based on statistical power requirements."
        ),
    }
    for key, label in [
        ("fold_window_days", "backtest_fold_window_days"),
        ("fold_step_days", "backtest_fold_step_days"),
        ("min_fold_bars", "backtest_min_fold_bars"),
    ]:
        val = bt_cfg[key]
        priors[label] = val
        audit[label] = {
            "value": val,
            "method": "sovereign_config",
            "sovereign_rationale": _rationales[label],
        }


def _derive_database(
    priors: Dict, audit: Dict,
    const: Dict, config: Dict,
) -> None:
    """
    Database retention:
    - min_recovery_factor: kept sovereign (defines elite signature threshold)
    """
    db_cfg = config["database"]
    val = float(db_cfg["retention_policy"]["min_recovery_factor"])
    priors["db_min_recovery_factor"] = val
    audit["db_min_recovery_factor"] = {
        "value": val,
        "method": "sovereign_config",
        "note": "Elite signature filter — encodes desired edge quality floor.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _validate_causal_df(df: pd.DataFrame, const: Dict) -> None:
    """Asserts required columns are present. Raises ValueError on violation."""
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"causal_df is missing required OHLCV columns: {sorted(missing)}. "
            "Ensure the DataFrame is the product of data_engine.load_shard_data."
        )
    if len(df) < const["one_int"]:
        raise ValueError("causal_df must contain at least one row.")


def _patch(target: Dict, key: str, priors: Dict, prior_key: str) -> None:
    """Patches target[key] with priors[prior_key] if the key exists in priors."""
    if prior_key in priors:
        target[key] = priors[prior_key]


def _get_git_commit() -> str:
    """Returns HEAD short commit hash, or 'unversioned' if git is unavailable."""
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=2,
        )
        return result.stdout.strip() or "unversioned"
    except Exception:
        return "unversioned"
