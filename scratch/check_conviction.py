import yaml
import pandas as pd
import numpy as np
import data_engine
import feature_builder_engine
import structural_engine
import neural_integration_engine
from collections import deque

def diagnostic():
    print("=== KRONOS DIAGNOSTIC ===")
    with open("params_yaml.txt") as f:
        cfg = yaml.safe_load(f)
    
    symbol = cfg["miner"]["symbols"][0]
    raw_candles, agg_trades = data_engine.load_shard_data(symbol, cfg)
    
    # Focus on the first shard
    shard_candles = raw_candles.iloc[:1000]
    shard_trades = agg_trades  # not partitioned here
    
    const = cfg["reproducibility"]["constants"]
    
    print("Computing precomputed matrices...")
    precomputed_structural_df = structural_engine.compute_slots_sovereign(
        shard_candles, shard_trades, cfg["feature_builder"]["structural"], cfg
    )
    precomputed_veto_composite = structural_engine.compute_veto_composite(
        precomputed_structural_df, cfg["feature_builder"]["structural"]["slot_15"], const
    )
    
    recent_convictions = deque(maxlen=cfg["feature_builder"]["gate"]["recent_conviction_window"])
    
    veto_passed_count = 0
    gate_passed_count = 0
    non_zero_embs = 0
    
    print("Running bar-by-bar sequence loop...")
    for idx in range(500, len(shard_candles)):
        veto_score = float(precomputed_veto_composite.iloc[idx])
        veto_passed = veto_score >= cfg["feature_builder"]["structural"]["veto_threshold"]
        
        if veto_passed:
            veto_passed_count += 1
            causal_candles = shard_candles.iloc[:idx + 1]
            
            # Run neural gate manually to inspect
            model = neural_integration_engine.load_verified_model(cfg)
            tokenizer = neural_integration_engine.load_verified_tokenizer(cfg)
            
            emb = neural_integration_engine.extract_embeddings(
                causal_candles, idx, model, tokenizer, cfg
            )
            
            norm = neural_integration_engine.compute_lp_norm(emb, cfg)
            thresh = neural_integration_engine.dynamic_threshold(pd.Series(list(recent_convictions)), cfg)
            neural_passed = norm >= thresh
            
            if np.any(emb != 0.0):
                non_zero_embs += 1
            
            recent_convictions.append(norm)
            
            # Build full DNA row
            dna_row = feature_builder_engine.build_full_dna_vector(
                shard_candles, shard_trades, idx, recent_convictions, cfg,
                precomputed_structural_df=precomputed_structural_df,
                precomputed_veto_composite=precomputed_veto_composite
            )
            
            quality = dna_row.get("slot_31", 0.0)
            flag = dna_row.get("signature_flag", False)
            
            if flag:
                gate_passed_count += 1
                
            if veto_passed_count <= 10:
                print(f"Bar {idx:4d} | Veto Score: {veto_score:.4f} | Neural Norm: {norm:.4f} | Thresh: {thresh:.4f} | Passed Neural: {neural_passed} | Quality: {quality:.4f} | Saved: {quality >= cfg['database']['min_quality_score']}", flush=True)
                
            if veto_passed_count >= 5:
                break
                
    print(f"\n--- Diagnostic Summary ---", flush=True)
    print(f"Total bars analyzed: {idx - 500 + 1}", flush=True)
    print(f"Bars passing structural veto (>= 0.65): {veto_passed_count}", flush=True)
    print(f"Bars producing non-zero embeddings: {non_zero_embs}", flush=True)
    print(f"Bars passing neural gate: {gate_passed_count}", flush=True)

if __name__ == "__main__":
    diagnostic()
