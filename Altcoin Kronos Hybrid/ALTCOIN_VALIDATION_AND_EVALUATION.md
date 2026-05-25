# Altcoin Validation and Evaluation Specification

**File**: `ALTCOIN_VALIDATION_AND_EVALUATION.md`  
**Status**: SOVEREIGN LOCKED — ZERO INLINE LITERAL DOCTRINE ENFORCED  
**Config Source**: `params_yaml.txt` loaded via `load_sovereign_config()`  
**Depends On**: `validation_engine.py`, `database_engine.py`

---

## Purpose

Defines the validation and evaluation contract for Altcoin KRONOS signatures across the cross-sectional perpetual universe (size: `cfg["universe"]["size"]`). Covers causal integrity assertions, signature quality checks, walk-forward performance evaluation, and edge measurement over the full historical data (`cfg["data_loader"]["history"]`) on the designated compute infrastructure (`cfg["infrastructure"]["compute"]`) at a specified timeframe (`cfg["feature_builder"]["interval"]`). All thresholds, metric boundaries, and evaluation horizons resolve exclusively via `cfg["section"]["key"]`.

---

## True Reverse Engineering Pipeline — Validation Flow

```text
═══════════════════════════════════════════════════════════════
ALTCOIN SIGNATURE VALIDATION PIPELINE
═══════════════════════════════════════════════════════════════

CONFIG LOAD
  cfg = load_sovereign_config()

CAUSAL INTEGRITY ASSERTIONS (before any mining)
  assert cfg["miner"]["max_lookahead_bars"] == cfg["reproducibility"]["constants"]["zero_int"]
  assert cfg["miner"]["forward_metric_mode"] == cfg["miner"]["valid_mode_post_detection"]

SIGNATURE ARCHIVE LOAD
  con = database_engine.get_connection(cfg)
  signatures_df = database_engine.query_elite_signatures(con, cfg)

QUALITY GATE FILTER
  quality_col = cfg["feature_builder"]["metadata"]["keys"]["signature_quality"]
  min_quality = cfg["database"]["min_quality_score"]
  filtered_df = signatures_df[signatures_df[quality_col] >= min_quality]

CAUSAL INTEGRITY GUARANTEE
  Full implementation →
    validation_engine.assert_causal_integrity(cfg)

PERFORMANCE METRICS COMPUTATION (Cross-Sectional)
  Full implementation →
    validation_engine.compute_edge_metrics(filtered_df, cfg)
  → gpf     : Gross Profit Factor — target: cfg["targets"]["min_gross_profit"]
  → rfactor : Recovery Factor    — target: cfg["targets"]["min_recovery"]

WALK-FORWARD OUT-OF-SAMPLE VALIDATION
  Full implementation →
    validation_engine.walk_forward_validation(cfg, start_date, end_date)
    → Loads compact parquet (cfg["database"]["compact_path"] with path fallback),
         filters to window, delegates Sharpe/OOS metrics to backtest_engine.run_backtest.

OPTIONAL CONTEXT PROVENANCE (NOT WIRED AUTOMATICALLY)
  Module git_audit_hook.commit_successful_run(metrics, cfg) exists for manual /
  orchestrator-triggered commits when evaluations pass thresholds.
  It is NOT called from validation_engine nor from the miner loop — run it
  explicitly if you want Pillar 3 commits after gated metrics.

═══════════════════════════════════════════════════════════════
```

---

## Validation Configuration Map

| Check | Description | Config Reference Key |
| :--- | :--- | :--- |
| Universe Scope | Asset universe size for cross-sectional processing | `cfg["universe"]["size"]` |
| Execution Interval | Data timeframe interval | `cfg["feature_builder"]["interval"]` |
| Historical Data | Evaluation history range | `cfg["data_loader"]["history"]` |
| Compute Infra | Cloud mining environment | `cfg["infrastructure"]["compute"]` |
| Causal lookahead guard | Max lookahead must equal zero_int | `cfg["miner"]["max_lookahead_bars"]` |
| Evaluation mode sentinel | Forward mode must equal valid sentinel | `cfg["miner"]["forward_metric_mode"]` |
| Valid mode value | Acceptable forward metric mode | `cfg["miner"]["valid_mode_post_detection"]` |
| Minimum quality gate | Archive quality score floor | `cfg["database"]["min_quality_score"]` |
| GPF target | Minimum Gross Profit Factor | `cfg["targets"]["min_gross_profit"]` |
| Recovery factor target | Minimum median recovery factor | `cfg["targets"]["min_recovery"]` |
| Regime focus | Target HMM regime identifier | `cfg["targets"]["regime_id"]` |
| Retention floor | Minimum recovery for archive entry | `cfg["database"]["retention_policy"]["min_recovery_factor"]` |
| Forward evaluation bars | Post-detection horizon | `cfg["miner"]["forward_bars"]` |
| Quality score column | Signature quality column name | `cfg["feature_builder"]["metadata"]["keys"]["signature_quality"]` |

---

## Edge Metrics Reference

| Metric | Definition | Pass Condition | Config Reference Key |
| :--- | :--- | :--- | :--- |
| Gross Profit Factor | Sum of winning recoveries / sum of losing recoveries | `>= cfg["targets"]["min_gross_profit"]` | `cfg["targets"]["min_gross_profit"]` |
| Median Recovery Factor | Median of (MFE / (MAE + epsilon)) | `>= cfg["targets"]["min_recovery"]` | `cfg["targets"]["min_recovery"]` |
| Causal Lookahead | Max bars accessed before detection | Must equal `cfg["reproducibility"]["constants"]["zero_int"]` | `cfg["miner"]["max_lookahead_bars"]` |
| Quality Score | Composite quality of signature DNA | `>= cfg["database"]["min_quality_score"]` | `cfg["database"]["min_quality_score"]` |
| Epsilon denominator | MAE guard preventing division instability | `cfg["reproducibility"]["constants"]["epsilon"]` | `cfg["reproducibility"]["constants"]["epsilon"]` |

---

## Validation Engine Stubs

```python
from typing import Dict
import pandas as pd

def load_sovereign_config(path: str = "params_yaml.txt") -> Dict:
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)

def assert_causal_integrity(config: Dict) -> None:
    """
    Runs all sovereignty assertions before any pipeline execution.

    Config refs:
      cfg["miner"]["max_lookahead_bars"]
      cfg["reproducibility"]["constants"]["zero_int"]
      cfg["miner"]["forward_metric_mode"]
      cfg["miner"]["valid_mode_post_detection"]
      cfg["universe"]["size"]
      cfg["infrastructure"]["compute"]

    Full implementation → validation_engine.assert_causal_integrity(config)
    """
    from validation_engine import assert_causal_integrity as _impl
    _impl(config)

def compute_edge_metrics(signatures_df: pd.DataFrame, config: Dict) -> Dict:
    """
    Computes GPF, median recovery factor, and regime alignment.
    All targets and epsilon from config.

    Config refs:
      cfg["targets"]["min_gross_profit"]
      cfg["targets"]["min_recovery"]
      cfg["targets"]["regime_id"]
      cfg["reproducibility"]["constants"]["epsilon"]
      cfg["feature_builder"]["interval"]

    Full implementation → validation_engine.compute_edge_metrics(signatures_df, config)
    """
    from validation_engine import compute_edge_metrics as _impl
    return _impl(signatures_df, config)

def walk_forward_validation(config: Dict, start_date: str, end_date: str) -> Dict:
    """
    Runs out-of-sample walk-forward validation across the entire universe.
    All horizons and quality thresholds from config.

    Config refs:
      cfg["miner"]["batch_size_days"]
      cfg["miner"]["forward_bars"]
      cfg["database"]["min_quality_score"]
      cfg["data_loader"]["history"]

    Full implementation → validation_engine.walk_forward_validation(config, start_date, end_date)
    """
    from validation_engine import walk_forward_validation as _impl
    return _impl(config, start_date, end_date)
```

---

**Hardcode Audit Passed — Zero Inline Literals**
