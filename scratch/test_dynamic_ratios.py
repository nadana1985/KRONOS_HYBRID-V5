import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import time
import pandas as pd
from load_sovereign_config import load_sovereign_config
from sovereign_prior_derivation_engine import derive_sovereign_priors

def run_test():
    print("Loading sovereign config...")
    config = load_sovereign_config("params_yaml.txt")
    
    # Enable dynamic ratios exclusively for this test run
    config["sovereign_derivation"]["enable_dynamic_ratios"] = True
    
    print("Loading OHLCV data sample...")
    df = pd.read_parquet("ethusdt_5m_extension_ohlcv.parquet")
    print(f"Total bars in parquet: {len(df):,}")
    
    # Take a representative causal shard window (e.g., 500 bars)
    sample_bars = 500
    df_sample = df.iloc[:sample_bars].copy()
    print(f"Using a causal window of {len(df_sample)} bars for test.")
    
    print("Running derive_sovereign_priors...")
    start_time = time.time()
    priors = derive_sovereign_priors(df_sample, config)
    elapsed = time.time() - start_time
    
    print(f"\n[PERFORMANCE] Shard Prior Derivation Time: {elapsed:.4f} seconds")
    
    audit = priors["_audit"]
    print(f"Dominant Cycle extracted: {audit['_dominant_cycle']} bars ({audit['_dominant_cycle_method']})")
    print(f"Dynamic Ratios active: {audit['_enable_dynamic_ratios_active']}")
    
    print("\nSample of static_vs_dynamic ratios:")
    import json
    # Print the comparison nicely formatted
    print(json.dumps(audit["_static_vs_dynamic_ratios"], indent=2))

if __name__ == "__main__":
    run_test()
