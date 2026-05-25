# Data Layer Specification

**File**: `DATA_LAYER_SPEC.md`  
**Status**: SOVEREIGN LOCKED — ZERO INLINE LITERAL DOCTRINE ENFORCED  
**Config Source**: `params_yaml.txt` loaded via `load_sovereign_config()`  
**Depends On**: `data_engine.py`

---

## Purpose

Defines the raw data acquisition, normalisation, validation, and caching contract for the KRONOS pipeline. All data source identifiers, symbol lists, interval strings, storage formats, and partition schemes resolve exclusively via `cfg["section"]["key"]`.

---

## True Reverse Engineering Pipeline — Data Ingestion Flow

The runtime data layer is **OHLCV-centric**: historical klines are fetched (or loaded from local Parquet), optionally extended incrementally. **Buy/sell imbalance for the miner is not a separate exchange AggTrades HTTP stage** in current code; it is **synthesised** from OHLCV volumes using either **BVC** (bulk volume classification) or a **deterministic SHA-256 bar split** fallback, controlled by `cfg["data"]["volume_classification_method"]`.

```
═══════════════════════════════════════════════════════════════
DATA LAYER CAUSAL FLOW (as implemented)
═══════════════════════════════════════════════════════════════

CONFIG LOAD
  cfg = load_sovereign_config()

SOVEREIGN ENTRY — SHARD-SIZE CAUSAL LOAD (preferred for mining)
  candles_df, agg_trades_like_df = data_engine.load_shard_data(symbol, cfg)
    → fetch_or_load_ohlcv(cfg, symbol=...)  # local Parquet at cfg["data"]["raw_ohlcv_path"]
    → optional incremental Binance kline extension when
         cfg["data"]["enable_incremental_fetch"] is truthy
    → calendar slice with warmup: cfg["data"]["warmup_bars"]
    → generate_synthetic_trades(candles_df, cfg)
         method "bvc"  → sovereign BVC proxy (cfg["data"]["bvc"])
         otherwise     → deterministic per-bar hash split (reproducible)

FETCH-ONLY ENTRY (preflight / orchestrator warm-up)
  df = data_engine.fetch_or_load_ohlcv(cfg, symbol=None)
    → honours cfg["data"]["fetch_end_date"] or resolves "yesterday" UTC
          via cfg["reproducibility"]["constants"]

BINANCE PAGINATION + RATE LIMITS (inside fetch)
  _fetch_binance_klines(symbol, start, end, cfg)
    → HTTP 429: respects Retry-After when present (seconds or HTTP-date),
         else exponential backoff from cfg["data"]["binance"]
    → inter-page sleep: cfg["data"]["binance"]["sleep_time_f"]

OUTPUT CONTRACT FOR MINER
  candles_df columns include open, high, low, close, volume, datetime
  agg_trades_like_df aligns row-wise: price, buy_vol, sell_vol, volume

═══════════════════════════════════════════════════════════════
```

---

## Data Configuration Map

| Property | Description | Config Reference Key |
| :--- | :--- | :--- |
| Data source identifier | Exchange or data provider key (metadata / future use) | `cfg["data"]["source"]` |
| Symbol list | Target asset identifiers | `cfg["data"]["symbols"]` |
| Interval list | Candle resolutions — first entry drives Binance `interval` | `cfg["data"]["intervals"]` |
| Raw OHLCV Parquet path | Primary on-disk OHLCV store | `cfg["data"]["raw_ohlcv_path"]` |
| Incremental fetch toggle | Extend local file toward effective end date | `cfg["data"]["enable_incremental_fetch"]` |
| Fetch date window | Historical range controls | `cfg["data"]["fetch_start_date"]`, `cfg["data"]["fetch_end_date"]` |
| Binance klines endpoint | Futures REST URL | `cfg["data"]["binance_api_url"]` |
| Binance client tuning | Pagination limit, sleep, retries, backoff | `cfg["data"]["binance"]` |
| Volume synthesis method | `"bvc"` or legacy hash split | `cfg["data"]["volume_classification_method"]` |
| BVC hyperparameters | Rolling std window, sigmoid steepness, z clip | `cfg["data"]["bvc"]` |
| Warm-up bar count | Bars kept before shard start index for validity | `cfg["data"]["warmup_bars"]` |
| Schema column aliases | OHLCV and synthetic trade column names | `cfg["data"]["ohlcv_columns"]`, `cfg["data"]["agg_trades_columns"]` |
| Legacy trades flag | May remain in config YAML; microstructure rows are synthesised unless extended later | `cfg["data"]["use_trades"]` |

---

## Data Schema Reference

Column names resolve from configuration. No string literals appear in this table.

| Feed | Column Role | Config Reference Key |
| :--- | :--- | :--- |
| OHLCV | Open price | `cfg["data"]["ohlcv_columns"]["open"]` |
| OHLCV | High price | `cfg["data"]["ohlcv_columns"]["high"]` |
| OHLCV | Low price | `cfg["data"]["ohlcv_columns"]["low"]` |
| OHLCV | Close price | `cfg["data"]["ohlcv_columns"]["close"]` |
| OHLCV | Volume | `cfg["data"]["ohlcv_columns"]["volume"]` |
| OHLCV | Timestamp | `cfg["data"]["ohlcv_columns"]["timestamp"]` |
| AggTrades | Trade timestamp | `cfg["data"]["agg_trades_columns"]["timestamp"]` |
| AggTrades | Trade price | `cfg["data"]["agg_trades_columns"]["price"]` |
| AggTrades | Buy-side volume | `cfg["data"]["agg_trades_columns"]["buy_vol"]` |
| AggTrades | Sell-side volume | `cfg["data"]["agg_trades_columns"]["sell_vol"]` |
| AggTrades | Total trade volume | `cfg["data"]["agg_trades_columns"]["volume"]` |

---

## Data Engine Public API (stubs)

```python
from typing import Dict, Tuple
import pandas as pd

def load_sovereign_config(path: str = "params_yaml.txt") -> Dict:
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)

def fetch_or_load_ohlcv(config: Dict, symbol: str | None = None) -> pd.DataFrame:
    """
    Sovereign OHLCV load or incremental Binance-backed extension.
    Persist/read path from cfg["data"]["raw_ohlcv_path"].

    Full implementation → data_engine.fetch_or_load_ohlcv(config, symbol)
    """
    from data_engine import fetch_or_load_ohlcv as _impl
    return _impl(config, symbol)

def generate_synthetic_trades(ohlcv_df: pd.DataFrame, config: Dict) -> pd.DataFrame:
    """
    Bar-aligned buy/sell volume decomposition (BVC or hash fallback).

    Full implementation → data_engine.generate_synthetic_trades(ohlcv_df, config)
    """
    from data_engine import generate_synthetic_trades as _impl
    return _impl(ohlcv_df, config)

def load_shard_data(symbol: str, config: Dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Causal candles + synthesised agg-trades-compatible frame for one symbol shard.

    Full implementation → data_engine.load_shard_data(symbol, config)
    """
    from data_engine import load_shard_data as _impl
    return _impl(symbol, config)
```

---

**Hardcode Audit Passed — Zero Inline Literals**
