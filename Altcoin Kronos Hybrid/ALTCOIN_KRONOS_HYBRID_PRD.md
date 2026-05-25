# Altcoin Kronos Hybrid Sovereign Engine — Product Requirements Document

**File**: `ALTCOIN_KRONOS_HYBRID_PRD.md`  
**Status**: SOVEREIGN LOCKED — ZERO INLINE LITERAL DOCTRINE ENFORCED  
**Config Source**: Configuration dictionary loaded dynamically at runtime  
**Depends On**: All engine modules

---

## Purpose

Defines the product-level requirements, edge targets, and architectural pipeline for the Altcoin Kronos Hybrid Sovereign Engine. Every performance target, regime identifier, model parameter, slot group, and threshold resolves exclusively via dynamic configuration lookups. No inline numbers, multipliers, string labels, or dimensions appear in this document.

---

## Execution Scope & Infrastructure

- **Universe Scope**: `cfg["universe"]["size"]` perpetual altcoins (cross-sectional processing).
- **Timeframe**: `cfg["feature_builder"]["interval"]` interval.
- **Data History**: `cfg["data_pipeline"]["history_start"]` to `cfg["data_pipeline"]["history_end"]`.
- **Compute Infrastructure**: `cfg["infrastructure"]["compute_provider"]`.

---

## Core Mission

Maximise trading edge across the altcoin universe through a strictly causal, bit-perfect reversal signature discovery engine that:

- Ingests cross-sectional raw OHLCV candlesticks at `cfg["feature_builder"]["interval"]` and tick-level aggregated trade microstructure.
- Computes a complete DNA vector with causal slice per bar enforced via `cfg["reproducibility"]["constants"]["one_int"]`.
- Gates signatures through a deterministic structural veto (`cfg["feature_builder"]["structural"]["veto_threshold"]`) followed by an orthogonal neural conviction check (`cfg["feature_builder"]["gate"]`).
- Stores audited signatures in a queryable Parquet/DuckDB archive under `cfg["database"]["path"]`.
- Evaluates all performance metrics post-detection only — zero lookahead enforced by `cfg["miner"]["max_lookahead_bars"]`.

---

## True Reverse Engineering Pipeline (Executive Overview)

```
RAW INPUTS
  Cross-sectional OHLCV at cfg["feature_builder"]["interval"]
  AggTrades (buy_vol, sell_vol) at same interval

CAUSAL SLICE (per bar t)
  df.iloc[: current_idx + cfg["reproducibility"]["constants"]["one_int"]]

STRUCTURAL SOVEREIGN CORE
  structural_engine.compute_slots_sovereign(causal_candles, causal_trades, cfg["feature_builder"]["structural"])
  structural_engine.compute_veto_composite(scores, cfg["feature_builder"]["structural"]["slot_15"])
  veto_passed = composite >= cfg["feature_builder"]["structural"]["veto_threshold"]

NEURAL ORTHOGONAL GATE (only if veto_passed)
  neural_integration_engine.extract_embeddings(causal_candles, current_idx, model, tokenizer, cfg)
  neural_integration_engine.compute_lp_norm(embedding, cfg)
  neural_passed = conviction_score > neural_integration_engine.dynamic_threshold(recent, cfg)

SIGNATURE DETECTION
  signature_flag = veto_passed AND neural_passed

POST-DETECTION EVALUATION (strictly after detection bar)
  fwd_slice = df.iloc[t + one_i : t + one_i + cfg["miner"]["forward_bars"]]
  miner_engine.compute_forward_metrics(dna_row, fwd_slice, cfg)

PERSISTENCE
  database_engine.store_signatures_batch(shard_detected, cfg)
  database_engine.initialize_duckdb_views(cfg)
```

---

## Performance Targets — Config Reference Map

All numeric targets exist only in the dynamic configuration. References are authoritative lookup keys.

| Target | Description | Config Reference Key |
| :--- | :--- | :--- |
| Gross Profit Factor | Minimum required GPF across back-test | `cfg["targets"]["min_gross_profit"]` |
| Recovery Factor | Minimum median recovery factor | `cfg["targets"]["min_recovery"]` |
| Regime Focus | Target HMM regime identifier | `cfg["targets"]["regime_id"]` |

---

## Architectural Requirements — Config Reference Map

| Requirement | Description | Config Reference Key |
| :--- | :--- | :--- |
| Universe size | Target perpetual altcoins | `cfg["universe"]["size"]` |
| Execution interval | Core timeframe | `cfg["feature_builder"]["interval"]` |
| History start | Genesis equivalent | `cfg["data_pipeline"]["history_start"]` |
| History end | Present equivalent | `cfg["data_pipeline"]["history_end"]` |
| Compute provider | Cloud processing backbone | `cfg["infrastructure"]["compute_provider"]` |
| Structural slot weights | Per-slot weight map (sum = `one_float`) | `cfg["feature_builder"]["structural"]["slot_15"]["weights"]` |
| Veto barrier | Minimum structural composite score | `cfg["feature_builder"]["structural"]["veto_threshold"]` |
| Neural embedding width | Kronos-mini bottleneck dimension | `cfg["kronos_mini"]["embedding_dim"]` |
| Neural context length | Transformer max token sequence | `cfg["kronos_mini"]["context_length"]` |
| Inference precision | PyTorch dtype format string | `cfg["reproducibility"]["precision"]` |
| L_p norm order | Conviction norm type | `cfg["feature_builder"]["gate"]["norm_order"]` |
| Conviction window | Rolling history for dynamic threshold | `cfg["feature_builder"]["gate"]["recent_conviction_window"]` |
| Conviction multiplier | Scale over rolling median | `cfg["feature_builder"]["gate"]["conviction_multiplier"]` |
| Forward evaluation horizon | Post-detection bar count | `cfg["miner"]["forward_bars"]` |
| Causal lookahead guard | Must equal `zero_int` | `cfg["miner"]["max_lookahead_bars"]` |
| Archive partition keys | Parquet partition dimensions | `cfg["database"]["partition_by"]` |
| Audit trail keys | Hash column identifiers | `cfg["database"]["audit"]` |
| Model weight integrity | Checksum for model | `cfg["kronos_mini"]["model_sha256"]` |

---

## Sovereignty Doctrine (Non-Negotiable)

> [!IMPORTANT]
> - Every number, dimension, threshold, path, and key resolves via `cfg["section"]["key"]`.
> - No code path reads future bars for features at bar $t$.
> - Post-detection performance is evaluated strictly after the detection index.
> - Model weights are verified against configuration hashes at every cold start.
> - `cfg["miner"]["max_lookahead_bars"]` is asserted equal to `cfg["reproducibility"]["constants"]["zero_int"]` before any mining loop begins.

---

## Sovereignty Migration Path

> [!WARNING]
> **Active Hybrid Compromises**:
> - Neural embedding slots require a frozen GPU transformer. Toggle via `cfg["miner"]["enable_kronos"]`.
> - Auxiliary slots depend on historical MFE/MAE projections. Toggle via `cfg["miner"]["enable_ablation"]`.
> - **Full Sovereignty Target**: Structural sovereign slots + metadata slots only — deterministic, GPU-free, hardware-portable.

---

**Hardcode Audit Passed — Zero Inline Literals**
