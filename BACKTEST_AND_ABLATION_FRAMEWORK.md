# Backtest and Ablation Framework

**File**: `BACKTEST_AND_ABLATION_FRAMEWORK.md`  
**Status**: SOVEREIGN LOCKED — ZERO INLINE LITERAL DOCTRINE ENFORCED  
**Config Source**: `params_yaml.txt` loaded via `load_sovereign_config()`  
**Depends On**: `backtest_engine.py`, `miner_engine.py`, `validation_engine.py`

---

## Purpose

Defines the walk-forward backtesting and ablation study framework for KRONOS. All fold sizes, evaluation horizons, ablation toggles, and performance targets resolve exclusively via `cfg["section"]["key"]`. The framework supports both full hybrid runs and sovereign-only structural ablations.

---

## True Reverse Engineering Pipeline — Backtest and Ablation Flow

```
═══════════════════════════════════════════════════════════════
BACKTEST + ABLATION PIPELINE
═══════════════════════════════════════════════════════════════

CONFIG LOAD
  cfg = load_sovereign_config()

CAUSAL INTEGRITY ASSERTIONS (mandatory before any run)
  assert cfg["miner"]["max_lookahead_bars"] == cfg["reproducibility"]["constants"]["zero_int"]

SIGNATURE CORPUS LOAD
  Load the Parquet corpus (typically post-compaction) keyed by timestamps.
  walk_forward_validation in validation_engine optionally reads cfg["database"]["compact_path"].

WALK-FORWARD FOLD GENERATOR
  folds = backtest_engine.generate_folds(signatures_df, cfg)
  → List of (train_shard, test_shard) pairs ordered in time.
     Fold geometry from cfg["backtest"]["fold_window_days"], cfg["backtest"]["fold_step_days"],
     cfg["backtest"]["min_fold_bars"].

ROLLING OOS PERFORMANCE (implemented aggregate)
  result = backtest_engine.run_backtest(signatures_df, cfg)
  → Dict with pooled out-of-sample style metrics:
       sharpe           — mean annualised Sharpe across OOS test folds
       max_drawdown     — max drawdown on concatenated daily return proxy series
       total_trades     — count of signatures evaluated across OOS folds
       fold_count       — number of generated folds

ABLATION STUDY (operational pattern)
  The engine exposes fold generation plus a single pooled backtest statistic.
  To compare hybrid vs structural-only regimes, run mining twice with toggles:
    cfg["miner"]["enable_kronos"], cfg["miner"]["enable_ablation"]
  Persist each archive, then invoke run_backtest (or downstream analytics) per corpus —
  no dual-signature evaluate_fold helper exists in backtest_engine.py.

═══════════════════════════════════════════════════════════════
```

---

## Backtest Configuration Map

| Property | Description | Config Reference Key |
| :--- | :--- | :--- |
| Walk-forward fold window | Train + test fold duration | `cfg["backtest"]["fold_window_days"]` |
| Fold step size | Stride between folds | `cfg["backtest"]["fold_step_days"]` |
| Minimum fold coverage | Minimum bars per fold | `cfg["backtest"]["min_fold_bars"]` |
| Forward evaluation bars | Post-detection evaluation horizon | `cfg["miner"]["forward_bars"]` |
| Max lookahead guard | Causal guard — must equal zero_int | `cfg["miner"]["max_lookahead_bars"]` |
| Neural gate toggle | Enable/disable hybrid neural layer | `cfg["miner"]["enable_kronos"]` |
| Ablation mode toggle | Enable sovereign-only structural run | `cfg["miner"]["enable_ablation"]` |
| GPF target | Minimum Gross Profit Factor | `cfg["targets"]["min_gross_profit"]` |
| Recovery factor target | Minimum median recovery factor | `cfg["targets"]["min_recovery"]` |
| Regime filter | Target HMM regime identifier | `cfg["targets"]["regime_id"]` |
| Epsilon guard | Division-by-zero stability | `cfg["reproducibility"]["constants"]["epsilon"]` |

---

## Ablation Study Design

| Ablation Scenario | Config State | Expected Finding | Config Toggles |
| :--- | :--- | :--- | :--- |
| Full hybrid baseline | `enable_kronos: True`, `enable_ablation: False` | Maximum short-term edge via orthogonal neural signal | `cfg["miner"]["enable_kronos"]`, `cfg["miner"]["enable_ablation"]` |
| Sovereign structural only | `enable_kronos: False`, `enable_ablation: True` | Quantify pure structural edge without neural weights | `cfg["miner"]["enable_kronos"]`, `cfg["miner"]["enable_ablation"]` |
| Veto threshold sensitivity | Sweep `veto_threshold` values via config | Identify minimum structural barrier for positive expectancy | `cfg["feature_builder"]["structural"]["veto_threshold"]` |
| Forward horizon sensitivity | Sweep `forward_bars` values via config | Identify optimal post-detection evaluation window | `cfg["miner"]["forward_bars"]` |
| Regime-conditioned ablation | Filter by `regime_id` before metric computation | Isolate per-regime edge contribution | `cfg["targets"]["regime_id"]` |

---

## Backtest Engine Stubs

```python
from typing import Dict, List, Tuple
import pandas as pd

def load_sovereign_config(path: str = "params_yaml.txt") -> Dict:
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)

def generate_folds(signatures_df: pd.DataFrame, config: Dict) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
    """
    Generates (train_shard, test_shard) pairs ordered along signature timestamps.

    Full implementation → backtest_engine.generate_folds(signatures_df, config)
    """
    from backtest_engine import generate_folds as _impl
    return _impl(signatures_df, config)


def run_backtest(signatures_df: pd.DataFrame, config: Dict) -> Dict:
    """
    Walk-forward OOS pooled metrics (Sharpe, max drawdown, trade counts).

    Full implementation → backtest_engine.run_backtest(signatures_df, config)
    """
    from backtest_engine import run_backtest as _impl
    return _impl(signatures_df, config)
```

---

**Hardcode Audit Passed — Zero Inline Literals**
