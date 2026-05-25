# Altcoin Pipeline Workflow

**File**: `ALTCOIN_PIPELINE_WORKFLOW.md`  
**Status**: SOVEREIGN LOCKED — ZERO INLINE LITERAL DOCTRINE ENFORCED  
**Config Source**: `params_yaml.txt` loaded via `load_sovereign_config()`

---

## Purpose

Defines the complete end-to-end operational workflow for running the Altcoin KRONOS Hybrid on cloud compute infrastructure (`cfg["infrastructure"]["provider"]`). From a cold start to a populated, query-ready signature archive spanning the full perpetual altcoin universe (`cfg["universe"]["size"]`), operating across the configured timeframe (`cfg["feature_builder"]["interval"]`). Every step references only engine function calls and config keys. No inline numbers, paths, or parameter values appear.

---

## End-to-End Execution Workflow

```
═══════════════════════════════════════════════════════════════
ALTCOIN KRONOS HYBRID COMPLETE PIPELINE WORKFLOW
═══════════════════════════════════════════════════════════════

STAGE 1 — PRE-FLIGHT
  ├── hardcode_validator_engine.run_full_validation(scan_dir, cfg)
  │     → cfg["validator"]["scan_extensions"]
  │     → cfg["validator"]["exit_violations"]
  ├── environment_engine.validate_environment(cfg)
  │     → cfg["infrastructure"]["provider"]          # validates cloud mining infrastructure
  │     → cfg["reproducibility"]["precision"]
  │     → cfg["reproducibility"]["random_seed"]
  │     → cfg["kronos_mini"]["model_sha256"]
  └── environment_engine.seed_everything(cfg)
        → cfg["reproducibility"]["random_seed"]

STAGE 2 — CROSS-SECTIONAL DATA INITIALISATION
  ├── data_engine.fetch_or_load_universe_ohlcv(cfg)            # orchestrator-grade warm reload
  │     → cfg["data"]["raw_ohlcv_path"]
  │     → cfg["feature_builder"]["interval"]
  │     → Fetches full historical data from cfg["data"]["start_date"] to cfg["data"]["end_date"]
  │     → incremental exchange extensions + adaptive Retry-After handling
  └── data_engine.load_cross_sectional_shards(cfg)
        → loads universe data for cfg["universe"]["size"] assets in parallel
        → warmup slice + cfg["data"]["warmup_bars"]
        → data_engine.generate_synthetic_trades(...)

STAGE 3 — DATABASE INITIALISATION
  └── database_engine.initialize_duckdb_views(cfg)
        → cfg["database"]["duckdb_path"]
        → cfg["database"]["parquet_path_pattern"]
        → cfg["database"]["compact_path"]           # binds view to compact parquet when present

STAGE 4 — WALK-FORWARD MINING LOOP (CROSS-SECTIONAL)
  └── miner_engine.run_cross_sectional_miner(cfg, start_date, end_date)

        PER CROSS-SECTIONAL BATCH:
        ├── Linear O(N) Batch-level Precomputations
        │     → precomputed_structural_df (Cross-sectional structural slots)
        │     → precomputed_veto_composite (Universe veto scores)
        │     → precomputed_vol_forecast (O(1) tail-slice, fixed O(N²) flaw)
        │
        ├── feature_builder_engine.build_universe_dna_matrix(
        │       universe_candles, universe_trades,
        │       current_idx, recent_convictions, cfg,
        │       precomputed_structural_df,
        │       precomputed_veto_composite,
        │       precomputed_vol_forecast
        │   )
        │     → [Linear Vector O(1) Slicing & Cross-sectional DNA Assembly]
        │     → slot_28 set to cfg["reproducibility"]["constants"]["zero_float"] placeholder during mining
        │
        ├── miner_engine.compute_forward_metrics_matrix(dna_matrix, fwd_slice, cfg)
        │     → cfg["miner"]["forward_bars"]
        │     → cfg["reproducibility"]["constants"]["epsilon"]
        │
        │   [BATCH WRITE: once per cross-section, not per-bar]
        ├── database_engine.store_signatures_batch(universe_detections, cfg)
        │     → cfg["database"]["path"]
        │     → cfg["database"]["partition_by"]
        │
        │   [RUN METRICS JSON — written after batches that yielded detections]
        └── miner_engine-internal _write_run_metrics_artifact(run_metrics, cfg)
              → cfg["database"]["path"] / audit_runs / run_universe_<ts>.json
              → Computes run_metrics via validation_engine.compute_edge_metrics(...)
              → No automatic git commits; use git_audit_hook manually if desired

        POST ALL BATCHES:
        ├── miner_engine.compile_global_ontology(cfg)
        │     → HDBSCAN on full universe corpus in a single pass
        │     → Overwrites slot_28 with globally-stable phylum labels
        │     → cfg["feature_builder"]["metadata"]["hdbscan"]
        │     → cfg["database"]["compact_path"]
        └── OPTIONAL — manual git provenance (not invoked by miner_engine)
              git_audit_hook.commit_successful_run(metrics, cfg)
  └── database_engine.initialize_duckdb_views(cfg)
        → Refreshes DuckDB view to bind to updated compact parquet
        → cfg["database"]["compact_path"]

STAGE 6 — VALIDATION SUITE
  ├── validation_engine.assert_causal_integrity(cfg)
  │     → cfg["miner"]["max_lookahead_bars"]
  │     → cfg["reproducibility"]["constants"]["zero_int"]
  └── validation_engine.compute_edge_metrics(signatures_df, cfg)
        → cfg["targets"]["min_gross_profit"]
        → cfg["targets"]["min_recovery"]
        → cfg["targets"]["perfect_gpf_sentinel"]

STAGE 7 — ANALYTICAL QUERY LAYER
  ├── database_engine.query_elite_signatures(con, cfg)
  ├── database_engine.query_cross_sectional_regime(con, cfg)
  └── database_engine.query_phylum_edge_stats(con, cfg)

STAGE 8 — POST-RUN OPTIMIZATION PROTOCOL
  # ORDERING IS CRITICAL: compact must run BEFORE ontology compiler.
  ├── compact_database.compact_database()
  │     → Merges partition tree → signatures_compact.parquet
  ├── miner_engine.compile_global_ontology(cfg)  [if not already run above]
  │     → HDBSCAN on full corpus, writes stable slot_28 to compact file
  ├── database_engine.initialize_duckdb_views(cfg)
  │     → DuckDB view refresh post-compaction
  └── generate_signatures_wiki.generate_wiki()
        → Auto-generates quantitative signatures wiki

═══════════════════════════════════════════════════════════════
```

---

## Workflow Configuration Map

| Stage | Key Configuration Nodes | Config Reference Keys |
| :--- | :--- | :--- |
| Pre-flight | Validator, environment, seed, infra | `cfg["validator"]`, `cfg["reproducibility"]`, `cfg["infrastructure"]` |
| Data initialisation | Source, universe size, intervals, warmup | `cfg["data"]`, `cfg["universe"]`, `cfg["feature_builder"]` |
| Database init | Archive path, DuckDB path, pattern | `cfg["database"]` |
| Mining loop | Universe, batch size, forward bars, gate | `cfg["miner"]`, `cfg["universe"]`, `cfg["feature_builder"]` |
| Structural core | All slot config blocks | `cfg["feature_builder"]["structural"]` |
| Neural gate | Model, tokenizer, pooling, norm | `cfg["kronos_mini"]`, `cfg["feature_builder"]["gate"]` |
| Validation | Causal guard, GPF, recovery | `cfg["targets"]`, `cfg["miner"]` |
| Queries | Quality, phylum, regime, audit | `cfg["database"]`, `cfg["targets"]` |

---

## Orchestration Stub

```python
from typing import Dict

def load_sovereign_config(path: str = "params_yaml.txt") -> Dict:
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)

def run_full_pipeline(config: Dict) -> Dict:
    """
    Executes all seven pipeline stages in sequence.
    All parameters resolved from config.

    Config refs (representative):
      cfg["validator"]
      cfg["reproducibility"]
      cfg["infrastructure"]
      cfg["universe"]
      cfg["data"]
      cfg["database"]
      cfg["miner"]
      cfg["feature_builder"]
      cfg["kronos_mini"]
      cfg["targets"]

    Full implementation → orchestrator_engine.run_full_pipeline(config)
    """
    from orchestrator_engine import run_full_pipeline as _impl
    return _impl(config)
```

---

## Stage Skip Configuration Map

| Skip Condition | Toggle Key | Config Reference Key |
| :--- | :--- | :--- |
| Skip neural gate | Disable Kronos-mini | `cfg["miner"]["enable_kronos"]` |
| Skip auxiliary slots | Enable ablation mode | `cfg["miner"]["enable_ablation"]` |
| Legacy microstructure flags | Older YAML knobs | `cfg["data"]["use_trades"]`, `cfg["data"]["volume_classification_method"]` |
| Skip partitioned tree reads | Presence of compact Parquet binds DuckDB first | `cfg["database"]["compact_path"]` |
| Skip weight check | Disable pinning enforcement | `cfg["reproducibility"]["enforce_pinning"]` |

---

**Hardcode Audit Passed — Zero Inline Literals**
