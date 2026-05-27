"""
KRONOS Data Engine — Sovereign Load + Dynamic Incremental Fetch
Zero inline literals. All values from cfg.
"""

from typing import Dict, Tuple
from pathlib import Path
import time
import email.utils
import requests
import pandas as pd
import numpy as np


def fetch_or_load_ohlcv(config: Dict, symbol: str | None = None) -> pd.DataFrame:
    """Main sovereign data entry point."""
    data_cfg = config["data"]
    raw_path = Path(data_cfg["raw_ohlcv_path"])
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    end_date = _resolve_effective_end_date(config)
    target_symbol = symbol or config["miner"]["symbols"][0]

    # Dynamic local check vs incremental fetch
    if raw_path.exists():
        df_local = pd.read_parquet(raw_path)
        if "datetime" in df_local.columns:
            df_local["datetime"] = pd.to_datetime(df_local["datetime"], utc=True)
        df_local = df_local.sort_values("datetime").reset_index(drop=True)

        if not data_cfg.get("enable_incremental_fetch", False):
            return df_local

        if not df_local.empty:
            max_ts = df_local["datetime"].iloc[-1]
            target_ts = pd.Timestamp(end_date).tz_localize("UTC")

            if max_ts >= target_ts:
                print(f"[OK] Local data covers up to {max_ts.strftime('%Y-%m-%d %H:%M:%S')}. Fetch skipped.")
                return df_local

            start_date_str = max_ts.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[INFO] Incremental fetch starting from {start_date_str} to {end_date} (dynamic yesterday)")
            df_new = _fetch_binance_klines(target_symbol, start_date_str, end_date, config)

            if not df_new.empty:
                df_combined = pd.concat([df_local, df_new], ignore_index=True)
                df_combined = df_combined.drop_duplicates(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
                df_combined.to_parquet(raw_path)
                print(f"[OK] Incremental fetch complete. Added {len(df_new):,} new bars. Total bars: {len(df_combined):,}")
                return df_combined
            else:
                return df_local

    start_date = data_cfg["fetch_start_date"]
    print(f"[INFO] Raw file missing. Performing full fetch from {start_date} to {end_date} (dynamic yesterday)")
    df = _fetch_binance_klines(target_symbol, start_date, end_date, config)
    if not df.empty:
        df = df.sort_values("datetime").reset_index(drop=True)
        df.to_parquet(raw_path)
        print(f"[OK] Full fetch complete: {len(df):,} bars saved to {raw_path}")
    return df


def _resolve_effective_end_date(config: Dict) -> str:
    """If fetch_end_date is null → compute yesterday UTC."""
    data_cfg = config["data"]
    const = config["reproducibility"]["constants"]

    end = data_cfg.get("fetch_end_date")
    if end is None or str(end).lower() == "null":
        yesterday = pd.Timestamp.now(tz="UTC").floor("D") - pd.Timedelta(days=const["one_day_int"])
        return yesterday.strftime("%Y-%m-%d")
    return str(end)


def _fetch_binance_klines(symbol: str, start_str: str, end_str: str, config: Dict) -> pd.DataFrame:
    """Config-driven paginated fetch."""
    data_cfg = config["data"]
    const = config["reproducibility"]["constants"]

    base_url = data_cfg["binance_api_url"]
    limit = data_cfg.get("binance", {}).get("limit_per_request", const["binance_limit_int"])

    all_data = []
    start_ts = pd.Timestamp(start_str)
    if start_ts.tz is None:
        start_ts = start_ts.tz_localize("UTC")
    end_ts = pd.Timestamp(end_str)
    if end_ts.tz is None:
        end_ts = end_ts.tz_localize("UTC")
    end_ms = int(end_ts.timestamp() * const["ms_factor_int"])
    current = int(start_ts.timestamp() * const["ms_factor_int"])
    one_i = const["one_int"]

    request_count = 0
    while True:
        params = {
            "symbol": symbol,
            "interval": data_cfg["intervals"][const["zero_int"]],
            "limit": limit,
            "startTime": current,
        }
        
        # Robust Retry Loop with Adaptive + Exponential Backoff
        data = None
        max_retries = data_cfg.get("binance", {}).get("max_retries", 5)
        base_backoff = data_cfg.get("binance", {}).get("base_backoff_s", 5)
        rate_limit_base = data_cfg.get("binance", {}).get("rate_limit_backoff_s", 30)

        for attempt in range(max_retries):
            try:
                resp = requests.get(base_url, params=params, timeout=const["fifteen_int"])
                if resp.status_code == const["rate_limit_status"]:
                    # FUTURE-PROOF FIX: read Retry-After header if present (adaptive),
                    # fall back to exponential backoff only when header is absent.
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after is not None:
                        backoff = _parse_retry_after_seconds(retry_after, rate_limit_base)
                        print(f"[WARNING] Binance rate-limited (HTTP 429). Retry-After header: {backoff}s. Sleeping...")
                    else:
                        backoff = rate_limit_base * (attempt + const["one_int"])
                        print(f"[WARNING] Binance rate-limited (HTTP 429). Attempt {attempt + 1}/{max_retries}. Sleeping {backoff}s...")
                    time.sleep(backoff)
                    continue
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception as exc:
                backoff = base_backoff * (attempt + const["one_int"])
                print(f"[WARNING] Network/Server glitch (Attempt {attempt + 1}/{max_retries}): {exc}. Retrying in {backoff}s...")
                time.sleep(backoff)

        
        if data is None:
            raise RuntimeError("Fatal: Binance Futures API historical fetch aborted due to persistent network or rate-limit failures.")

        if not data:
            break

        df_chunk = pd.DataFrame(data, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_vol", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore"
        ])
        
        df_chunk["datetime"] = pd.to_datetime(df_chunk["timestamp"], unit="ms", utc=True)
        df_chunk[["open", "high", "low", "close", "volume"]] = df_chunk[["open", "high", "low", "close", "volume"]].astype(float)
        df_chunk = df_chunk[["open", "high", "low", "close", "volume", "datetime"]]

        all_data.append(df_chunk)
        last_ms = int(data[-1][const["zero_int"]])
        if last_ms >= end_ms:
            break
        current = last_ms + one_i
        
        request_count += 1
        # Print progress every 50 requests
        if request_count % const["fifty_int"] == const["zero_int"]:
            current_dt = df_chunk["datetime"].iloc[-1].strftime("%Y-%m-%d %H:%M:%S")
            print(f"[INFO] Download Progress: Fetch request {request_count} complete. Reached date: {current_dt}")

        if len(data) < limit:
            break
        time.sleep(data_cfg.get("binance", {}).get("sleep_time_f", const["half_float"]))

    if all_data:
        df_res = pd.concat(all_data, ignore_index=True)
        df_res = df_res[df_res["datetime"] <= end_ts]
        return df_res.sort_values("datetime").reset_index(drop=True)
    return pd.DataFrame()


def _classify_buy_sell_volume(ohlcv_df: pd.DataFrame, config: Dict) -> pd.DataFrame:
    """
    Sovereign config-driven Bulk Volume Classification (BVC) proxy.
    Calculates buy/sell volume fraction from standardized intraday returns
    mapped to a sigmoid cumulative probability curve.
    """
    const = config["reproducibility"]["constants"]
    one_f = const["one_float"]
    zero_f = const["zero_float"]
    epsilon = const["epsilon"]

    bvc_cfg = config.get("data", {}).get("bvc", {})
    std_window = bvc_cfg.get("std_window", const.get("twenty_four_int", 24))
    k = bvc_cfg.get("sigmoid_k", 1.5)
    z_clip_val = bvc_cfg.get("z_clip", 10.0)

    price_change = ohlcv_df["close"].pct_change().fillna(zero_f)
    roll_mean = price_change.rolling(std_window, min_periods=1).mean()
    roll_std = price_change.rolling(std_window, min_periods=1).std().clip(lower=epsilon)
    
    z = (price_change - roll_mean) / roll_std
    z = z.clip(-z_clip_val, z_clip_val)                          # prevents overflow
    
    buy_fraction = one_f / (one_f + np.exp(-k * z))
    
    total_vol = ohlcv_df["volume"]
    buy_vol = total_vol * buy_fraction
    sell_vol = total_vol - buy_vol

    return pd.DataFrame({
        "price": ohlcv_df["close"],
        "buy_vol": buy_vol,
        "sell_vol": sell_vol,
        "volume": total_vol
    }, index=ohlcv_df.index)


def generate_synthetic_trades(ohlcv_df: pd.DataFrame, config: Dict) -> pd.DataFrame:
    """
    Sovereign volume classification dispatcher.
    Routes to BVC if configured, otherwise falls back to deterministic SHA-256 splits.
    """
    data_cfg = config.get("data", {})
    method = data_cfg.get("volume_classification_method", "")
    if method == "bvc":
        return _classify_buy_sell_volume(ohlcv_df, config)

    import hashlib as _hashlib
    const = config["reproducibility"]["constants"]
    one_f = const["one_float"]
    vol = ohlcv_df["volume"].values

    datetimes = ohlcv_df["datetime"] if "datetime" in ohlcv_df.columns else ohlcv_df.index
    splits = np.empty(len(vol), dtype=np.float64)
    sixteen_int = const["sixteen_int"]
    hash_divisor = float(sixteen_int ** sixteen_int)
    for i, dt in enumerate(datetimes):
        dt_bytes = str(dt).encode("utf-8")
        hash_int = int(_hashlib.sha256(dt_bytes).hexdigest()[:sixteen_int], sixteen_int)
        splits[i] = hash_int / hash_divisor

    buy_vol = vol * splits
    sell_vol = vol * (one_f - splits)

    return pd.DataFrame({
        "price": ohlcv_df["close"],
        "buy_vol": buy_vol,
        "sell_vol": sell_vol,
        "volume": vol
    }, index=ohlcv_df.index)



def load_shard_data(symbol: str, config: Dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Loads causal OHLCV data, slices it to the configured start/end dates (plus warmup),
    and generates aligned trade volume imbalances.
    """
    candles = fetch_or_load_ohlcv(config, symbol=symbol)

    # Slice the loaded DataFrame to the active month shard if configured
    data_cfg = config["data"]
    start_str = data_cfg.get("fetch_start_date")
    end_str = _resolve_effective_end_date(config)

    if start_str and not candles.empty:
        start_ts = pd.Timestamp(start_str)
        if start_ts.tz is None:
            start_ts = start_ts.tz_localize("UTC")
            
        end_ts = pd.Timestamp(end_str)
        if end_ts.tz is None:
            end_ts = end_ts.tz_localize("UTC")

        # Slice data starting at (start_ts - warmup_bars) up to end_ts
        warmup = int(data_cfg.get("warmup_bars", 500))
        
        # Locate indices where datetime is greater than or equal to start_ts
        matching = candles[candles["datetime"] >= start_ts].index
        if len(matching) > 0:
            start_idx = max(0, matching[0] - warmup)
            end_matching = candles[candles["datetime"] < end_ts].index
            end_idx = end_matching[-1] + 1 if len(end_matching) > 0 else len(candles)
            
            candles = candles.iloc[start_idx:end_idx].reset_index(drop=True)

    agg = generate_synthetic_trades(candles, config)
    if "datetime" in candles.columns:
        candles["datetime"] = pd.to_datetime(candles["datetime"], utc=True)
        candles = candles.sort_values("datetime").reset_index(drop=True)
    return candles, agg


def load_shard_data_causal_only(symbol: str, config: Dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Like load_shard_data but with NO warmup prepend — for prior derivation only."""
    candles = fetch_or_load_ohlcv(config, symbol=symbol)
    data_cfg = config["data"]
    start_str = data_cfg.get("fetch_start_date")
    end_str = _resolve_effective_end_date(config)
    if start_str and not candles.empty:
        start_ts = pd.Timestamp(start_str)
        if start_ts.tz is None:
            start_ts = start_ts.tz_localize("UTC")
        end_ts = pd.Timestamp(end_str)
        if end_ts.tz is None:
            end_ts = end_ts.tz_localize("UTC")
        matching = candles[candles["datetime"] >= start_ts].index
        if len(matching) > 0:
            start_idx = matching[0]  # NO warmup subtraction
            end_matching = candles[candles["datetime"] < end_ts].index
            end_idx = end_matching[-1] + 1 if len(end_matching) > 0 else len(candles)
            candles = candles.iloc[start_idx:end_idx].reset_index(drop=True)
    agg = generate_synthetic_trades(candles, config)
    if "datetime" in candles.columns:
        candles["datetime"] = pd.to_datetime(candles["datetime"], utc=True)
        candles = candles.sort_values("datetime").reset_index(drop=True)
    return candles, agg


def _parse_retry_after_seconds(retry_after_value: str, fallback_seconds: float) -> float:
    """
    Parse HTTP Retry-After header into seconds.
    Supports either delta-seconds or IMF-fixdate formats.
    """
    try:
        parsed_seconds = float(retry_after_value)
        return max(parsed_seconds, 0.0)
    except (TypeError, ValueError):
        parsed_dt = email.utils.parsedate_to_datetime(str(retry_after_value))
        if parsed_dt is None:
            return float(fallback_seconds)

        now_utc = pd.Timestamp.now(tz="UTC").to_pydatetime()
        if parsed_dt.tzinfo is None:
            parsed_dt = parsed_dt.replace(tzinfo=now_utc.tzinfo)

        wait_seconds = (parsed_dt - now_utc).total_seconds()
        return max(float(wait_seconds), 0.0)
