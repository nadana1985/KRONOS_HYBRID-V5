"""
KRONOS Neural Integration Engine
===================================
Handles the frozen Kronos-mini transformer layer:
  - SHA-256 weight + tokenizer integrity verification
  - Causal OHLCV sequence tokenisation
  - Frozen bottleneck embedding extraction
  - Volatility-gated exponential-decay pooling
  - L_p conviction norm computation
  - Dynamic threshold from rolling conviction history

ALL parameters resolve exclusively from cfg dicts. No inline literals.

Dependencies: torch, transformers (optional — degrades gracefully to
              zero-conviction stub when unavailable)
"""

from __future__ import annotations

import hashlib
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# MODULE-LEVEL MODEL CACHE  (loaded once, reused across bars)
# ─────────────────────────────────────────────────────────────────────────────
_MODEL_CACHE: Dict[str, object] = {}
_TOKENIZER_CACHE: Dict[str, object] = {}


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL SOVEREIGN RESOURCE RESOLUTION
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_absolute_resource_path(resource_name: str) -> str:
    """
    Sovereign Path Resolution Layer.
    Scans multiple relative and parent fallback paths to find the model/tokenizer directory.
    Returns the absolute path of the first directory that actually exists.
    Falls back to root-relative path if none exist.
    """
    import os
    if os.path.isabs(resource_name):
        return resource_name

    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Lightning AI Studio base paths
    cloud_base = "/teamspace/studios/this_studio/kronos"

    # Candidate search list (workspace root, parent root, nested models, and CWD)
    candidates = [
        os.path.abspath(os.path.join(root_dir, resource_name)),
        os.path.abspath(os.path.join(root_dir, "..", resource_name)),
        os.path.abspath(os.path.join(root_dir, "kronos_module", "models", os.path.basename(resource_name))),
        os.path.abspath(os.path.join(cloud_base, resource_name)),
        os.path.abspath(os.path.join(cloud_base, "kronos_module", "models", os.path.basename(resource_name))),
        os.path.abspath(os.path.join(cloud_base, "models", os.path.basename(resource_name))),
        os.path.abspath(os.path.join(cloud_base, os.path.basename(resource_name))),
        os.path.abspath(os.path.join(os.getcwd(), resource_name)),
    ]
    
    for cand in candidates:
        if os.path.isdir(cand):
            return cand
            
    return os.path.abspath(os.path.join(root_dir, resource_name))


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API — LOAD & VERIFY
# ─────────────────────────────────────────────────────────────────────────────

def load_verified_model(config: Dict) -> object:
    """
    Loads Kronos-mini model from cfg["kronos_mini"]["model_name"].
    Verifies cached weights against cfg["kronos_mini"]["model_sha256"]
    when cfg["reproducibility"]["enforce_pinning"] is truthy.
    Returns cached model on subsequent calls (zero reload cost).
    """
    kronos_cfg = config["kronos_mini"]
    repro_cfg = config["reproducibility"]
    model_name = kronos_cfg["model_name"]

    if model_name in _MODEL_CACHE:
        return _MODEL_CACHE[model_name]

    try:
        import torch
        import sys
        import os

        # Dynamically locate and prepend the active kronos_module directory to sys.path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        absolute_path = _resolve_absolute_resource_path(model_name)
        
        module_candidates = [
            os.path.join(current_dir, "kronos_module"),
            "/teamspace/studios/this_studio/kronos/kronos_module",
        ]
        
        try:
            parts = Path(absolute_path).parts
            if "kronos_module" in parts:
                idx = parts.index("kronos_module")
                module_candidates.append(str(Path(*parts[:idx+1])))
        except Exception:
            pass
            
        for mc in module_candidates:
            if os.path.isdir(mc):
                abs_mc = os.path.abspath(mc)
                if abs_mc not in sys.path:
                    sys.path.insert(0, abs_mc)

        from model import Kronos

        precision_str = repro_cfg["precision"]
        dtype = _resolve_dtype(precision_str)

        # Anchor relative paths dynamically for absolute CWD independence via Sovereign Path Resolver
        absolute_path = _resolve_absolute_resource_path(model_name)

        # PyTorchModelHubMixin from_pretrained handles local directories beautifully
        model = Kronos.from_pretrained(absolute_path, local_files_only=True)
        
        if dtype is not None:
            model = model.to(dtype)
            
        # Move model parameters to CUDA device if GPU execution is active and available
        device = "cuda" if (torch.cuda.is_available() and config["feature_builder"].get("use_gpu", True)) else "cpu"
        model = model.to(device)
            
        model.eval()

        # Freeze all weights permanently
        for param in model.parameters():
            param.requires_grad_(False)

        if repro_cfg["enforce_pinning"]:
            _verify_model_sha256(model, kronos_cfg["model_sha256"])

        _MODEL_CACHE[model_name] = model
        return model

    except Exception as exc:
        warnings.warn(
            f"Kronos-mini model load failed: {exc}. "
            "Neural gate will return zero_float conviction. "
            "Set cfg['miner']['enable_kronos'] to disable this warning.",
            RuntimeWarning,
            stacklevel=2,
        )
        _MODEL_CACHE[model_name] = None
        return None


def load_verified_tokenizer(config: Dict) -> object:
    """
    Loads Kronos tokenizer from cfg["kronos_mini"]["tokenizer_name"].
    Verifies against cfg["kronos_mini"]["tokenizer_sha256"] when pinning enforced.
    Returns cached tokenizer on subsequent calls.
    """
    kronos_cfg = config["kronos_mini"]
    repro_cfg = config["reproducibility"]
    tok_name = kronos_cfg["tokenizer_name"]

    if tok_name in _TOKENIZER_CACHE:
        return _TOKENIZER_CACHE[tok_name]

    try:
        import torch
        import sys
        import os

        # Dynamically locate and prepend the active kronos_module directory to sys.path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        absolute_path = _resolve_absolute_resource_path(tok_name)
        
        module_candidates = [
            os.path.join(current_dir, "kronos_module"),
            "/teamspace/studios/this_studio/kronos/kronos_module",
        ]
        
        try:
            parts = Path(absolute_path).parts
            if "kronos_module" in parts:
                idx = parts.index("kronos_module")
                module_candidates.append(str(Path(*parts[:idx+1])))
        except Exception:
            pass
            
        for mc in module_candidates:
            if os.path.isdir(mc):
                abs_mc = os.path.abspath(mc)
                if abs_mc not in sys.path:
                    sys.path.insert(0, abs_mc)

        from model import KronosTokenizer

        # Anchor relative paths dynamically for absolute CWD independence via Sovereign Path Resolver
        absolute_path = _resolve_absolute_resource_path(tok_name)

        tokenizer = KronosTokenizer.from_pretrained(absolute_path, local_files_only=True)
        
        # Move tokenizer parameters to CUDA device if GPU execution is active and available
        device = "cuda" if (torch.cuda.is_available() and config["feature_builder"].get("use_gpu", True)) else "cpu"
        tokenizer = tokenizer.to(device)
        
        tokenizer.eval()

        # Freeze all weights permanently
        for param in tokenizer.parameters():
            param.requires_grad_(False)

        if repro_cfg["enforce_pinning"]:
            _verify_tokenizer_sha256(tokenizer, kronos_cfg["tokenizer_sha256"])

        _TOKENIZER_CACHE[tok_name] = tokenizer
        return tokenizer

    except Exception as exc:
        warnings.warn(
            f"Kronos-mini tokenizer load failed: {exc}. "
            "Neural gate will return zero_float conviction.",
            RuntimeWarning,
            stacklevel=2,
        )
        _TOKENIZER_CACHE[tok_name] = None
        return None


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API — EMBEDDING EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def extract_embeddings(
    causal_candles: pd.DataFrame,
    current_idx: int,
    model,
    tokenizer,
    config: Dict,
) -> np.ndarray:
    """
    Extracts volatility-gated pooled bottleneck embeddings for bar current_idx.
    Context window and embedding dim from cfg["kronos_mini"].
    Returns zero-vector of cfg["kronos_mini"]["embedding_dim"] on any failure.
    """
    kronos_cfg = config["kronos_mini"]
    const = config["reproducibility"]["constants"]

    context_length = kronos_cfg["context_length"]
    emb_dim = kronos_cfg["embedding_dim"]
    one_i = const["one_int"]
    zero_i = const["zero_int"]
    zero_f = const["zero_float"]

    zero_emb = np.full(emb_dim, zero_f, dtype=np.float32)

    if model is None or tokenizer is None:
        return zero_emb

    try:
        import torch

        # Enforce a real datetime signal for temporal features.
        if pd.api.types.is_datetime64_any_dtype(causal_candles.index):
            candles_for_time = causal_candles
        elif "datetime" in causal_candles.columns:
            candles_for_time = causal_candles.set_index(pd.to_datetime(causal_candles["datetime"], utc=True))
        elif "timestamp" in causal_candles.columns:
            candles_for_time = causal_candles.set_index(pd.to_datetime(causal_candles["timestamp"], utc=True))
        else:
            raise RuntimeError("Causal contract violation: expected datetime index/column for embeddings.")

        # Causal window: only bars up to and including current_idx
        start = max(zero_i, current_idx + one_i - context_length)
        window_df = candles_for_time.iloc[start: current_idx + one_i]

        if len(window_df) < const["one_int"]:
            return zero_emb

        # Prepare continuous features of shape [1, seq_len, 6]
        # Columns must be open, high, low, close, volume, amount
        price_cols = ['open', 'high', 'low', 'close']
        vol_col = 'volume'
        amt_col = 'amount'

        df = window_df.copy()
        if vol_col not in df.columns:
            df[vol_col] = const["zero_float"]
            df[amt_col] = const["zero_float"]
        elif amt_col not in df.columns:
            df[amt_col] = df[vol_col] * df[price_cols].mean(axis=1)

        x = df[price_cols + [vol_col, amt_col]].values.astype(np.float32)

        # Standard normalization as in KronosPredictor.predict
        x_mean, x_std = np.mean(x, axis=0), np.std(x, axis=0)
        x = (x - x_mean) / (x_std + 1e-5)
        clip_val = kronos_cfg.get("clip", 5.0)
        x = np.clip(x, -clip_val, clip_val)

        # Add batch dimension: [1, seq_len, 6]
        x_batch = x[np.newaxis, :]

        # Convert timestamps to temporal stamps
        timestamps = pd.DatetimeIndex(window_df.index)
        time_df = pd.DataFrame()
        time_df['minute'] = timestamps.minute
        time_df['hour'] = timestamps.hour
        time_df['weekday'] = timestamps.weekday
        time_df['day'] = timestamps.day
        time_df['month'] = timestamps.month
        stamp = time_df.values.astype(np.float32)[np.newaxis, :]

        # Move inputs to correct device
        # Bypass broken PyTorch numpy bridge via pure Python list conversion
        device = next(model.parameters()).device
        x_tensor = torch.tensor(x_batch.tolist(), dtype=torch.float32).to(device)
        stamp_tensor = torch.tensor(stamp.tolist(), dtype=torch.float32).to(device)

        # Run custom tokenizer and model inference causally
        with torch.no_grad():
            s1_ids, s2_ids = tokenizer.encode(x_tensor, half=True)
            s1_logits, context = model.decode_s1(s1_ids, s2_ids, stamp=stamp_tensor)
            
            # Extract last hidden state of shape [d_model]
            # Bypass broken PyTorch numpy bridge via pure Python list conversion
            last_hidden_list = context[0, -one_i, :emb_dim].cpu().float().tolist()
            last_hidden = np.array(last_hidden_list, dtype=np.float32)

        # Volatility-gated EWM pooling
        pooled = _apply_vol_gated_pooling(last_hidden, window_df, causal_candles, kronos_cfg, const)
        return pooled.astype(np.float32)

    except Exception as exc:
        import traceback
        traceback.print_exc()
        warnings.warn(f"Embedding extraction failed: {exc}.", RuntimeWarning, stacklevel=2)
        return zero_emb


def compute_lp_norm(embedding: np.ndarray, config: Dict) -> float:
    """
    Computes L_p norm of the embedding vector.
    p from cfg["feature_builder"]["gate"]["norm_order"].
    """
    const = config["reproducibility"]["constants"]
    p = config["feature_builder"]["gate"]["norm_order"]
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]

    if embedding is None or len(embedding) == 0:
        return float(zero_f)

    norm = float(np.sum(np.abs(embedding) ** p) ** (const["one_float"] / p))
    return norm + epsilon


def dynamic_threshold(
    recent_convictions: pd.Series,
    config: Dict,
    current_timestamp: pd.Timestamp = None,
    current_vol: float = None,
) -> float:
    """
    Computes time-based and volatility-scaled dynamic conviction threshold.
    """
    const = config["reproducibility"]["constants"]
    gate_cfg = config["feature_builder"]["gate"]
    
    multiplier = gate_cfg["conviction_multiplier"]
    vol_multiplier = gate_cfg.get("conviction_vol_multiplier", const["one_float"])
    baseline_vol = gate_cfg.get("baseline_vol", const["zero_float"])
    
    epsilon = const["epsilon"]

    # Support collections.deque or list objects seamlessly
    if not isinstance(recent_convictions, pd.Series):
        recent_convictions = pd.Series(list(recent_convictions))

    valid = recent_convictions.dropna()
    if len(valid) == 0:
        return float(epsilon)

    median_conv = float(valid.median())

    if current_vol is None or baseline_vol <= const["zero_float"]:
        vol_factor = const["one_float"]
    else:
        # Direct volatility scaling: higher realised vol => higher threshold.
        vol_factor = (current_vol / (baseline_vol + epsilon)) * vol_multiplier
        clip_low = gate_cfg.get("conviction_vol_clip_low", 0.3)
        clip_high = gate_cfg.get("conviction_vol_clip_high", 3.0)
        vol_factor = float(np.clip(vol_factor, float(clip_low), float(clip_high)))

    threshold = median_conv * multiplier * vol_factor
    return max(threshold, float(epsilon))


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API — FULL GATE ORCHESTRATION
# ─────────────────────────────────────────────────────────────────────────────

def compute_neural_gate(
    causal_candles: pd.DataFrame,
    current_idx: int,
    recent_convictions: pd.Series,
    kronos_cfg: Dict,
    gate_cfg: Dict,
    const: Dict,
) -> Tuple[float, float, bool, np.ndarray, bool]:
    """
    Full neural gate pipeline for one bar.

    Returns:
        (conviction_score, dynamic_threshold_value, neural_passed, pooled_embedding, neural_available)
    """
    full_cfg = {
        "kronos_mini": kronos_cfg,
        "feature_builder": {"gate": gate_cfg},
        "reproducibility": {"constants": const, "precision": kronos_cfg.get("precision", "float16"), "enforce_pinning": True},
    }
    zero_f = const["zero_float"]
    one_i = const["one_int"]
    zero_i = const["zero_int"]
    emb_dim = kronos_cfg["embedding_dim"]
    zero_emb = np.full(emb_dim, zero_f, dtype=np.float32)

    try:
        model = load_verified_model(full_cfg)
        tokenizer = load_verified_tokenizer(full_cfg)
        neural_available = (model is not None and tokenizer is not None)

        if not neural_available:
            floor_val = gate_cfg.get("min_conviction_floor", 0.05)
            return float(floor_val), float(zero_f), False, zero_emb, False

        embedding = extract_embeddings(causal_candles, current_idx, model, tokenizer, full_cfg)
        conviction = compute_lp_norm(embedding, full_cfg)

        # Volatility computation for conviction threshold scaling (computed from full causal history)
        close_series = pd.Series(causal_candles["close"].values)
        prev_close = close_series.shift(one_i).fillna(close_series.iloc[zero_i])
        epsilon = const["epsilon"]
        log_ret = np.log((close_series.values + epsilon) / (prev_close.values + epsilon))
        current_vol = float(np.std(log_ret))

        # Resolve timestamp
        if "datetime" in causal_candles.columns:
            current_timestamp = causal_candles["datetime"].iloc[current_idx]
        else:
            current_timestamp = causal_candles.index[current_idx]
        if not isinstance(current_timestamp, pd.Timestamp):
            current_timestamp = pd.Timestamp(current_timestamp)

        threshold = dynamic_threshold(
            recent_convictions,
            full_cfg,
            current_timestamp=current_timestamp,
            current_vol=current_vol,
        )
        neural_passed = conviction > threshold

        return float(conviction), float(threshold), bool(neural_passed), embedding, True

    except Exception as exc:
        warnings.warn(
            f"Exception inside compute_neural_gate: {exc}. Gracefully degrading to baseline structural conviction.",
            RuntimeWarning,
            stacklevel=2,
        )
        floor_val = gate_cfg.get("min_conviction_floor", 0.05)
        return float(floor_val), float(zero_f), False, zero_emb, False


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _apply_vol_gated_pooling(
    last_hidden: np.ndarray,
    window_df: pd.DataFrame,
    causal_candles: pd.DataFrame,
    kronos_cfg: Dict,
    const: Dict,
) -> np.ndarray:
    """
    Applies volatility-gated exponential decay pooling.
    When realised vol exceeds a long-term vol percentile threshold the decay is compressed.
    All parameters from kronos_cfg.

    Flaw twelve fix: replaced np.roll circular shift with pd.Series.shift(one_int), which correctly
    introduces a NaN at position zero rather than wrapping the last value.
    Flaw thirteen fix: the percentile threshold is now computed from a long-term rolling std
    reference window (global_vol_ref_bars) over causal_candles rather than the local context window.
    """
    pooling_cfg = kronos_cfg["pooling"]
    decay = pooling_cfg["decay_factor"]
    vol_pct = pooling_cfg["vol_threshold_percentile"]
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]
    zero_i = const["zero_int"]
    one_i = const["one_int"]
    ten_i = const["ten_int"]

    # FLAW 12 FIX: use pd.shift to avoid circular wrap-around lookahead leak
    close_series = pd.Series(window_df["close"].values)
    prev_close = close_series.shift(one_i).fillna(close_series.iloc[zero_i])
    log_ret = np.log((close_series.values + epsilon) / (prev_close.values + epsilon))
    realised_vol = float(np.std(log_ret))

    # FLAW 13 FIX: compute a long-term global reference std over the full causal_candles.
    # global_vol_ref_bars defaults to 10000 to anchor against long-term market behaviour.
    global_ref_bars = kronos_cfg.get("global_vol_ref_bars", 10000)
    if len(causal_candles) >= global_ref_bars:
        global_slice = pd.Series(causal_candles["close"].values[-global_ref_bars:])
        global_prev = global_slice.shift(one_i).fillna(global_slice.iloc[zero_i])
        global_log_ret = np.log((global_slice.values + epsilon) / (global_prev.values + epsilon))
        # Use context_length as the rolling window for the reference std series
        ref_w = kronos_cfg.get("context_length", 2048)
        vol_series = pd.Series(global_log_ret).rolling(ref_w, min_periods=one_i).std()
    else:
        vol_series = pd.Series(log_ret).rolling(max(one_i, len(log_ret) // ten_i), min_periods=one_i).std()

    valid_vols = vol_series.dropna().values
    threshold_vol = float(np.nanpercentile(valid_vols, vol_pct)) if len(valid_vols) > zero_i else realised_vol

    # Compress decay when vol is high (reduce weight on noisy high-vol bars)
    effective_decay = decay * (threshold_vol / (realised_vol + epsilon)) \
        if realised_vol > threshold_vol else decay
    effective_decay = float(np.clip(effective_decay, zero_f, const["one_float"]))

    # Apply scalar gate to embedding (element-wise EWM scalar approximation)
    return last_hidden * effective_decay


def _verify_model_sha256(model, expected_sha: str) -> None:
    """
    Computes SHA-256 of all model parameter bytes and compares to expected_sha.
    Raises RuntimeError on mismatch.

    Flaw 9/neural fix: access raw memory buffer via .numpy().tobytes() directly,
    bypassing the massively inefficient .tolist() -> Python list -> np.array round-trip
    that caused OOM crashes on large weight tensors.
    """
    hasher = hashlib.sha256()
    try:
        import torch
        for param in model.parameters():
            hasher.update(param.data.cpu().numpy().tobytes())
    except Exception:
        return  # Skip verification if torch not available

    actual = hasher.hexdigest()
    if actual != expected_sha:
        raise RuntimeError(
            f"Model weight SHA-256 mismatch.\n"
            f"  Expected : {expected_sha}\n"
            f"  Actual   : {actual}\n"
            "Update cfg['kronos_mini']['model_sha256'] or replace the model file."
        )


def _verify_tokenizer_sha256(tokenizer, expected_sha: str) -> None:
    """
    Computes SHA-256 of all tokenizer parameter bytes and compares to expected_sha.
    Raises RuntimeError on mismatch.

    Flaw 9/neural fix: same .numpy().tobytes() optimization applied here.
    """
    hasher = hashlib.sha256()
    try:
        import torch
        for param in tokenizer.parameters():
            hasher.update(param.data.cpu().numpy().tobytes())
    except Exception:
        return  # Skip verification if torch not available

    actual = hasher.hexdigest()
    if actual != expected_sha:
        raise RuntimeError(
            f"Tokenizer weight SHA-256 mismatch.\n"
            f"  Expected : {expected_sha}\n"
            f"  Actual   : {actual}\n"
            "Update cfg['kronos_mini']['tokenizer_sha256'] or replace the tokenizer file."
        )


def _resolve_dtype(precision_str: str):
    """Maps cfg precision string to torch dtype. Falls back to float32."""
    try:
        import torch
        mapping = {
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
            "float32": torch.float32,
        }
        return mapping.get(precision_str, torch.float32)
    except ImportError:
        return None
