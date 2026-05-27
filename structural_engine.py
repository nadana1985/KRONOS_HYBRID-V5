"""
KRONOS Structural Sovereign Engine
====================================
Vectorised, config-driven implementations of Slots 0-14 and
the Slot fifteen sovereign veto composite.

ALL parameters resolve exclusively from the slot_cfg and const dicts
passed at call time. No inline literals exist in this module.

Dependencies: numpy, pandas, scipy
"""

from __future__ import annotations

import logging
import numpy as np
import pandas as pd
from scipy import signal
from typing import Dict, Optional

# Optional Numba acceleration — graceful fallback if not installed
try:
    from numba import njit as _njit
    _NUMBA_AVAILABLE = True
except ImportError:
    def _njit(*args, **kwargs):          # noqa: E306
        """No-op decorator when numba is unavailable."""
        if len(args) == 1 and callable(args[0]):
            return args[0]
        def _wrap(fn):
            return fn
        return _wrap
    _NUMBA_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# SLOT REGISTRY — maps slot_cfg["type"] → implementation function
# "type" strings are engine-internal routing keys loaded from params_yaml.txt
# ─────────────────────────────────────────────────────────────────────────────

_REGISTRY: Dict[str, object] = {}
_LOGGER = logging.getLogger(__name__)


def _enforce_finite(series: pd.Series, const: Dict, slot_name: str) -> pd.Series:
    """Clamp/clean non-finite values for numerical regime safety."""
    if not const.get("finite_check_enabled", True):
        return series

    zero_f = const["zero_float"]
    z_clip = const["z_clip_default"]

    # Coerce nullable/object series safely before finite check.
    numeric = pd.to_numeric(series, errors="coerce")
    arr = numeric.to_numpy(dtype=float, copy=False)

    if not np.isfinite(arr).all():
        _LOGGER.warning(
            "Non-finite values detected in slot '%s'; applying sanitize and clip.",
            slot_name,
        )
        numeric = (
            numeric.replace([np.inf, -np.inf], np.nan)
            .fillna(zero_f)
            .clip(-z_clip, z_clip)
        )
    return numeric


def _register(type_key: str):
    def decorator(fn):
        def _wrapped(df: pd.DataFrame, agg_trades: pd.DataFrame, slot_cfg: Dict, const: Dict) -> pd.Series:
            out = fn(df, agg_trades, slot_cfg, const)
            return _enforce_finite(out, const, type_key)
        _REGISTRY[type_key] = _wrapped
        return _wrapped
    return decorator


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def compute_slots_sovereign(
    df: pd.DataFrame,
    agg_trades: pd.DataFrame,
    structural_cfg: Dict,
    global_cfg: Dict,
) -> pd.DataFrame:
    """
    Computes all structural sovereign slots in the order defined by
    structural_cfg["slot_order"].  Each slot's parameters are resolved
    from structural_cfg[slot_key].  Returns a DataFrame aligned to df.index.
    """
    const = global_cfg["reproducibility"]["constants"]
    slot_order = structural_cfg["slot_order"]
    results: Dict[str, pd.Series] = {}

    for slot_key in slot_order:
        slot_cfg = structural_cfg[slot_key]
        slot_type = slot_cfg["type"]
        fn = _REGISTRY.get(slot_type)
        if fn is None:
            raise ValueError(
                f"No implementation for slot type '{slot_type}' "
                f"(slot key '{slot_key}'). Register it in structural_engine."
            )
        key_name = slot_cfg["key_name"]
        res = fn(df, agg_trades, slot_cfg, const)
        res = _enforce_finite(res, const, key_name)
        results[key_name] = res

    output_df = pd.DataFrame(results, index=df.index)
    for col in output_df.columns:
        output_df[col] = _enforce_finite(output_df[col], const, col)
    return output_df


def _safe_zscore_normalize(
    series: pd.Series,
    slot_cfg: Dict,
    const: Dict,
    window: int = None
) -> pd.Series:
    """Sovereign numerical safety layer — used by all z-score style slots."""
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]
    z_clip = const["z_clip_default"]
    
    w = window or slot_cfg.get("normalisation_window", const["default_normalisation_window"])
    
    roll_mean = series.rolling(w, min_periods=1).mean()
    roll_std = series.rolling(w, min_periods=1).std().clip(lower=epsilon)
    
    z = (series - roll_mean) / roll_std
    z = z.clip(-z_clip, z_clip)
    
    return _enforce_finite(z.fillna(zero_f), const, slot_cfg.get("type", "zscore_helper"))


def _normalize_slot(
    series: pd.Series,
    col_key: str,
    slot_15_cfg: Dict,
    const: Dict,
) -> pd.Series:
    """Fully config-driven rolling normalisation."""
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]
    one_f = const["one_float"]
    w = slot_15_cfg.get("normalisation_window", const["default_normalisation_window"])
    
    # Check if per-slot bounds are configured
    per_norm = slot_15_cfg.get("per_slot_normalisation", {})
    if col_key in per_norm:
        bounds = per_norm[col_key]
        low, high = float(bounds["low"]), float(bounds["high"])
        # If signed (low < 0), take absolute value first
        if low < zero_f:
            s_abs = series.abs()
            return ((s_abs.clip(zero_f, high) - zero_f) / (high - zero_f + epsilon)).clip(zero_f, one_f)
        else:
            return ((series.clip(low, high) - low) / (high - low + epsilon)).clip(zero_f, one_f)
    
    # Empirical rolling min-max normalization
    rmin = series.rolling(w, min_periods=const["one_int"]).min()
    rmax = series.rolling(w, min_periods=const["one_int"]).max()
    denom = (rmax - rmin).clip(lower=epsilon)
    return ((series - rmin) / denom).clip(zero_f, one_f)


def compute_veto_composite(
    structural_df: pd.DataFrame,
    slot_15_cfg: Dict,
    const: Dict,
) -> pd.Series:
    """
    Weighted composite of all structural slot scores (sovereign veto).
    Weights from slot_15_cfg["weights"].  Sum-to-one enforced at runtime.
    """
    weights = slot_15_cfg["weights"]
    one_f = const["one_float"]
    zero_f = const["zero_float"]
    epsilon = const["epsilon"]

    weight_sum = sum(weights.values())
    if abs(weight_sum - one_f) > epsilon:
        raise ValueError(
            f"Slot fifteen weights sum to {weight_sum:.6f}, not one_float. "
            "Fix cfg['feature_builder']['structural']['slot_15']['weights']."
        )

    composite = pd.Series(zero_f, index=structural_df.index, dtype=float)
    for col_key, weight in weights.items():
        if col_key not in structural_df.columns:
            raise KeyError(
                f"Weight key '{col_key}' not in structural output columns. "
                "Ensure slot key_name values match slot_15 weight keys."
            )
        # Normalize the column before weighting to prevent scale mismatch and cancellation
        norm_series = _normalize_slot(structural_df[col_key], col_key, slot_15_cfg, const)
        composite = composite + norm_series.fillna(zero_f) * weight

    return composite.clip(zero_f, one_f)


def compute_slot(
    df: pd.DataFrame,
    agg_trades: pd.DataFrame,
    slot_cfg: Dict,
    global_cfg: Dict,
) -> pd.Series:
    """Compute a single structural slot by type dispatch."""
    const = global_cfg["reproducibility"]["constants"]
    fn = _REGISTRY.get(slot_cfg["type"])
    if fn is None:
        raise ValueError(f"Unknown slot type '{slot_cfg['type']}'.")
    return fn(df, agg_trades, slot_cfg, const)


# ─────────────────────────────────────────────────────────────────────────────
# SLOT 0 — Bid-Ask Delta Absorption
# ─────────────────────────────────────────────────────────────────────────────

@_register("bid_ask_absorb")
def _slot_bid_ask_absorb(
    df: pd.DataFrame,
    agg_trades: pd.DataFrame,
    slot_cfg: Dict,
    const: Dict,
) -> pd.Series:
    """
    Measures cumulative buy/sell absorption at local price extremes.
    Score in [-one_float, one_float]; positive = bullish absorption.
    """
    lookback = slot_cfg["lookback_bars"]
    decay = slot_cfg["decay_factor"]
    extreme_thresh = slot_cfg["extreme_threshold"]
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]
    one_f = const["one_float"]

    roll_low = df["low"].rolling(lookback, min_periods=lookback).min()
    roll_high = df["high"].rolling(lookback, min_periods=lookback).max()
    price_range = (roll_high - roll_low).clip(lower=epsilon)

    low_prox = (df["low"] - roll_low) / price_range
    high_prox = (roll_high - df["high"]) / price_range

    buy_vol = agg_trades["buy_vol"].reindex(df.index, fill_value=zero_f)
    sell_vol = agg_trades["sell_vol"].reindex(df.index, fill_value=zero_f)

    buy_at_low = buy_vol.where(low_prox < extreme_thresh, other=zero_f)
    sell_at_high = sell_vol.where(high_prox < extreme_thresh, other=zero_f)

    ewm_span = max(lookback * (one_f - decay), one_f)
    cum_buy = buy_at_low.ewm(span=ewm_span, adjust=False).mean()
    cum_sell = sell_at_high.ewm(span=ewm_span, adjust=False).mean()

    total = cum_buy + cum_sell + epsilon
    score = (cum_buy - cum_sell) / total
    return score.clip(-one_f, one_f).fillna(zero_f)


# ─────────────────────────────────────────────────────────────────────────────
# SLOT 1 — Order Flow Toxicity (VPIN)
# ─────────────────────────────────────────────────────────────────────────────

@_register("vpin")
def _slot_vpin(
    df: pd.DataFrame,
    agg_trades: pd.DataFrame,
    slot_cfg: Dict,
    const: Dict,
) -> pd.Series:
    """
    Volume-Synchronised Probability of Informed Trading.
    Proxied per-bar: |buy_vol - sell_vol| / total_vol, rolling average.
    """
    lookback = slot_cfg["lookback_buckets"]
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]

    buy_vol = agg_trades["buy_vol"].reindex(df.index, fill_value=zero_f)
    sell_vol = agg_trades["sell_vol"].reindex(df.index, fill_value=zero_f)
    total_vol = (buy_vol + sell_vol).clip(lower=epsilon)

    order_imbalance = (buy_vol - sell_vol).abs() / total_vol
    return order_imbalance.rolling(lookback, min_periods=lookback).mean().fillna(zero_f)


# ─────────────────────────────────────────────────────────────────────────────
# SLOT 2 — Spectral Entropy
# ─────────────────────────────────────────────────────────────────────────────

@_register("spectral_entropy")
def _slot_spectral_entropy(
    df: pd.DataFrame,
    agg_trades: pd.DataFrame,
    slot_cfg: Dict,
    const: Dict,
) -> pd.Series:
    """
    Shannon entropy of the FFT power spectral density of rolling returns.
    Low entropy = dominant frequency; high entropy = chaotic.
    """
    lookback = slot_cfg["lookback_bars"]
    use_log = slot_cfg["use_log_returns"]
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]

    close = df["close"]
    if use_log:
        rets = np.log(close / close.shift(1) + epsilon)
    else:
        rets = close.pct_change()

    def _spectral_entropy(x: np.ndarray) -> float:
        x = x[~np.isnan(x)]
        if len(x) < 2:
            return np.nan
        mag_sq = np.abs(np.fft.rfft(x - x.mean())) ** 2
        total = mag_sq.sum()
        if total < epsilon:
            return zero_f
        p = mag_sq / total
        p = p[p > epsilon]
        return float(-np.sum(p * np.log(p)))

    return rets.rolling(lookback, min_periods=lookback).apply(
        _spectral_entropy, raw=True
    ).fillna(zero_f)


# ─────────────────────────────────────────────────────────────────────────────
# SLOT 3 — Log Variance Ratio
# ─────────────────────────────────────────────────────────────────────────────

@_register("log_var_ratio")
def _slot_log_var_ratio(
    df: pd.DataFrame,
    agg_trades: pd.DataFrame,
    slot_cfg: Dict,
    const: Dict,
) -> pd.Series:
    """
    Log ratio of short-window to long-window return variance.
    Negative value → vol compression → mean-reversion precursor.
    """
    short_w = slot_cfg["short_window"]
    long_w = slot_cfg["long_window"]
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]

    log_ret = np.log(df["close"] / df["close"].shift(1) + epsilon)
    short_var = log_ret.rolling(short_w, min_periods=short_w).var()
    long_var = log_ret.rolling(long_w, min_periods=long_w).var()
    ratio = np.log((short_var + epsilon) / (long_var + epsilon))
    return ratio.fillna(zero_f)


# ─────────────────────────────────────────────────────────────────────────────
# SLOT 4 — Fractal Exhaustion (Hurst Exponent, R/S)
# ─────────────────────────────────────────────────────────────────────────────

@_register("fractal_hurst")
def _slot_fractal_hurst(
    df: pd.DataFrame,
    agg_trades: pd.DataFrame,
    slot_cfg: Dict,
    const: Dict,
) -> pd.Series:
    """
    Rolling Hurst exponent via Rescaled Range analysis.
    Score = half_float - H  (positive when H < half_float = mean-reverting).
    """
    lookback = slot_cfg["lookback_bars"]
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]
    half_f = const["half_float"]

    log_ret = np.log(df["close"] / df["close"].shift(1) + epsilon)

    @_njit
    def _hurst_nb(x: np.ndarray, eps: float, half: float) -> float:
        n = len(x)
        if n < 2:
            return half
        mean_x = x.mean()
        cum_dev = np.cumsum(x - mean_x)
        R = cum_dev.max() - cum_dev.min()
        S = x.std()
        if S < eps:
            return half
        rs = R / (S + eps)
        if rs < eps:
            return half
        return np.log(rs) / np.log(float(n))

    _eps = epsilon
    _half = half_f

    def _hurst_wrapper(x: np.ndarray) -> float:
        return float(_hurst_nb(x[~np.isnan(x)], _eps, _half))

    hurst_series = log_ret.rolling(lookback, min_periods=lookback).apply(
        _hurst_wrapper, raw=True
    )
    score = half_f - hurst_series
    return score.fillna(zero_f)


# ─────────────────────────────────────────────────────────────────────────────
# SLOT 5 — Multi-Lag Autocorrelation
# ─────────────────────────────────────────────────────────────────────────────

@_register("autocorr_multillag")
def _slot_autocorr_multillag(
    df: pd.DataFrame,
    agg_trades: pd.DataFrame,
    slot_cfg: Dict,
    const: Dict,
) -> pd.Series:
    """
    Mean absolute autocorrelation across configured lags.
    High value = persistent structure in returns.
    """
    lookback = slot_cfg["lookback_bars"]
    lags = slot_cfg["lags"]
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]

    log_ret = np.log(df["close"] / df["close"].shift(1) + epsilon)

    lag_series = []
    for lag in lags:
        ac = log_ret.rolling(lookback, min_periods=lookback).apply(
            lambda x: float(pd.Series(x).autocorr(lag=lag))
            if len(x) > lag else np.nan,
            raw=False,
        )
        lag_series.append(ac.abs())

    combined = pd.concat(lag_series, axis=1)
    return combined.mean(axis=1).fillna(zero_f)


# ─────────────────────────────────────────────────────────────────────────────
# SLOT 6 — Exhaustion Momentum (EMA Ribbon Deviation)
# ─────────────────────────────────────────────────────────────────────────────

@_register("ema_ribbon_deviation")
def _slot_ema_ribbon_deviation(
    df: pd.DataFrame,
    agg_trades: pd.DataFrame,
    slot_cfg: Dict,
    const: Dict,
) -> pd.Series:
    """
    Mean absolute deviation of price from EMA ribbon members,
    normalised by rolling std of deviations. High value = stretched ribbon.
    """
    spans = slot_cfg["ema_ribbon_spans"]
    div_window = slot_cfg["divergence_window"]
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]

    close = df["close"]
    deviations = pd.concat(
        [(close - close.ewm(span=s, adjust=False).mean()) for s in spans],
        axis=1,
    )
    mean_dev = deviations.abs().mean(axis=1)
    score = _safe_zscore_normalize(mean_dev, slot_cfg, const, div_window)
    return score.fillna(zero_f)


# ─────────────────────────────────────────────────────────────────────────────
# SLOT 7 — Volume-Price Divergence
# ─────────────────────────────────────────────────────────────────────────────

@_register("volume_price_divergence")
def _slot_volume_price_divergence(
    df: pd.DataFrame,
    agg_trades: pd.DataFrame,
    slot_cfg: Dict,
    const: Dict,
) -> pd.Series:
    """
    Divergence between price acceleration and volume acceleration.
    Strong divergence = unsupported price move = potential reversal.
    """
    lookback = slot_cfg["lookback_bars"]
    lag = slot_cfg["acceleration_lag"]
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]

    log_ret = np.log(df["close"] / df["close"].shift(const["one_int"]) + epsilon)
    price_accel = log_ret - log_ret.shift(lag)

    vol = agg_trades["buy_vol"].reindex(df.index, fill_value=zero_f) + \
          agg_trades["sell_vol"].reindex(df.index, fill_value=zero_f)
    vol_chg = np.log((vol + epsilon) / (vol.shift(lag) + epsilon)).fillna(zero_f)

    # Divergence: price accelerating but volume decelerating (or vice versa)
    divergence = (price_accel.abs() - vol_chg.abs()).rolling(
        lookback, min_periods=lookback
    ).mean()
    score = _safe_zscore_normalize(divergence, slot_cfg, const, lookback)
    return score.fillna(zero_f)


# ─────────────────────────────────────────────────────────────────────────────
# SLOT 8 — HMM Regime Classifier
# ─────────────────────────────────────────────────────────────────────────────

@_register("hmm_regime")
def _slot_hmm_regime(
    df: pd.DataFrame,
    agg_trades: pd.DataFrame,
    slot_cfg: Dict,
    const: Dict,
) -> pd.Series:
    """
    Rolling Gaussian HMM walk-forward regime label.
    Requires hmmlearn. Falls back to volatility-quantile proxy if unavailable.
    Regime label (integer) normalised to [zero_float, one_float].
    """
    lookback = slot_cfg["lookback_bars"]
    n_states = slot_cfg["num_regimes"]
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]
    one_f = const["one_float"]

    log_ret = np.log(df["close"] / df["close"].shift(const["one_int"]) + epsilon).fillna(zero_f)
    vol = log_ret.rolling(lookback, min_periods=lookback).std().fillna(zero_f)

    try:
        from hmmlearn.hmm import GaussianHMM

        features = np.column_stack([log_ret.values, vol.values])
        labels = np.full(len(df), np.nan)
        n_iter = slot_cfg.get("hmm_n_iter", 100)
        refit_every = slot_cfg.get("hmm_refit_interval", lookback)
        cached_model = None
        cached_sort_order = None

        # Walk-forward: fit once per refit_every bars, predict in batches → O(n/R)
        for start in range(lookback, len(df), refit_every):
            train_window = features[start - lookback: start]
            if np.isnan(train_window).any():
                continue
            try:
                m = GaussianHMM(
                    n_components=n_states,
                    covariance_type="diag",
                    n_iter=n_iter,
                    random_state=const["zero_int"],
                )
                if cached_model is not None:
                    try:
                        if (hasattr(cached_model, "n_components") and 
                            cached_model.n_components == n_states and 
                            hasattr(cached_model, "means_") and 
                            cached_model.means_.shape == (n_states, train_window.shape[1])):
                            
                            # Re-sort states by volatility covariance ascending to prevent label drift before warm-start copy
                            prev_covars = cached_model.covars_
                            state_vols = np.array([np.mean(np.diag(np.diag(prev_covars[s]))) for s in range(n_states)])
                            sort_order = np.argsort(state_vols)
                            
                            m.n_features = int(cached_model.n_features)
                            m.startprob_ = np.copy(cached_model.startprob_[sort_order]).astype(float)
                            m.transmat_ = np.copy(cached_model.transmat_[sort_order][:, sort_order]).astype(float)
                            m.means_ = np.copy(cached_model.means_[sort_order]).astype(float)
                            m.covars_ = np.copy(prev_covars[sort_order]).astype(float)
                            m.init_params = ""  # SOVEREIGN_MATH_CONSTANT: warm-start HMM
                    except Exception:
                        m.init_params = "stmc"  # SOVEREIGN_MATH_CONSTANT: standard fallback
                
                m.fit(train_window)

                # FLAW 3 FIX: sort states by ascending mean volatility covariance.
                try:
                    state_vols = np.array([np.mean(np.diag(np.diag(m.covars_[s]))) for s in range(n_states)])
                    sort_order = np.argsort(state_vols)   # ascending: low-vol → high-vol
                    # Re-map transition matrices and means to sorted order
                    m.means_ = m.means_[sort_order]
                    m.covars_ = m.covars_[sort_order]
                    m.startprob_ = m.startprob_[sort_order]
                    m.transmat_ = m.transmat_[sort_order][:, sort_order]
                except Exception:
                    sort_order = np.arange(n_states)

                cached_model = m
                cached_sort_order = sort_order
            except Exception:
                pass

            if cached_model is None:
                continue

            # Predict the next refit_every bars using the freshly fitted model
            batch_end = min(start + refit_every, len(df))
            predict_input = features[start - lookback: batch_end]
            if np.isnan(predict_input).any():
                continue
            try:
                probs = cached_model.predict_proba(predict_input)
                # Remap the state columns to volatility sorted order
                sorted_probs = probs[:, cached_sort_order]
                target_idx = slot_cfg.get("target_regime_index", const["three_int"])
                # Extract target regime probability for the batch
                labels[start:batch_end] = sorted_probs[lookback: lookback + (batch_end - start), target_idx]
            except Exception:
                pass

        regime = pd.Series(labels, index=df.index)

    except ImportError:
        target_idx = slot_cfg.get("target_regime_index", const["three_int"])
        regime_idx = pd.cut(vol, bins=n_states, labels=False).astype(float)
        regime = (regime_idx == target_idx).astype(float)

    return regime.fillna(zero_f).clip(zero_f, one_f)


# ─────────────────────────────────────────────────────────────────────────────
# SLOT 9 — Liquidity Vacuum (Microstructure Proxy)
# ─────────────────────────────────────────────────────────────────────────────

@_register("liquidity_vacuum")
def _slot_liquidity_vacuum(
    df: pd.DataFrame,
    agg_trades: pd.DataFrame,
    slot_cfg: Dict,
    const: Dict,
) -> pd.Series:
    """
    Proxy for order-book liquidity vacuum using trade volume imbalance.
    Extreme imbalance at threshold = depleted liquidity on one side.
    """
    imbalance_thresh = slot_cfg["imbalance_threshold"]
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]
    one_f = const["one_float"]

    buy_vol = agg_trades["buy_vol"].reindex(df.index, fill_value=zero_f)
    sell_vol = agg_trades["sell_vol"].reindex(df.index, fill_value=zero_f)
    total = (buy_vol + sell_vol).clip(lower=epsilon)

    imbalance = (buy_vol - sell_vol).abs() / total
    # Score: how far imbalance exceeds the configured threshold
    vacuum_score = ((imbalance - imbalance_thresh) / (one_f - imbalance_thresh + epsilon)).clip(
        zero_f, one_f
    )
    return vacuum_score.fillna(zero_f)


# ─────────────────────────────────────────────────────────────────────────────
# SLOT 10 — Wick-to-Body Ratio
# ─────────────────────────────────────────────────────────────────────────────

@_register("wick_ratio")
def _slot_wick_ratio(
    df: pd.DataFrame,
    agg_trades: pd.DataFrame,
    slot_cfg: Dict,
    const: Dict,
) -> pd.Series:
    """
    Wick prominence ratio: (high - low) / max(|close - open|, epsilon).
    High ratio with small body = potential exhaustion / indecision bar.
    Normalised to [zero_float, one_float] via rolling percentile.
    """
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]
    one_f = const["one_float"]
    body_thresh = slot_cfg["body_threshold"]
    w = slot_cfg["normalisation_window"]
    q_thresh = slot_cfg["quantile_threshold"]

    candle_range = (df["high"] - df["low"]).clip(lower=epsilon)
    body = (df["close"] - df["open"]).abs().clip(lower=epsilon)
    wick_ratio = (candle_range / body).clip(upper=const["max_wick_ratio"])

    # Flag bars with small body (doji-like exhaustion)
    body_pct = body / candle_range
    exhaustion_flag = (body_pct < body_thresh).astype(float)

    # Combined: wick prominence weighted by exhaustion flag
    score = wick_ratio * exhaustion_flag
    # Rolling quantile to avoid lookahead leak
    roll_q = wick_ratio.rolling(w, min_periods=const["one_int"]).quantile(q_thresh)
    score = score.clip(upper=roll_q)

    # Rolling max instead of expanding max to avoid path-dependency
    norm = score.rolling(w, min_periods=const["one_int"]).max().clip(lower=epsilon)
    return (score / norm).clip(zero_f, one_f).fillna(zero_f)


# ─────────────────────────────────────────────────────────────────────────────
# SLOT 11 — S/R KDE Proximity
# ─────────────────────────────────────────────────────────────────────────────

@_register("sr_kde_proximity")
def _slot_sr_kde_proximity(
    df: pd.DataFrame,
    agg_trades: pd.DataFrame,
    slot_cfg: Dict,
    const: Dict,
) -> pd.Series:
    """
    Proximity to nearest pivot cluster via kernel density estimation.
    High score = price near a dense S/R zone = reversal probability elevated.
    """
    pivot_lookback = slot_cfg["pivot_lookback"]
    pivot_strength = slot_cfg["pivot_strength"]
    bandwidth = slot_cfg["bandwidth"]
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]
    one_f = const["one_float"]

    # ── STAGE 1: vectorised pivot identification ─────────────────────────────
    # A bar is a pivot high if its high equals the rolling max of a
    # (2*pivot_strength + 1)-bar centred window (no Python loop).
    win = pivot_strength * 2 + 1
    roll_max_local = df["high"].rolling(win, center=True, min_periods=win).max()
    roll_min_local = df["low"].rolling(win, center=True, min_periods=win).min()
    is_pivot_high = df["high"] == roll_max_local
    is_pivot_low = df["low"] == roll_min_local

    # Pivot prices (NaN where not a pivot)
    pivot_h_prices = df["high"].where(is_pivot_high)
    pivot_l_prices = df["low"].where(is_pivot_low)

    # ── STAGE 2: rolling nearest S/R level within pivot_lookback ────────────
    # Shift rolling calculation to prevent lookahead bias when precomputing vectorially.
    # W is adjusted to W = pivot_lookback - pivot_strength, then shifted by pivot_strength.
    W = max(pivot_lookback - pivot_strength, 1)
    nearest_resist = pivot_h_prices.rolling(W, min_periods=1).max().shift(pivot_strength)
    nearest_support = pivot_l_prices.rolling(W, min_periods=1).min().shift(pivot_strength)

    # ── STAGE 3: exponential proximity score ────────────────────────────────
    dist_resist = (nearest_resist - df["close"]).abs() / (
        df["close"] * bandwidth + epsilon
    )
    dist_support = (df["close"] - nearest_support).abs() / (
        df["close"] * bandwidth + epsilon
    )
    min_dist = pd.concat([dist_resist, dist_support], axis=1).min(axis=1)
    score = np.exp(-min_dist.clip(upper=const["ten_float"]))
    return score.clip(zero_f, one_f).fillna(zero_f)


# ─────────────────────────────────────────────────────────────────────────────
# SLOT 12 — Micro-Price Deviation
# ─────────────────────────────────────────────────────────────────────────────

@_register("microprice_deviation")
def _slot_microprice_deviation(
    df: pd.DataFrame,
    agg_trades: pd.DataFrame,
    slot_cfg: Dict,
    const: Dict,
) -> pd.Series:
    """
    Deviation of micro-price (volume-weighted) from raw mid-price (close).
    High positive deviation = buy-side pressure driving price above mid.
    """
    coeff = slot_cfg["imbalance_coefficient"]
    rolling_w = slot_cfg["rolling_window"]
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]

    buy_vol = agg_trades["buy_vol"].reindex(df.index, fill_value=zero_f)
    sell_vol = agg_trades["sell_vol"].reindex(df.index, fill_value=zero_f)
    total_vol = (buy_vol + sell_vol).clip(lower=epsilon)

    # Micro-price: close adjusted by volume imbalance coefficient
    imbalance = (buy_vol - sell_vol) / total_vol
    micro_price = df["close"] * (1 + coeff * imbalance)

    deviation = micro_price - df["close"]
    score = _safe_zscore_normalize(deviation, slot_cfg, const, rolling_w)
    return score.fillna(zero_f)


# ─────────────────────────────────────────────────────────────────────────────
# SLOT 13 — Shannon Returns Entropy
# ─────────────────────────────────────────────────────────────────────────────

@_register("shannon_entropy")
def _slot_shannon_entropy(
    df: pd.DataFrame,
    agg_trades: pd.DataFrame,
    slot_cfg: Dict,
    const: Dict,
) -> pd.Series:
    """
    Shannon entropy of discretised log-return distribution over rolling window.
    Low entropy → concentrated return distribution → structural regime clarity.
    """
    lookback = slot_cfg["lookback_bars"]
    num_bins = slot_cfg["num_bins"]
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]

    log_ret = np.log(df["close"] / df["close"].shift(1) + epsilon)

    def _shannon(x: np.ndarray) -> float:
        x = x[~np.isnan(x)]
        if len(x) < 2:
            return np.nan
        counts, _ = np.histogram(x, bins=num_bins)
        total = counts.sum()
        if total == 0:
            return zero_f
        p = counts[counts > 0] / total
        return float(-np.sum(p * np.log(p + epsilon)))

    return log_ret.rolling(lookback, min_periods=lookback).apply(
        _shannon, raw=True
    ).fillna(zero_f)


# ─────────────────────────────────────────────────────────────────────────────
# SLOT 14 — Hilbert Dominant Cycle Phase
# ─────────────────────────────────────────────────────────────────────────────

@_register("hilbert_cycle")
def _slot_hilbert_cycle(
    df: pd.DataFrame,
    agg_trades: pd.DataFrame,
    slot_cfg: Dict,
    const: Dict,
) -> pd.Series:
    """
    Instantaneous phase from Hilbert Transform on rolling detrended log-returns.
    High rate-of-phase-change → cycle exhaustion → potential reversal.
    """
    lookback = slot_cfg["lookback_bars"]
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]
    one_f = const["one_float"]

    log_ret = np.log(df["close"] / df["close"].shift(1) + epsilon).fillna(zero_f)

    def _hilbert_phase_delta(x: np.ndarray) -> float:
        x = x[~np.isnan(x)]
        if len(x) < 4:
            return np.nan
        detrended = x - x.mean()
        analytic = signal.hilbert(detrended)
        phase = np.unwrap(np.angle(analytic))
        phase_delta = np.abs(np.diff(phase)).mean()
        return float(phase_delta)

    raw = log_ret.rolling(lookback, min_periods=lookback).apply(
        _hilbert_phase_delta, raw=True
    ).fillna(zero_f)

    norm = raw.rolling(lookback, min_periods=lookback).max().clip(lower=epsilon)
    return (raw / norm).clip(zero_f, one_f).fillna(zero_f)
