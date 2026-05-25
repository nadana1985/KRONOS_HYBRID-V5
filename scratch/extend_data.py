import os
import time
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

def fetch_binance_kline(symbol, interval, start_str, end_str):
    url = "https://fapi.binance.com/fapi/v1/klines"
    
    start_ts = int(datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp() * 1000)
    end_ts = int(datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp() * 1000)
    
    all_klines = []
    current_ts = start_ts
    
    print(f"Fetching 5m OHLCV for {symbol} from {start_str} to {end_str}...")
    while current_ts < end_ts:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current_ts,
            "endTime": end_ts,
            "limit": 1500
        }
        
        response = requests.get(url, params=params)
        if response.status_code != 200:
            print(f"[!] Error fetching candles: {response.text}")
            time.sleep(2)
            continue
            
        data = response.json()
        if not data:
            break
            
        all_klines.extend(data)
        current_ts = data[-1][0] + 1
        print(f"  Fetched up to {datetime.fromtimestamp(data[-1][0]/1000, tz=timezone.utc)}")
        time.sleep(0.5)
        
    df = pd.DataFrame(all_klines, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume', 
        'close_time', 'quote_volume', 'trades', 'taker_buy_base', 
        'taker_buy_quote', 'ignore'
    ])
    
    df['datetime'] = pd.to_datetime(df['open_time'], unit='ms', utc=True)
    cols_to_fix = ['open', 'high', 'low', 'close', 'volume', 'quote_volume', 'taker_buy_base', 'taker_buy_quote']
    df[cols_to_fix] = df[cols_to_fix].apply(pd.to_numeric)
    
    return df

def fetch_binance_funding(symbol, start_str, end_str):
    url = "https://fapi.binance.com/fapi/v1/fundingRate"
    
    start_ts = int(datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp() * 1000)
    end_ts = int(datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp() * 1000)
    
    all_funding = []
    current_ts = start_ts
    
    print(f"Fetching Funding Rates for {symbol} from {start_str} to {end_str}...")
    while current_ts < end_ts:
        params = {
            "symbol": symbol,
            "startTime": current_ts,
            "limit": 1000
        }
        
        response = requests.get(url, params=params)
        if response.status_code != 200:
            print(f"[!] Error fetching funding: {response.text}")
            time.sleep(2)
            continue
            
        data = response.json()
        if not data:
            break
            
        all_funding.extend(data)
        current_ts = data[-1]['fundingTime'] + 1
        print(f"  Fetched funding up to {datetime.fromtimestamp(data[-1]['fundingTime']/1000, tz=timezone.utc)}")
        
        if data[-1]['fundingTime'] >= end_ts:
            break
        time.sleep(0.5)
        
    df = pd.DataFrame(all_funding)
    df['datetime'] = pd.to_datetime(df['fundingTime'], unit='ms', utc=True)
    df['funding_rate'] = df['fundingRate'].astype(float)
    
    df = df[(df['fundingTime'] >= start_ts) & (df['fundingTime'] <= end_ts)]
    return df[['datetime', 'funding_rate', 'fundingTime']]

def extend_pipeline():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from load_sovereign_config import load_sovereign_config

    config = load_sovereign_config("params_yaml.txt")
    symbol = config["miner"]["symbols"][0]
    start_time = config["data"]["fetch_start_date"]
    # Dynamic yesterday from config
    from datetime import datetime, timezone, timedelta
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    end_time = config["data"].get("fetch_end_date") or yesterday

    # Paths from config
    from pathlib import Path as _Path
    hybrid_raw = _Path(config["data"]["raw_ohlcv_path"]).parent
    hybrid_processed = _Path(config["data"]["processed_path"]).parent

    hybrid_raw.mkdir(parents=True, exist_ok=True)
    hybrid_processed.mkdir(parents=True, exist_ok=True)

    ohlcv_path = _Path(config["data"]["raw_ohlcv_path"])
    funding_path = hybrid_raw / "ethusdt_funding_extension.parquet"
    output_path = _Path(config["data"]["processed_path"])

    # 1. Fetch OHLCV
    ohlcv_df = fetch_binance_kline(symbol, "5m", start_time, end_time)
    ohlcv_df.to_parquet(ohlcv_path)
    print(f"[+] Saved raw OHLCV extension ({len(ohlcv_df)} rows) to: {ohlcv_path}")
    
    # 2. Fetch Funding
    funding_df = fetch_binance_funding(symbol, start_time, end_time)
    funding_df.to_parquet(funding_path)
    print(f"[+] Saved raw Funding extension ({len(funding_df)} rows) to: {funding_path}")
    
    # 3. Load Base Truth File — search in configured paths only
    base_options = [
        ohlcv_path,
        output_path,
    ]
    
    base_df = None
    for p in base_options:
        if p.exists():
            print(f"[+] Loading Base Truth Dataset: {p}")
            base_df = pd.read_parquet(p)
            break
            
    if base_df is None:
        raise FileNotFoundError("Base truth parquet file not found in ETHreverseEngineer/data/processed!")
        
    # 4. Merge Extensions (Bit-perfect ZOH logic)
    print("[*] Merging extension OHLCV with Funding (ZOH)...")
    ohlcv_sorted = ohlcv_df.sort_values('open_time')
    funding_sorted = funding_df.sort_values('fundingTime')
    
    merged_ext = pd.merge_asof(
        ohlcv_sorted, 
        funding_sorted, 
        left_on='open_time', 
        right_on='fundingTime', 
        direction='backward'
    )
    
    # Clean datetime columns
    if 'datetime_y' in merged_ext.columns:
        merged_ext = merged_ext.drop(columns=['datetime_y']).rename(columns={'datetime_x': 'datetime'})
        
    # Ensure all columns in base_df are present in merged_ext (filled with zero/NaN as in original specification)
    for col in base_df.columns:
        if col not in merged_ext.columns:
            merged_ext[col] = 0.0
            
    # Align column order
    merged_ext = merged_ext[base_df.columns]
    
    # Combine
    print("[*] Concatenating base truth with merged extension...")
    final_df = pd.concat([base_df, merged_ext], ignore_index=True)
    
    # Clean duplicates and sort chronologically
    final_df = final_df.drop_duplicates(subset=['open_time']).sort_values('open_time')
    
    # Truncate strictly to May 17, 2026, 00:00:00 UTC
    target_end = pd.to_datetime(end_time).tz_localize('UTC')
    final_df = final_df[final_df['datetime'] <= target_end]
    
    # Save output
    final_df.to_parquet(output_path)
    print(f"\n[SUCCESS] Extended truth dataset successfully created!")
    print(f"    Path:  {output_path}")
    print(f"    Rows:  {len(final_df)}")
    print(f"    Range: {final_df['datetime'].min()} to {final_df['datetime'].max()}")

if __name__ == "__main__":
    extend_pipeline()
