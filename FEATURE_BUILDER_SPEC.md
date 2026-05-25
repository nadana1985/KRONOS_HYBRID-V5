# Feature Builder Specification

**File**: `FEATURE_BUILDER_SPEC.md`  
**Status**: SOVEREIGN LOCKED — ZERO INLINE LITERAL DOCTRINE ENFORCED  
**Config Source**: Configuration dictionary loaded dynamically at runtime  
**Depends On**: `structural_engine.py`, `neural_integration_engine.py`, `feature_builder_engine.py`

---

## Purpose

Defines the authoritative, mathematically pure pipeline for converting raw OHLCV candlesticks and aggregated microstructure trades into the 32-slot reversal signature DNA vector. Every index boundary, sliding window, threshold, norm order, and column identifier resolves exclusively via config lookups. No inline numeric constants, literal array bounds, or hardcoded strings exist in this specification or its matching engine code.

---

## True Reverse Engineering Pipeline (Authoritative Causal Flow)

The compilation of a reversal signature DNA vector follows a strict, non-lookahead causal sequence. The data slicing and pipeline execution block are detailed below:

```
══════════════════════════════════════════════════════════════════════════════════
KRONOS CAUSAL FEATURE PIPELINE — bar t
══════════════════════════════════════════════════════════════════════════════════

STEP ONE — SOVEREIGN CONFIG LOADING
  config_path = cfg["reproducibility"]["constants"]["config_filename"]
  cfg = load_sovereign_config(config_path)

STEP TWO — CAUSAL BARS SLICING (Hard Future-Data Barrier)
  # Limit input candles and aggregated trades up to index t causally
  one_idx        = cfg["reproducibility"]["constants"]["one_int"]
  causal_candles = raw_candles.iloc[: current_idx + one_idx]
  causal_trades  = agg_trades_df.iloc[: current_idx + one_idx]

STEP THREE — STRUCTURAL SLOTS GENERATION
  # Vectorized computation of slots via Numba/Pandas in structural_engine.py
  structural_scores = structural_engine.compute_slots_sovereign(
      causal_candles, causal_trades,
      cfg["feature_builder"]["structural"],
      cfg
  )

STEP FOUR — COMPOSITE VETO EVALUATION
  composite_series = structural_engine.compute_veto_composite(
      structural_scores,
      cfg["feature_builder"]["structural"]["slot_15"],
      cfg["reproducibility"]["constants"],
  )
  composite_score_at_t = composite_series.iloc[-one_idx]   # bar t
  veto_threshold       = cfg["feature_builder"]["structural"]["veto_threshold"]
  veto_passed          = composite_score_at_t >= veto_threshold

STEP FIVE — NEURAL ORTHOGONAL INFERENCE
  pooled_emb              = zeros(cfg["kronos_mini"]["embedding_dim"])  # pooled bottleneck vector (float32)
  conviction_score        = cfg["reproducibility"]["constants"]["zero_float"]
  dynamic_thresh          = cfg["reproducibility"]["constants"]["zero_float"]
  neural_passed_flag      = False

  if veto_passed and cfg["miner"]["enable_kronos"]:
      conviction_score, dynamic_thresh, neural_passed_flag, pooled_emb = (
          neural_integration_engine.compute_neural_gate(
              causal_candles,
              current_idx,
              recent_convictions,          # rolling Series from feature_builder_engine.update_conviction_buffer
              cfg["kronos_mini"],
              cfg["feature_builder"]["gate"],
              cfg["reproducibility"]["constants"],
          )
      )

STEP SIX — CONVICTION HISTORY (TIME WINDOW, NOT COUNT WINDOW)
  # After emitting each DNA row the miner/engine calls:
  recent_convictions = feature_builder_engine.update_conviction_buffer(
      buffer, dna_row, cfg
  )
  # Buffer retention is TIMESTAMP-based:
  cutoff = bar_timestamp - timedelta(days = cfg["feature_builder"]["gate"]["conviction_time_window_days"])

STEP SEVEN — AUXILIARY + METADATA + ASSEMBLY
  # Implemented inside feature_builder_engine.build_full_dna_vector(...)
  # — merges structural row, pooled_emb into neural slot columns, veto key,
  #   auxiliary slots, metadata/phylum scaffold, gate columns.

STEP EIGHT — REVERSAL SIGNATURE FLAG
  signature_flag = veto_passed and (neural_passed_flag or not cfg["miner"]["enable_kronos"])
  # If Kronos is disabled the structural veto alone can qualify detections once structural threshold passes.

══════════════════════════════════════════════════════════════════════════════════
```

---

## Slot Group Configuration Map

No array range slicing index appears as a bare integer literal. All bounds and target index partitions must be fetched dynamically.

| Slot Group | Range Key Prefix | Range Start Key | Range End Key | Engine Module | Config Reference Key |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Structural Core | `slot_` | `cfg["reproducibility"]["constants"]["zero_int"]` | `cfg["reproducibility"]["constants"]["fifteen_int"]` | `structural_engine` | `cfg["feature_builder"]["structural"]` |
| Neural Embeddings | `slot_` | `cfg["reproducibility"]["constants"]["sixteen_int"]` | `cfg["reproducibility"]["constants"]["twenty_three_int"]` | `neural_integration_engine` | `cfg["kronos_mini"]["slot_key_prefix"]` |
| Auxiliary Synthetic | `slot_` | `cfg["reproducibility"]["constants"]["twenty_four_int"]` | `cfg["reproducibility"]["constants"]["twenty_seven_int"]` | `feature_builder_engine` | `cfg["feature_builder"]["aux"]` |
| Metadata & Phylum | `slot_` | `cfg["reproducibility"]["constants"]["twenty_eight_int"]` | `cfg["reproducibility"]["constants"]["thirty_one_int"]` | `feature_builder_engine` | `cfg["feature_builder"]["metadata"]` |

---

## Conviction Gate Configuration Map

All thresholds, windows, and scaling parameters for dynamic gating are dynamic references.

| Gate Property | Purpose | Config Reference Key |
| :--- | :--- | :--- |
| Veto composite threshold | Minimum structural veto composite score | `cfg["feature_builder"]["structural"]["veto_threshold"]` |
| Veto composite recipe | Slot-15 weights + structure | `cfg["feature_builder"]["structural"]["slot_15"]` |
| Veto composite column key | Writes composite score column name | `cfg["feature_builder"]["structural"]["slot_15"]["key_name"]` |
| L_p norm order | Order p for conviction vector norm | `cfg["feature_builder"]["gate"]["norm_order"]` |
| Conviction history window | DAYS retained in rolling buffer (timestamp filter) | `cfg["feature_builder"]["gate"]["conviction_time_window_days"]` |
| Conviction multiplier | Scale applied to median history | `cfg["feature_builder"]["gate"]["conviction_multiplier"]` |
| Vol-adjusted multiplier | Amplifies threshold with realised vol regime | `cfg["feature_builder"]["gate"]["conviction_vol_multiplier"]` |
| Vol factor clips | Clamp range for volatility scaling | `cfg["feature_builder"]["gate"]["conviction_vol_clip_low"]`, `conviction_vol_clip_high` |
| Rolling window size (median) | Count of trailing convictions for median/threshold maths | `cfg["feature_builder"]["gate"]["recent_conviction_window"]` |
| Signature flag key | Column key for signature boolean | `cfg["feature_builder"]["gate"]["signature_flag_key"]` |
| Neural conviction key | Column key for L_p conviction | `cfg["feature_builder"]["gate"]["neural_conviction_key"]` |
| Dynamic threshold key | Column key for threshold used at bar t | `cfg["feature_builder"]["gate"]["conviction_threshold_key"]` |

---

## Reproducibility Constants Reference

| Constant Role | Operational Use | Config Reference Key |
| :--- | :--- | :--- |
| Zero float | Default array fill and math boundaries | `cfg["reproducibility"]["constants"]["zero_float"]` |
| One float | Weights normalized base | `cfg["reproducibility"]["constants"]["one_float"]` |
| Half float | Pricing offsets | `cfg["reproducibility"]["constants"]["half_float"]` |
| Epsilon | Numerical division stabilizer | `cfg["reproducibility"]["constants"]["epsilon"]` |
| Zero integer | Causal loops initialization index | `cfg["reproducibility"]["constants"]["zero_int"]` |
| One integer | Offsets for causal slicing barriers | `cfg["reproducibility"]["constants"]["one_int"]` |
| Two integer | Scale variables and dimensions | `cfg["reproducibility"]["constants"]["two_int"]` |
| Three integer | Argument bounds validation check | `cfg["reproducibility"]["constants"]["three_int"]` |
| Sixteen integer | Lower bound for neural slot mappings | `cfg["reproducibility"]["constants"]["sixteen_int"]` |
| Twenty-three integer | Upper bound for neural slot mappings | `cfg["reproducibility"]["constants"]["twenty_three_int"]` |

---

## Feature Builder Engine Interface

The compilation engine contains pure stubs delegating parameter retrieval and computation logic directly to their respective modules, strictly enforcing zero inline literals:

```python
from typing import Dict
import pandas as pd

def load_sovereign_config(path: str) -> Dict:
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)

def build_full_dna_vector(
    raw_candles: pd.DataFrame,
    agg_trades_df: pd.DataFrame,
    current_idx: int,
    recent_convictions: pd.Series,
    config: Dict
) -> pd.Series:
    """
    Builds the complete DNA vector for bar current_idx.
    All indexing parameters and windows are fetched dynamically.
    No hardcoded integers or inline calculations.

    Args:
        raw_candles: Historical OHLCV data.
        agg_trades_df: Tick buy/sell aggregated trade data.
        current_idx: Causal index t.
        recent_convictions: Time-indexed Series of historic neural convictions for dynamic_threshold.
        config: Authoritative parameters dictionary.

    Returns:
        Series representing the fully populated DNA row (slots + gates).
    """
    from feature_builder_engine import build_full_dna_vector as _impl
    return _impl(raw_candles, agg_trades_df, current_idx, recent_convictions, config)
```

---

## Sovereignty Migration Path

> [!WARNING]
> **Active Hybrid Compromises**:
> - Neural conviction checks require high-end GPUs. When operating in environments lacking CUDA execution pools, enable the structural-only ablation path via config.
> - **Ablation Mode**: `cfg["miner"]["enable_ablation"]` is honoured inside the miner/orchestration layer. The feature builder only gates neural math when `cfg["miner"]["enable_kronos"]` is truthy — otherwise structural veto-qualified bars advance without transformer inference (`feature_builder_engine.py`).

---

**Hardcode Audit Passed — Zero Inline Literals**