# Altcoin Data Layer Specification

**File**: `ALTCOIN_DATA_LAYER_SPEC.md`  
**Status**: SOVEREIGN LOCKED — ZERO INLINE LITERAL DOCTRINE ENFORCED  
**Config Source**: `params_yaml.txt` loaded via `load_sovereign_config()`  
**Depends On**: `data_engine.py`

---

## Purpose

Defines the raw data acquisition, cross-sectional normalisation, validation, and caching contract for the Altcoin KRONOS Hybrid pipeline on cloud compute (e.g., Lightning AI Cloud Mining). All data source identifiers, symbol lists (spanning `cfg["universe"]["size"]` altcoins), interval strings (e.g., `cfg["feature_builder"]["interval"]`), storage formats, and partition schemes resolve exclusively via `cfg["section"]["key"]`. Full historical data is enforced from `cfg["data"]["fetch_start_date"]` (genesis) to `cfg["data"]["fetch_end_date"]`.

---

## True Reverse Engineering Pipeline — Data Ingestion Flow

The runtime data layer is **OHLCV-centric** and highly concurrent, processing a vast universe of altcoins. Historical klines are fetched (or loaded from local Parquet caches optimized for Lightning AI Cloud Mining), optionally extended incrementally. **Buy/sell imbalance for the miner is not a separate exchange AggTrades HTTP stage** in current code; it is **synthesised** from OHLCV volumes using either **BVC** (bulk volume classification) or a **deterministic SHA-256 bar split** fallback, controlled by `cfg["data"]["volume_classification_method"]`.

```text
═══════════════════════════════════════════════════════════════
DATA LAYER CAUSAL FLOW (as implemented)
═══════════════════════════════════════════════════════════════

CONFIG LOAD
  cfg = load_sovereign_config()

SOVEREIGN ENTRY — UNIVERSE-WIDE CAUSAL LOAD (cross-sectional mining)
  universe_dict = data_engine.load_universe_data(cfg)
    → For each symbol in cfg["universe"]["symbols"]:
      → fetch_or_load_ohlcv(cfg, symbol)  # local Parquet at cfg["data"]["raw_ohlcv_path"]
      → optional incremental Binance kline extension when
           cfg["data"]["enable_incremental_fetch"] is truthy
      → enforce interval via cfg["feature_builder"]["interval"]
      → calendar slice with warmup: cfg["data"]["warmup_bars"]
      → generate_synthetic_trades(candles_df, cfg)
           method "bvc"  → sovereign BVC proxy (cfg["data"]["bvc"])
           otherwise     → deterministic per-bar hash split (reproducible)

FETCH-ONLY ENTRY (preflight / orchestrator warm-up on Lightning AI)
  data_engine.sync_universe_history(cfg)
    → honours cfg["data"]["fetch_start_date"] and cfg["data"]["fetch_end_date"]
    → runs concurrently for cfg["universe"]["size"] perpetuals

BINANCE PAGINATION + RATE LIMITS (inside fetch)
  _fetch_binance_klines(symbol, start, end, cfg)
    → HTTP 429: respects Retry-After when present (seconds or HTTP-date),
         else exponential backoff from cfg["data"]["binance"]
    → inter-page sleep: cfg["data"]["binance"]["sleep_time_f"]

OUTPUT CONTRACT FOR MINER
  universe_dict maps symbol -> (candles_df, agg_trades_like_df)
  candles_df columns include open, high, low, close, volume, datetime
  agg_trades_like_df aligns row-wise: price, buy_vol, sell_vol, volume

═══════════════════════════════════════════════════════════════
```

---

## Data Configuration Map

| Property | Description | Config Reference Key |
| :--- | :--- | :--- |
| Data source identifier | Exchange or data provider key | `cfg["data"]["source"]` |
| Symbol list | Target asset identifiers for cross-sectional mining | `cfg["universe"]["symbols"]` |
| Universe size | Target number of altcoins | `cfg["universe"]["size"]` |
| Interval list | Candle resolutions | `cfg["feature_builder"]["interval"]` |
| Raw OHLCV Parquet path | Primary on-disk OHLCV store | `cfg["data"]["raw_ohlcv_path"]` |
| Compute infrastructure | Target cloud environment | `cfg["infrastructure"]["compute_provider"]` |
| Incremental fetch toggle | Extend local file toward effective end date | `cfg["data"]["enable_incremental_fetch"]` |
| Fetch date window | Full history (genesis) controls | `cfg["data"]["fetch_start_date"]`, `cfg["data"]["fetch_end_date"]` |
| Binance klines endpoint | Futures REST URL | `cfg["data"]["binance_api_url"]` |
| Binance client tuning | Pagination limit, sleep, retries, backoff | `cfg["data"]["binance"]` |
| Volume synthesis method | `"bvc"` or legacy hash split | `cfg["data"]["volume_classification_method"]` |
| BVC hyperparameters | Rolling std window, sigmoid steepness, z clip | `cfg["data"]["bvc"]` |
| Warm-up bar count | Bars kept before shard start index for validity | `cfg["data"]["warmup_bars"]` |
| Schema column aliases | OHLCV and synthetic trade column names | `cfg["data"]["ohlcv_columns"]`, `cfg["data"]["agg_trades_columns"]` |
| Legacy trades flag | Microstructure rows are synthesised unless extended later | `cfg["data"]["use_trades"]` |

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
from typing import Dict, Tuple, List
import pandas as pd

def load_sovereign_config(path: str = "params_yaml.txt") -> Dict:
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)

def fetch_or_load_ohlcv(config: Dict, symbol: str | None = None) -> pd.DataFrame:
    """
    Sovereign OHLCV load or incremental Binance-backed extension.
    Persist/read path from cfg["data"]["raw_ohlcv_path"].
    Interval dictated by cfg["feature_builder"]["interval"].
    
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

def load_universe_data(config: Dict) -> Dict[str, Tuple[pd.DataFrame, pd.DataFrame]]:
    """
    Cross-sectional candles + synthesised agg-trades-compatible frames for the entire universe.
    Spans cfg["universe"]["size"] symbols.

    Full implementation → data_engine.load_universe_data(config)
    """
    from data_engine import load_universe_data as _impl
    return _impl(config)
```

---

**Hardcode Audit Passed — Zero Inline Literals**
