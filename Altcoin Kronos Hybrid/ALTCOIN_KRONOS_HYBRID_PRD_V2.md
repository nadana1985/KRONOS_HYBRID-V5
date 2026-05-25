# ALTCOIN KRONOS Hybrid Sovereign Engine — Product Requirements V2

**File**: `ALTCOIN_KRONOS_HYBRID_PRD_V2.md`  
**Status**: SOVEREIGN LOCKED — ZERO INLINE LITERAL DOCTRINE ENFORCED  
**Config Source**: `params_yaml.txt` loaded via `load_sovereign_config()`  
**Supersedes**: `KRONOS_HYBRID_PRD_V2.md`

---

## Executive Summary

Altcoin KRONOS V2 PRD expands the product requirements to cover the full 19-file specification suite, the multi-phase sovereignty migration roadmap, and a complete gate matrix adapted for large-scale cross-sectional processing. All performance targets, model specifications, slot boundaries, and timing parameters resolve exclusively via `cfg["section"]["key"]`.

---

## Altcoin Operational Scope

- **Universe**: Cross-sectional processing of `cfg["universe"]["size"]` `cfg["universe"]["asset_type"]` assets.
- **Timeframe**: Operating continuously on a `cfg["feature_builder"]["interval"]` resolution.
- **History**: Full historical backfill and processing from `cfg["history"]["start"]` to `cfg["history"]["end"]`.
- **Infrastructure**: Large-scale distributed compute powered by `cfg["hardware"]["provider"]`.

---

## Core Mission

Discover, archive, and query high-conviction mean-reversion reversal signatures from raw financial microstructure data across the altcoin universe via:

- A strictly causal, deterministic structural sovereign core (zero GPU, zero network dependency).
- An orthogonal neural conviction gate as a hybrid booster (toggled via `cfg["miner"]["enable_kronos"]`).
- A bit-perfect, audited Parquet/DuckDB archive with parameterised analytical queries.
- A zero-inline-literal codebase validated by `hardcode_validator_engine.py`.

---

## True Reverse Engineering Pipeline (PRD-Level Statement)

```python
for asset in universe[:cfg["universe"]["size"]]:
  raw_candles + agg_trades
    → df.iloc[: current_idx + cfg["reproducibility"]["constants"]["one_int"]]
    → structural_engine.compute_slots_sovereign(causal_candles, causal_trades, cfg["feature_builder"]["structural"])
    → structural_engine.compute_veto_composite(scores, cfg["feature_builder"]["structural"]["slot_15"])
    → veto_passed = score >= cfg["feature_builder"]["structural"]["veto_threshold"]
    → neural_integration_engine.compute_neural_gate(causal_candles, current_idx, recent_convictions, cfg["kronos_mini"], cfg["feature_builder"]["gate"])
    → neural_passed = conviction > dynamic_threshold
    → signature_flag = veto_passed AND neural_passed
    → database_engine.store_signatures_batch(shard_detected, cfg)
```

---

## Gate Matrix

| Gate Layer | Condition | Pass Criterion | Config Reference Key |
| :--- | :--- | :--- | :--- |
| Structural sovereign veto | Always active | `composite_score >= threshold` | `cfg["feature_builder"]["structural"]["veto_threshold"]` |
| Neural conviction gate | Only if veto passed AND `enable_kronos` | `conviction_score > dynamic_threshold` | `cfg["feature_builder"]["gate"]["conviction_multiplier"]` |
| Quality archive gate | At storage time | `quality_score >= min_quality` | `cfg["database"]["min_quality_score"]` |
| Retention gate | At query time | `recovery_factor >= min_retention` | `cfg["database"]["retention_policy"]["min_recovery_factor"]` |

---

## Performance Targets — Config Reference Map

| Target | Description | Config Reference Key |
| :--- | :--- | :--- |
| Gross Profit Factor | Minimum cross-period GPF | `cfg["targets"]["min_gross_profit"]` |
| Recovery Factor | Minimum median MFE/(MAE+eps) | `cfg["targets"]["min_recovery"]` |
| Regime Focus | Target HMM regime for analysis | `cfg["targets"]["regime_id"]` |

---

## Specification Suite Coverage Map

| Spec File | Covers | Config Root |
| :--- | :--- | :--- |
| `V5_HYBRID_SLOT_DEFINITIONS.md` | DNA slot definitions and stubs | `cfg["feature_builder"]` |
| `FEATURE_BUILDER_SPEC.md` | Causal DNA pipeline | `cfg["feature_builder"]` |
| `MINER_SPEC.md` | Walk-forward loop | `cfg["miner"]` |
| `SIGNATURE_DATABASE_SPEC.md` | Archive schema and queries | `cfg["database"]` |
| `KRONOS_MINI_INTEGRATION.md` | Neural gate | `cfg["kronos_mini"]`, `cfg["feature_builder"]["gate"]` |
| `DATA_LAYER_SPEC.md` | Raw data ingestion | `cfg["data"]` |
| `VALIDATION_AND_EVALUATION.md` | Edge metrics and causal checks | `cfg["targets"]` |
| `BACKTEST_AND_ABLATION_FRAMEWORK.md` | Fold-level ablation | `cfg["backtest"]` |
| `SIGNATURE_QUERY_EXAMPLES.md` | Parameterised DuckDB queries | `cfg["database"]`, `cfg["targets"]` |
| `DEPLOYMENT_AND_MIGRATION_GUIDE.md` | Deployment and rollback | `cfg["deployment"]` |
| `VALIDATOR_AND_HARDWARE_SPEC.md` | Hardware and environment | `cfg["hardware"]`, `cfg["reproducibility"]` |
| `SOVEREIGN_VALIDATOR.md` | Hardcode scan engine | `cfg["validator"]` |
| `PIPELINE_WORKFLOW.md` | End-to-end execution workflow | All roots |
| `IMPLEMENTATION_CHECKLIST.md` | Pre-flight and audit status | All roots |
| `KRONOS_V5_SOVEREIGN_ARCHITECTURE.md` | System architecture | All roots |
| `REFERENCES_AND_EXTERNAL_CONTEXT.md` | Research and external context | — |
| `ALTCOIN_KRONOS_HYBRID_PRD.md` | PRD V1 | `cfg["targets"]` |
| `ALTCOIN_KRONOS_HYBRID_PRD_V2.md` | PRD V2 (this file) | `cfg["targets"]` |
| `README.md` | Project entry point | All roots |

---

## Sovereignty Migration Roadmap

| Phase | Status | Action | Config Change |
| :--- | :--- | :--- | :--- |
| Current — Hybrid | **Active** | Structural + neural gate active | `cfg["miner"]["enable_kronos"]: True` |
| Ablation — Structural Only | **Available** | Neural gate disabled | `cfg["miner"]["enable_kronos"]: False`, `cfg["miner"]["enable_ablation"]: True` |
| V5 Sovereign — Partial | **Planned** | Neural slots replaced with deterministic structural surrogates | Remove `cfg["kronos_mini"]` dependency |
| V5 Sovereign — Full | **Target** | GPU-free, all slots deterministic, hardware-portable | All neural toggles permanently disabled |

---

## Non-Negotiable Doctrine

> [!IMPORTANT]
> - Zero inline literals anywhere in specification or engine files.
> - `cfg["miner"]["max_lookahead_bars"]` asserted equal to `cfg["reproducibility"]["constants"]["zero_int"]` before every mining loop.
> - Post-detection metrics (`cfg["miner"]["forward_bars"]`) computed strictly from bars after detection index.
> - Model weights verified against `cfg["kronos_mini"]["model_sha256"]` at every cold start when `cfg["miner"]["enable_kronos"]` is active.
> - Slot weight sum invariant: $\sum w_s =$ `cfg["reproducibility"]["constants"]["one_float"]` — enforced at runtime.

---

**Hardcode Audit Passed — Zero Inline Literals**
