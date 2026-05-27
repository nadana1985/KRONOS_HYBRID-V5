import sys
import os
import pandas as pd
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from load_sovereign_config import load_sovereign_config
import neural_integration_engine
import structural_engine
import feature_builder_engine
import data_engine

def run_diagnostic():
    print("================ KRONOS CLOUD DIAGNOSTIC ================")
    
    # 1. Config Loading
    try:
        cfg = load_sovereign_config("params_yaml.txt")
        print("[OK] Loaded config successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to load config: {e}")
        return

    # 2. Model & Tokenizer loading test
    print("\n--- Model & Tokenizer Loading ---")
    try:
        model = neural_integration_engine.load_verified_model(cfg)
        if model is None:
            print("[ERROR] Model failed to load (returned None).")
        else:
            print(f"[OK] Model loaded successfully on device: {next(model.parameters()).device}")
            
        tokenizer = neural_integration_engine.load_verified_tokenizer(cfg)
        if tokenizer is None:
            print("[ERROR] Tokenizer failed to load (returned None).")
        else:
            print("[OK] Tokenizer loaded successfully.")
    except Exception as e:
        print(f"[ERROR] Exception during model/tokenizer load: {e}")
        import traceback
        traceback.print_exc()

    # 3. Data Check
    print("\n--- Data Check ---")
    symbol = cfg["miner"]["symbols"][0]
    raw_ohlcv_path = cfg["data"]["raw_ohlcv_path"]
    print(f"Checking raw OHLCV path: {raw_ohlcv_path}")
    if not os.path.exists(raw_ohlcv_path):
        print(f"[ERROR] Raw data file not found at: {raw_ohlcv_path}")
        return
    
    try:
        df = pd.read_parquet(raw_ohlcv_path)
        print(f"[OK] Loaded raw data: {len(df):,} bars. Columns: {list(df.columns)}")
        print(f"Data range: {df['datetime'].min()} to {df['datetime'].max()}")
    except Exception as e:
        print(f"[ERROR] Failed to load raw data parquet: {e}")
        return

    # 4. Run Slot 15 Veto checks on a sample slice
    print("\n--- Veto Gating Test (First 2000 bars) ---")
    try:
        # Load sample data
        candles, trades = data_engine.load_shard_data(symbol, cfg)
        slice_candles = candles.iloc[:2000].copy()
        slice_trades = trades.iloc[:2000].copy() if trades is not None else None
        
        # Precompute structural
        print("Computing structural slots...")
        struct_df = structural_engine.compute_slots_sovereign(
            slice_candles, slice_trades, cfg["feature_builder"]["structural"], cfg
        )
        const = cfg["reproducibility"]["constants"]
        veto_comp = structural_engine.compute_veto_composite(
            struct_df, cfg["feature_builder"]["structural"]["slot_15"], const
        )
        
        veto_threshold = cfg["feature_builder"]["structural"]["veto_threshold"]
        veto_passed_mask = veto_comp >= veto_threshold
        veto_passed_count = int(veto_passed_mask.sum())
        max_veto = float(veto_comp.max())
        
        print(f"Max veto score computed: {max_veto:.4f}")
        print(f"Veto threshold configured: {veto_threshold}")
        print(f"Bars passing veto check: {veto_passed_count} / {len(slice_candles)} ({veto_passed_count/len(slice_candles)*100:.2f}%)")
        
        if veto_passed_count > 0:
            print("\n--- Neural conviction test on first passing bar ---")
            first_passing_idx = int(np.where(veto_passed_mask)[0][0])
            print(f"First passing bar index: {first_passing_idx}")
            
            recent_conv = feature_builder_engine.init_conviction_buffer(cfg)
            conv, thresh, passed, emb, neural_avail = neural_integration_engine.compute_neural_gate(
                slice_candles,
                first_passing_idx,
                recent_conv,
                cfg["kronos_mini"],
                cfg["feature_builder"]["gate"],
                const
            )
            print(f"Conviction Score  : {conv}")
            print(f"Dynamic Threshold : {thresh}")
            print(f"Gate Passed       : {passed}")
            print(f"Embedding L2 norm : {float(np.linalg.norm(emb))}")
            
    except Exception as e:
        print(f"[ERROR] Exception during structural/neural test run: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_diagnostic()
