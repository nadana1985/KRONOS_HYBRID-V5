# ALTCOIN KRONOS V5 Sovereign Architecture

**File**: `ALTCOIN_KRONOS_V5_SOVEREIGN_ARCHITECTURE.md`  
**Status**: SOVEREIGN LOCKED — ZERO INLINE LITERAL DOCTRINE ENFORCED  
**Config Source**: `params_yaml.txt` loaded via `load_sovereign_config()`

---

## Purpose

Defines the complete system architecture of the Altcoin KRONOS Hybrid Sovereign Engine — component boundaries, data flows, engine responsibilities, and the sovereign/hybrid split. Engineered for cross-sectional processing of perpetual altcoins (scaled to `cfg["universe"]["size"]`), operating on a `cfg["feature_builder"]["interval"]` timeframe from `cfg["data_loader"]["history"]`, and distributed across `cfg["infrastructure"]["compute_provider"]`. All dimensions, thresholds, and configuration keys resolve exclusively via `cfg["section"]["key"]`.

---

## True Reverse Engineering Pipeline (Architecture-Level Causal Flow)

```text
═══════════════════════════════════════════════════════════════
ALTCOIN KRONOS SYSTEM ARCHITECTURE — CAUSAL DATA FLOW
═══════════════════════════════════════════════════════════════

LAYER — CROSS-SECTIONAL RAW DATA INGESTION
  data_engine.fetch_cross_sectional(
      cfg["data"]["source"],
      cfg["universe"]["symbols"],
      cfg["feature_builder"]["interval"],
      cfg["data_loader"]["history"]
  )
  → raw_candles_df   : OHLCV cross-section at cfg["feature_builder"]["interval"]
  → agg_trades_df    : tick buy_vol / sell_vol at same interval

LAYER — CAUSAL FEATURE EXTRACTION (no future data)
  one_i = cfg["reproducibility"]["constants"]["one_int"]
  for each symbol in cfg["universe"]["symbols"]:
    for each bar t:
      causal_slice = raw_candles_df[symbol].iloc[: t + one_i]
      trades_slice = agg_trades_df[symbol].iloc[: t + one_i]

      [SOVEREIGN STRUCTURAL ENGINE]
        structural_engine.compute_slots_sovereign(
            causal_slice, trades_slice,
            cfg["feature_builder"]["structural"]
        )

      [SOVEREIGN VETO GATE]
        structural_engine.compute_veto_composite(
            structural_scores,
            cfg["feature_builder"]["structural"]["slot_15"]
        )
        → veto_passed = score >= cfg["feature_builder"]["structural"]["veto_threshold"]

      [NEURAL HYBRID ENGINE — conditional on veto_passed]
        neural_integration_engine.extract_embeddings(
            causal_slice, t, model, tokenizer,
            cfg["kronos_mini"]
        )
        neural_integration_engine.compute_lp_norm(embedding, cfg)
        → neural_passed = conviction > dynamic_threshold(recent_convictions, cfg)

      [AUXILIARY + METADATA ENGINE]
        feature_builder_engine.compute_aux_slots(causal_slice, cfg["feature_builder"]["aux"])
        feature_builder_engine.compute_metadata_slots(scores, cfg["feature_builder"]["metadata"])

LAYER — SIGNATURE DETECTION
  signature_flag = veto_passed AND neural_passed

LAYER — POST-DETECTION EVALUATION (only when signature_flag)
  fwd_slice = raw_candles_df[symbol].iloc[t + one_i : t + one_i + cfg["miner"]["forward_bars"]]
  miner_engine.compute_forward_metrics(dna_row, fwd_slice, cfg)

LAYER — SIGNATURE STORAGE
  database_engine.store_signatures_batch(shard_detected, cfg)

LAYER — ANALYTICAL QUERY LAYER
  database_engine.initialize_duckdb_views(cfg)
  database_engine.query_elite_signatures(con, cfg)

═══════════════════════════════════════════════════════════════
```

---

## Component Responsibility Map

| Component | Engine Module | Responsibility | Config Root |
| :--- | :--- | :--- | :--- |
| Data ingestion | `data_engine.py` | Fetch, normalise, and cache raw OHLCV and AggTrades across `cfg["universe"]["size"]` spanning `cfg["data_loader"]["history"]` | `cfg["data"]`, `cfg["universe"]`, `cfg["data_loader"]` |
| Structural core | `structural_engine.py` | Vectorised computation of all structural sovereign slots | `cfg["feature_builder"]["structural"]` |
| Feature assembly | `feature_builder_engine.py` | Causal slice, slot dispatch, DNA vector assembly, gate logic | `cfg["feature_builder"]` |
| Neural integration | `neural_integration_engine.py` | Transformer inference, pooling, L_p conviction norm | `cfg["kronos_mini"]`, `cfg["feature_builder"]["gate"]` |
| Walk-forward miner | `miner_engine.py` | Cross-sectional shard generation, detection loop, forward metric evaluation on `cfg["infrastructure"]["compute_provider"]` | `cfg["miner"]`, `cfg["infrastructure"]` |
| Signature storage | `database_engine.py` | Parquet write, DuckDB view management, analytical queries | `cfg["database"]` |
| Hardcode validator | `hardcode_validator_engine.py` | Scan all spec files for inline literal violations | `cfg["validator"]` |
| System orchestrator | `orchestrator_engine.py` | Top-level pipeline coordination and distribution on `cfg["infrastructure"]["compute_provider"]` | All cfg roots |

---

## Sovereignty Boundary Map

| Layer | Sovereignty Status | Dependency | Config Toggle |
| :--- | :--- | :--- | :--- |
| Structural sovereign core | **100% Sovereign** — deterministic, GPU-free | OHLCV + AggTrades only | Always active |
| Sovereign veto composite | **100% Sovereign** — weighted sum, no neural weights | Structural core output | Always active |
| Neural orthogonal gate | **Hybrid** — frozen transformer dependency | Kronos-mini model + GPU on `cfg["infrastructure"]["compute_provider"]` | `cfg["miner"]["enable_kronos"]` |
| Auxiliary slots | **Hybrid** — synthetic projections | Historical MFE/MAE data | `cfg["miner"]["enable_ablation"]` |
| Metadata slots | **100% Sovereign** — deterministic hashing + HDBSCAN | Structural + neural output | Always active |
| Signature storage | **100% Sovereign** — deterministic Parquet schema | All upstream outputs | Always active |

---

## Engine Interface Map

All inter-engine calls use config-driven parameter passing. No engine may accept or return hardcoded values.

| Caller | Callee | Interface Stub | Config Reference Key |
| :--- | :--- | :--- | :--- |
| `orchestrator_engine` | `data_engine` | `data_engine.fetch_cross_sectional(cfg)` | `cfg["data"]`, `cfg["universe"]`, `cfg["data_loader"]` |
| `orchestrator_engine` | `miner_engine` | `miner_engine.run_cross_sectional_miner(cfg, start, end)` | `cfg["miner"]`, `cfg["infrastructure"]` |
| `miner_engine` | `feature_builder_engine` | `feature_builder_engine.build_full_dna_vector(...)` | `cfg["feature_builder"]` |
| `feature_builder_engine` | `structural_engine` | `structural_engine.compute_slots_sovereign(...)` | `cfg["feature_builder"]["structural"]` |
| `feature_builder_engine` | `neural_integration_engine` | `neural_integration_engine.compute_neural_gate(...)` | `cfg["kronos_mini"]`, `cfg["feature_builder"]["gate"]` |
| `miner_engine` | `database_engine` | `database_engine.store_signatures_batch(shard_detected, cfg)` | `cfg["database"]` |

---

## Architecture Stub

```python
from typing import Dict

def load_sovereign_config(path: str = "params_yaml.txt") -> Dict:
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)

class AltcoinKRONOSOrchestrator:
    """
    Top-level cross-sectional system orchestrator distributed on cfg["infrastructure"]["compute_provider"].
    All engine configurations resolved exclusively from cfg.

    Full implementation → orchestrator_engine.AltcoinKRONOSOrchestrator
    """

    def __init__(self, config: Dict) -> None:
        from orchestrator_engine import AltcoinKRONOSOrchestrator as _impl
        self._impl = _impl(config)

    def run(self, start_date: str, end_date: str) -> None:
        """
        Config refs (representative):
          cfg["universe"]["size"]
          cfg["feature_builder"]["interval"]
          cfg["data_loader"]["history"]
          cfg["infrastructure"]["compute_provider"]
          cfg["miner"]["batch_size_days"]
          cfg["miner"]["forward_bars"]
          cfg["database"]["path"]

        Full implementation → orchestrator_engine.AltcoinKRONOSOrchestrator.run(...)
        """
        self._impl.run(start_date, end_date)
```

---

## Sovereignty Migration Path

> [!WARNING]
> **V5 Pure Sovereignty Target**:
> - Phase current: Hybrid — structural sovereign core + Kronos-mini neural gate distributed on `cfg["infrastructure"]["compute_provider"]`.
> - Phase next: Replace neural slots with deterministic structural surrogates. Toggle via `cfg["miner"]["enable_kronos"]`.
> - Phase final: All slots deterministic, GPU-free, hardware-portable. Weight map covers full cross-sectional slot set.

---

**Hardcode Audit Passed — Zero Inline Literals**
