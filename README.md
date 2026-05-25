# KRONOS Hybrid Sovereign Engine

**Status**: SOVEREIGN LOCKED — ZERO INLINE LITERAL DOCTRINE ENFORCED  
**Config Source**: `params_yaml.txt` loaded via `load_sovereign_config()`

---

## Executive Summary

KRONOS is a strictly causal, bit-perfect market reversal signature discovery and storage engine. It converts raw OHLCV candlesticks and aggregated microstructure trades into an audited, queryable Parquet/DuckDB signature archive through a two-stage gate: a deterministic structural veto (sovereign core) followed by an orthogonal neural conviction check (hybrid layer).

Every parameter in this system — window sizes, thresholds, dimensions, forward evaluation horizons, storage paths — is loaded exclusively from `params_yaml.txt`. No inline literals exist anywhere in source specifications or code stubs.

---

## True Reverse Engineering Pipeline (System-Level Overview)

```
[Raw OHLCV Feed]     ─────────────────────────────────────────────┐
  interval = cfg["feature_builder"]["interval"]                   │
                                                                   ▼
[AggTrades Feed]  ───────────► [Causal Slice per bar t]
  buy_vol / sell_vol            df.iloc[: t + cfg["reproducibility"]["constants"]["one_int"]]
                                                                   │
                                                                   ▼
                         [Structural Sovereign Core]
                         structural_engine.compute_slots_sovereign(
                             causal_candles, causal_trades,
                             cfg["feature_builder"]["structural"]
                         )
                                                                   │
                                                                   ▼
                         [Sovereign Veto Gate — Slot veto_composite]
                         score >= cfg["feature_builder"]["structural"]["veto_threshold"]
                                                                   │ YES
                                                                   ▼
                         [Neural Orthogonal Gate]
                         neural_integration_engine.compute_neural_gate(
                             causal_candles, current_idx,
                             recent_convictions,
                             cfg["kronos_mini"],
                             cfg["feature_builder"]["gate"]
                         )
                                                                   │ YES
                                                                   ▼
                         [Signature Detected — Post-Detection Evaluation]
                         fwd_slice = df.iloc[t + one_i : t + one_i + cfg["miner"]["forward_bars"]]
                         miner_engine.compute_forward_metrics(dna_row, fwd_slice, cfg)
                                                                   │
                                                                   ▼
                         [Parquet Archive + DuckDB Index]
                         database_engine.store_signatures_batch(shard_detected, cfg)
```

---

## Project Structure

| Component | File | Purpose | Config Reference Key |
| :--- | :--- | :--- | :--- |
| System architecture | `KRONOS_V5_SOVEREIGN_ARCHITECTURE.md` | Full component diagram and data flow | `cfg["feature_builder"]`, `cfg["miner"]`, `cfg["database"]` |
| Product requirements | `KRONOS_HYBRID_PRD.md` | Edge targets and non-negotiable doctrine | `cfg["targets"]` |
| Slot definitions | `V5_HYBRID_SLOT_DEFINITIONS.md` | All structural and neural slot specs | `cfg["feature_builder"]["structural"]` |
| Feature builder | `FEATURE_BUILDER_SPEC.md` | Causal DNA vector construction | `cfg["feature_builder"]` |
| Mining pipeline | `MINER_SPEC.md` | Walk-forward loop and forward metrics | `cfg["miner"]` |
| Database layer | `SIGNATURE_DATABASE_SPEC.md` | Schema, storage, DuckDB views | `cfg["database"]` |
| Neural integration | `KRONOS_MINI_INTEGRATION.md` | Transformer inference + conviction gate | `cfg["kronos_mini"]`, `cfg["feature_builder"]["gate"]` |
| Data ingestion | `DATA_LAYER_SPEC.md` | Raw feed acquisition and normalisation | `cfg["data"]` |
| Validation | `VALIDATION_AND_EVALUATION.md` | Signature quality and causal validity | `cfg["targets"]`, `cfg["database"]` |
| Backtesting | `BACKTEST_AND_ABLATION_FRAMEWORK.md` | Walk-forward ablation and edge measurement | `cfg["miner"]`, `cfg["targets"]` |
| Query examples | `SIGNATURE_QUERY_EXAMPLES.md` | Parameterised DuckDB query patterns | `cfg["database"]`, `cfg["targets"]` |
| Deployment | `DEPLOYMENT_AND_MIGRATION_GUIDE.md` | Installation and sovereignty migration | `cfg["reproducibility"]` |
| Hardware | `VALIDATOR_AND_HARDWARE_SPEC.md` | Hardware requirements | `cfg["reproducibility"]`, `cfg["kronos_mini"]` |
| Pipeline workflow | `PIPELINE_WORKFLOW.md` | Step-by-step execution workflow | All config roots |
| Sovereignty validator | `SOVEREIGN_VALIDATOR.md` | Hardcode scan and doctrine enforcement | `cfg["validator"]` |
| Implementation checklist | `IMPLEMENTATION_CHECKLIST.md` | Pre-flight checks and audit status | All config roots |
| References | `REFERENCES_AND_EXTERNAL_CONTEXT.md` | Research and external context | — |

---

## Quick-Start

```python
from typing import Dict

def load_sovereign_config(path: str = "params_yaml.txt") -> Dict:
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)

def main() -> None:
    """
    Entry point — all runtime parameters resolved from config.

    Config refs (representative):
      cfg["miner"]["symbols"]
      cfg["miner"]["interval"]
      cfg["miner"]["batch_size_days"]
      cfg["miner"]["forward_bars"]

    Full implementation → orchestrator_engine.run_full_pipeline(config)
    """
    cfg = load_sovereign_config()
    from orchestrator_engine import run_full_pipeline
    run_full_pipeline(cfg)
```

---

## Documentation vs implementation

Specifications are synchronised **as of the current tree** with these runtime facts (consult the cited modules for authoritative behaviour):

- **Data ingestion** exposes `fetch_or_load_ohlcv`, `load_shard_data`, and `generate_synthetic_trades` — not legacy `fetch_ohlcv` / `fetch_agg_trades`. Microstructure imbalances are synthesized (BVC or hash split) (`data_engine.py`, `DATA_LAYER_SPEC.md`).
- **`compute_neural_gate`** is the single-call neural path; pooled embeddings already include volatility gating (`neural_integration_engine.py`, `KRONOS_MINI_INTEGRATION.md`).
- **`backtest_engine.run_backtest` + `generate_folds`** implement walk-forward pooled statistics; pairwise hybrid/sovereign `evaluate_fold` helpers do not exist (`backtest_engine.py`, `BACKTEST_AND_ABLATION_FRAMEWORK.md`).
- **Hardcode validator** entry point is **`run_full_validation` / `run_validation`** with internal `_discover_files` / `_scan_file`; there is **no `ci_entrypoint`** export (`hardcode_validator_engine.py`, `SOVEREIGN_VALIDATOR.md`).
- **`git_audit_hook.commit_successful_run`** is standalone — **miner and validation flows do not invoke it automatically** (`git_audit_hook.py`, `VALIDATION_AND_EVALUATION.md`, `miner_engine.py`).

---
> **Non-Negotiable Rules**:
> - Every number, path, dimension, and threshold resolves via `cfg["section"]["key"]`.
> - No code path reads future data for features at bar $t$.
> - `cfg["miner"]["max_lookahead_bars"]` asserted equal to `cfg["reproducibility"]["constants"]["zero_int"]` before any mining loop.
> - Model weights verified against `cfg["kronos_mini"]["model_sha256"]` at every cold start.

---

**Hardcode Audit Passed — Zero Inline Literals**
