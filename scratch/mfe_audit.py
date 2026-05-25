import pandas as pd
import numpy as np
import os, sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from load_sovereign_config import load_sovereign_config

def run_mfe_audit():
    cfg = load_sovereign_config("params_yaml.txt")
    import data_engine
    import structural_engine

    print("Loading raw candles...")
    candles, trades = data_engine.load_shard_data("ETHUSDT", cfg)
    
    # We will use the first 15,000 bars for a comprehensive sample
    slice_len = 15000
    print(f"Loaded {len(candles):,} bars. Slicing first {slice_len:,} bars for structural precomputations...")
    candles_slice = candles.iloc[:slice_len].copy()
    trades_slice = trades.iloc[:slice_len].copy() if trades is not None else None

    struct_df = structural_engine.compute_slots_sovereign(
        candles_slice, trades_slice, cfg["feature_builder"]["structural"], cfg
    )
    const = cfg["reproducibility"]["constants"]
    veto_comp = structural_engine.compute_veto_composite(
        struct_df, cfg["feature_builder"]["structural"]["slot_15"], const
    )

    forward_bars = cfg["miner"]["forward_bars"]  # 288
    epsilon = const["epsilon"]

    mfes = []
    for i in range(len(candles_slice) - forward_bars - 1):
        entry_price = float(candles_slice["open"].iloc[i + 1])
        highs = candles_slice["high"].iloc[i + 1 : i + 1 + forward_bars].values
        mfe = float((highs.max() - entry_price) / (entry_price + epsilon))
        mfes.append(mfe)

    # Align arrays
    veto_scores = veto_comp.iloc[:len(mfes)].values
    mfes = np.array(mfes)

    df_analysis = pd.DataFrame({"veto": veto_scores, "mfe": mfes})

    low_veto = df_analysis[df_analysis["veto"] < 0.65]
    high_veto = df_analysis[df_analysis["veto"] >= 0.65]

    print("\n================ MFE AUDIT RESULTS ================")
    print(f"Total bars analyzed: {len(df_analysis):,}")
    print(f"Low Veto group (< 0.65) count:  {len(low_veto):,} bars")
    print(f"High Veto group (>= 0.65) count: {len(high_veto):,} bars")
    print("---------------------------------------------------")
    
    max_low_mfe = low_veto["mfe"].max() if len(low_veto) > 0 else 0.0
    mean_low_mfe = low_veto["mfe"].mean() if len(low_veto) > 0 else 0.0
    
    max_high_mfe = high_veto["mfe"].max() if len(high_veto) > 0 else 0.0
    mean_high_mfe = high_veto["mfe"].mean() if len(high_veto) > 0 else 0.0

    print(f"Low Veto (< 0.65)  - Max MFE: {max_low_mfe*100:.4f}% | Mean MFE: {mean_low_mfe*100:.4f}%")
    print(f"High Veto (>= 0.65) - Max MFE: {max_high_mfe*100:.4f}% | Mean MFE: {mean_high_mfe*100:.4f}%")
    
    if len(low_veto) > 0 and len(high_veto) > 0:
        improvement = (mean_high_mfe / (mean_low_mfe + 1e-9)) - 1.0
        print(f"\n[OK] High Veto signals yield a {improvement*100:.2f}% relative increase in average MFE!")

if __name__ == "__main__":
    run_mfe_audit()
