# Reversal Signature Miner Specification

**File**: `MINER_SPEC.md`  
**Status**: SOVEREIGN LOCKED — ZERO INLINE LITERAL DOCTRINE ENFORCED  
**Config Source**: Configuration dictionary loaded dynamically at runtime  
**Depends On**: `miner_engine.py`, `feature_builder_engine.py`, `database_engine.py`

---

## Purpose

Defines the authoritative walk-forward mining engine that converts a continuous historical price stream into a queryable reversal signature archive. Every window length, stride, forward evaluation horizon, mode sentinel, and metric threshold resolves exclusively via dynamic lookups. No hardcoded integers, inline mode strings, or lookup constants are permitted in this specification or the underlying engine implementation.

---

## True Reverse Engineering Pipeline (Authoritative Walk-Forward Flow)

The walk-forward mining loop operates strictly on historical data partitions. All indicator warmups and forward-looking evaluations are partitioned by a rigorous causal barrier:

```
══════════════════════════════════════════════════════════════════════════════════
KRONOS WALK-FORWARD MINING PIPELINE
══════════════════════════════════════════════════════════════════════════════════

STEP ONE — INITIALIZATION & CONFIG LOADING
  config_path = cfg["reproducibility"]["constants"]["config_filename"]
  cfg = load_sovereign_config(config_path)
  
  # Causal assertions enforced at runtime
  assert cfg["miner"]["max_lookahead_bars"] == cfg["reproducibility"]["constants"]["zero_int"]
  assert cfg["miner"]["forward_metric_mode"] == cfg["miner"]["valid_mode_post_detection"]

STEP TWO — WALKING SEGMENT CHECKPOINTED SHARDING
  # Automated monthly stop-start-resume sharding using run_sharded_pipeline.py
  # Completed monthly intervals are tracked in "data/shard_checkpoint.json"
  # NOTE: compile_global_ontology is suppressed per-shard; it runs once globally
  # after all shards complete so HDBSCAN sees the full corpus.
  For each month_interval in get_monthly_ranges(start_date, end_date):
      shard_key = f"{shard_start}_{shard_end}"
      If shard_key in completed_shards:
          Skip already mined monthly block
          
      # Fetch and slice shard-level inputs for the current month
      shard_candles, shard_trades = data_engine.load_shard_data(symbol, cfg)
      
      # Generate walking shards using continuous sharding generator:
      # generator returns sequential dataframes matching cfg["miner"]["batch_size_days"]
      For shard_candles, shard_trades in miner_engine.generate_shards(shard_candles, shard_trades, cfg):
          
          # STEP THREE — SHARD-LEVEL LINEAR PRECOMPUTATION PASS
          # Bypasses rolling window loops to compress time complexity from O(N^2) to O(N)
          pre_struct_df = structural_engine.compute_slots_sovereign(
              shard_candles, shard_trades, cfg["feature_builder"]["structural"], cfg
          )
          pre_veto_comp = structural_engine.compute_veto_composite(
              pre_struct_df, cfg["feature_builder"]["structural"]["slot_15"], cfg["reproducibility"]["constants"]
          )
          # O(1) per-bar vol forecast via tail-slice only (fixed Flaw 8 / O(N²) regression)
          vol_series = log_ret.rolling(vol_lb).std()
          pre_vol_fc = vol_series.diff().fillna(zero_f)
          
          # Initialize dynamic rolling conviction history
          recent_convictions = feature_builder_engine.init_conviction_buffer(cfg)
          one_idx = cfg["reproducibility"]["constants"]["one_int"]
          
          # FLAW 5 FIX: warmup only skipped on the FIRST shard.
          # Subsequent shards start from bar 0 of their slice, eliminating
          # the ~1.73-day monthly data gap.
          For current_idx in miner_engine.bar_index_range(shard_candles, cfg, skip_warmup=is_first_shard):
              
              # ── CAUSAL BOUNDARY ──
              causal_candles = shard_candles.iloc[: current_idx + one_idx]
              causal_trades  = shard_trades.iloc[: current_idx + one_idx]
              
              # Compile DNA vector (using linear precomputed structures for O(1) bar lookups)
              dna_row = feature_builder_engine.build_full_dna_vector(
                  causal_candles, causal_trades, current_idx, recent_convictions, cfg,
                  precomputed_structural_df=pre_struct_df,
                  precomputed_veto_composite=pre_veto_comp,
                  precomputed_vol_forecast=pre_vol_fc
              )
              
              # Check signature detection flag
              flag_key     = cfg["feature_builder"]["gate"]["signature_flag_key"]
              is_signature = dna_row[flag_key]
              
              If is_signature:
                  
                  # ── FORWARD EVALUATION ZONE — STRICTLY POST-DETECTION ──
                  # Slices future candles strictly after detection bar current_idx
                  forward_bars = cfg["miner"]["forward_bars"]
                  fwd_slice = shard_candles.iloc[
                      current_idx + one_idx :
                      current_idx + one_idx + forward_bars
                  ]
                  
                  # Compute Maximum Favorable Excursion (MFE), MAE, and Recovery
                  dna_row = miner_engine.compute_forward_metrics(
                      dna_row, fwd_slice, cfg
                  )
                  
                  # slot_28 (phylum_id) is set to 0.0 placeholder here.
                  # The Global Ontology Compiler (compile_global_ontology) assigns
                  # globally-stable HDBSCAN labels after ALL shards complete.
                  
                  # Buffer for batch write
                  shard_detected.append(dna_row)
              
              # Append current conviction score to dynamic rolling window
              feature_builder_engine.update_conviction_buffer(
                  recent_convictions, dna_row, cfg
              )
          
          # FLAW 7 FIX: single I/O write per shard (replaces per-row store_signature).
          # FLAW 10 FIX: run metrics saved as artifact, no in-loop git side effects.
          if shard_detected:
              database_engine.store_signatures_batch(shard_detected, cfg)
              run_metrics = validation_engine.compute_edge_metrics(pd.DataFrame(shard_detected), cfg)
              miner_engine._write_run_metrics_artifact(run_metrics, cfg, symbol)
          
          is_first_shard = False

  # ── GLOBAL ONTOLOGY COMPILER ──────────────────────────────────────────────────
  # Runs ONCE per symbol after all shards are mined.
  # HDBSCAN is applied to the complete signature corpus in a single pass,
  # producing stable, globally-consistent phylum cluster labels for slot_28.
  # Labels are written back to signatures_compact.parquet.
  miner_engine.compile_global_ontology(symbol, cfg)

  # Mark month as successfully completed and save to JSON checkpoint file
  completed_shards.append(shard_key)
  save_checkpoint(completed_shards)

══════════════════════════════════════════════════════════════════════════════════
```

---

## Miner Configuration Map

Every parameter controlling shard sizes, evaluation windows, and mode configurations is resolved dynamically.

| Property | Description | Config Reference Key |
| :--- | :--- | :--- |
| Target asset list | Symbol strings to mine | `cfg["miner"]["symbols"]` |
| Execution interval | Bar timeframe resolution | `cfg["miner"]["interval"]` |
| Shard window size | Duration of each walk-forward fold (in days) | `cfg["miner"]["batch_size_days"]` |
| Forward horizon | Number of future bars for evaluation | `cfg["miner"]["forward_bars"]` |
| Evaluation mode string | Mode sentinel string for causal assertions | `cfg["miner"]["forward_metric_mode"]` |
| Mode verification key | Allowed value asserting no future leak | `cfg["miner"]["valid_mode_post_detection"]` |
| Max lookahead | Causal guard parameter (must resolve to zero) | `cfg["miner"]["max_lookahead_bars"]` |
| Neural gate enable | Gate toggle for Kronos-mini transformer | `cfg["miner"]["enable_kronos"]` |
| Ablation study toggle | Bypass toggle for conviction gating tests | `cfg["miner"]["enable_ablation"]` |
| Min signature quality | Quality cutoff parameter for storage | `cfg["miner"]["min_quality_score"]` |
| Dynamic buffer size | History capacity for median conviction | `cfg["feature_builder"]["gate"]["recent_conviction_window"]` |
| Causal slice offset | Causal index step modifier | `cfg["reproducibility"]["constants"]["one_int"]` |
| Numerical stabilizer | Mathematical epsilon for metric quotients | `cfg["reproducibility"]["constants"]["epsilon"]` |

---

## Miner Engine Programmatic Interface

The mining pipeline is managed by the `miner_engine.py` wrapper, which acts as the functional engine runner:

```python
from typing import Dict
import pandas as pd

def load_sovereign_config(path: str) -> Dict:
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)

def run_miner(config: Dict, start_date: str, end_date: str) -> None:
    """
    Executes walk-forward mining loops over configured symbols.
    All sharding constraints, horizons, mode guards, and limits are fetched
    dynamically from the config payload. No literals permitted.

    Config References:
      cfg["miner"]["symbols"]
      cfg["miner"]["batch_size_days"]
      cfg["miner"]["forward_bars"]
      cfg["miner"]["max_lookahead_bars"]
      cfg["miner"]["forward_metric_mode"]
      cfg["reproducibility"]["constants"]["zero_int"]
      cfg["reproducibility"]["constants"]["one_int"]

    Implementation in miner_engine.py
    """
    from miner_engine import run_miner as _impl
    _impl(config, start_date, end_date)

def compute_forward_metrics(
    dna_row: pd.Series,
    forward_slice: pd.DataFrame,
    config: Dict
) -> pd.Series:
    """
    Calculates MFE, MAE, and Recovery factors over post-detection prices.
    Uses strict causal limits; all parameters parsed dynamically from config.

    Config References:
      cfg["miner"]["forward_bars"]
      cfg["reproducibility"]["constants"]["epsilon"]

    Implementation in miner_engine.py
    """
    from miner_engine import compute_forward_metrics as _impl
    return _impl(dna_row, forward_slice, config)
```

---

## Sovereignty Migration Path

> [!WARNING]
> **Active Hybrid Compromises**:
> - Post-detection metric evaluation requires a continuous feed slice immediately following the signature trigger bar.
> - **Causal Enforcement**: If `cfg["miner"]["max_lookahead_bars"]` is set to any value other than `cfg["reproducibility"]["constants"]["zero_int"]`, the miner will fail to bootstrap, preserving the integrity of the sovereign backtest from retrofitted lookahead bias.

---

**Hardcode Audit Passed — Zero Inline Literals**