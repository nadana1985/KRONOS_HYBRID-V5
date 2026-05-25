# Kronos-mini Neural Integration Layer

**File**: `KRONOS_MINI_INTEGRATION.md`  
**Status**: SOVEREIGN LOCKED — ZERO INLINE LITERAL DOCTRINE ENFORCED  
**Config Source**: Configuration dictionary loaded dynamically at runtime  
**Depends On**: `neural_integration_engine.py`

---

## Purpose

Defines the authoritative integration contract and inference pipeline interface between the KRONOS feature engine and the frozen `Kronos-mini` transformer model. Every model identifier, context window limit, bottleneck embedding dimension, precision parameter, decay weight, percentile gate, norm order, and file integrity checksum resolves exclusively via dynamic configurations. No inline numeric constants, PyTorch datatypes, or configuration values are hardcoded in this document or its engine code.

---

## True Reverse Engineering Pipeline — Neural Causal Flow

Canonical per-bar inference is **`neural_integration_engine.compute_neural_gate`**, which bundles verified model/tokenizer loading, pooled embedding extraction, `L_p` conviction, instantaneous-vol–scaled thresholding, and the boolean neural pass outcome.

Supporting helpers (`load_verified_*`, `extract_embeddings`, `compute_lp_norm`, `dynamic_threshold`) remain callable for tooling, but note that **`extract_embeddings` returns the volatility-gated pooled vector**: `_apply_vol_gated_pooling` is deliberately private inside `neural_integration_engine.py`.

```
══════════════════════════════════════════════════════════════════════════════════
KRONOS NEURAL INTEGRATION PIPELINE (bar t, structural veto already passed)
══════════════════════════════════════════════════════════════════════════════════

PRIMARY ENTRY POINT
  conviction, thresh, neural_passed, pooled_vec = neural_integration_engine.compute_neural_gate(
      causal_candles,
      current_idx,
      recent_convictions,               # pandas Series from feature_builder conviction buffer
      cfg["kronos_mini"],
      cfg["feature_builder"]["gate"],
      cfg["reproducibility"]["constants"],
  )

INTERNAL STAGES (automatic when using compute_neural_gate)
  model, tokenizer → load_verified_model / tokenizer (SHA checks when pinning on)
  pooled_vec       ← extract_embeddings(..., full_cfg stitching kronos_mini + reproducibility slices)
                       • builds causal tensors + stamps
                       • invokes frozen Kronos forwards + volatility-gated decay pooling
  conviction       ← compute_lp_norm(pooled_vec, synthetic_full_cfg)
  realised_vol     ← std of causal log closes up to bar t
  thresh           ← dynamic_threshold(recent_convictions, synthetic_full_cfg,
                                        current_timestamp, current_vol)
  neural_passed    ← conviction > thresh

══════════════════════════════════════════════════════════════════════════════════
```

---

## Model & Gating Configuration Map

All dimensions, precision keys, and pooling metrics are resolved dynamically.

| Property | Description | Config Reference Key |
| :--- | :--- | :--- |
| Model identifier | Frozen checkpoint directory / hub id | `cfg["kronos_mini"]["model_name"]` |
| Tokenizer identifier | Frozen tokenizer artefacts | `cfg["kronos_mini"]["tokenizer_name"]` |
| Model weight hash | SHA-256 checksum (when pinning on) | `cfg["kronos_mini"]["model_sha256"]` |
| Tokenizer file hash | SHA-256 checksum for packaged tokenizer files | `cfg["kronos_mini"]["tokenizer_sha256"]` |
| Context window | Bars ending at causal index `t` | `cfg["kronos_mini"]["context_length"]` |
| Embedding dimension | Neural slot spanning width | `cfg["kronos_mini"]["embedding_dim"]` |
| Tensor clip guard | Normalised OHLCV stabilisation clamp | `cfg["kronos_mini"]["clip"]` |
| Pooling envelope | Vol-gated pooling controls | `cfg["kronos_mini"]["pooling"]` |
| Precision | Dtype string for reproducibility | `cfg["reproducibility"]["precision"]` |
| L_p exponent | Conviction magnitude norm | `cfg["feature_builder"]["gate"]["norm_order"]` |
| Conviction deque window | Count window feeding median logic | `cfg["feature_builder"]["gate"]["recent_conviction_window"]` |
| Threshold multiplier | Scales backbone median convictions | `cfg["feature_builder"]["gate"]["conviction_multiplier"]` |
| Vol-linked multiplier | Additional scaling vs realised vol | `cfg["feature_builder"]["gate"]["conviction_vol_multiplier"]` |
| Vol factor clamps | Hard limits on multiplier swing | `cfg["feature_builder"]["gate"]["conviction_vol_clip_low"]`, `conviction_vol_clip_high` |
| Rolling history horizon | DAYS retained upstream (feature buffer) | `cfg["feature_builder"]["gate"]["conviction_time_window_days"]` |
| Baseline vol denominator | Threshold stabiliser when estimating vol-factor | `cfg["feature_builder"]["gate"]["baseline_vol"]` |
| Slot prefix | Column prefix for pooled embedding lanes | `cfg["kronos_mini"]["slot_key_prefix"]` |
| Slot start row | Embedding column offset | `cfg["kronos_mini"]["slot_start_idx"]` |

---

## Neural Integration Engine Interface

Typical callers should **`import neural_integration_engine` and delegate to `compute_neural_gate`**. The stubs below illustrate the authoritative Python surface without embedding inline literals beyond config references shown in prose.

```python
from typing import Dict, Tuple
import pandas as pd
import numpy as np

def load_sovereign_config(path: str) -> Dict:
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)

def load_verified_model(config: Dict):
    from neural_integration_engine import load_verified_model as _impl
    return _impl(config)


def load_verified_tokenizer(config: Dict):
    from neural_integration_engine import load_verified_tokenizer as _impl
    return _impl(config)


def compute_neural_gate(
    causal_candles: pd.DataFrame,
    current_idx: int,
    recent_convictions: pd.Series,
    kronos_cfg: Dict,
    gate_cfg: Dict,
    const: Dict,
) -> Tuple[float, float, bool, np.ndarray]:
    from neural_integration_engine import compute_neural_gate as _impl
    return _impl(causal_candles, current_idx, recent_convictions, kronos_cfg, gate_cfg, const)


def extract_embeddings(
    causal_candles: pd.DataFrame,
    current_idx: int,
    model,
    tokenizer,
    config: Dict,
) -> np.ndarray:
    """Returns pooled bottleneck vector (already volatility gated)."""
    from neural_integration_engine import extract_embeddings as _impl
    return _impl(causal_candles, current_idx, model, tokenizer, config)


def compute_lp_norm(embedding: np.ndarray, config: Dict) -> float:
    from neural_integration_engine import compute_lp_norm as _impl
    return _impl(embedding, config)


def dynamic_threshold(
    recent_convictions: pd.Series,
    config: Dict,
    current_timestamp=None,
    current_vol: float | None = None,
) -> float:
    from neural_integration_engine import dynamic_threshold as _impl
    return _impl(recent_convictions, config, current_timestamp, current_vol)
```

---

## Sovereignty Migration Path

> [!WARNING]
> **Active Hybrid Compromises**:
> - Frozen model checkpoints are dependent on floating-point precision configurations. Models executed in `float16` can experience weight representation errors on non-CUDA CPU platforms.
> - **PyTorch-Free Fallback Mode**: `neural_integration_engine.py` supports a graceful, high-performance fallback mechanism. If `torch` or `transformers` is unavailable on the local host machine, the engine intercepts the runtime error, falls back to a zeroed bottleneck vector, and assigns zero neural conviction. This prevents pipeline termination under lean or restricted CPU execution environments.
> - **Ablation Mode**: When hardware environments lack high-velocity execution support, bypass neural evaluation entirely by setting `cfg["miner"]["enable_kronos"]` to `False`, forcing the feature builder to evaluate structural veto compositions only.

---

**Hardcode Audit Passed — Zero Inline Literals**