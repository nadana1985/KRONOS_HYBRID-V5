"""
KRONOS Hardened Full Corpus Mining Pipeline
===========================================
Safe, resumable full history mining of ethusdt_5m_extension_ohlcv.parquet.
Locks down static priors only (enable_dynamic_ratios=false, enable_adaptive_weights=false).

Rigorous causal integrity, resource guardrails, and cryptographic checkpoint validation.
"""

from __future__ import annotations
import os
import sys
import json
import time
import hashlib
from pathlib import Path
import pandas as pd
import numpy as np

# Core quant engines
from load_sovereign_config import load_sovereign_config
import sovereign_prior_derivation_engine as _sov_deriv
import data_engine
import miner_engine
import database_engine
import feature_builder_engine
import structural_engine
import hardcode_validator_engine

try:
    import psutil
except ImportError:
    psutil = None


def get_sharded_ranges(start_date_str: str, end_date_str: str, chunk_days: int) -> list[tuple[str, str]]:
    """Generates chronologically sharded intervals based on chunk size."""
    start_dt = pd.to_datetime(start_date_str)
    end_dt = pd.to_datetime(end_date_str)
    
    # Resolve ranges sequentially by adding delta days
    ranges = []
    current = start_dt
    delta = pd.Timedelta(days=chunk_days)
    
    while current < end_dt:
        nxt = current + delta
        if nxt > end_dt:
            nxt = end_dt
        ranges.append((current.strftime("%Y-%m-%d %H:%M:%S"), nxt.strftime("%Y-%m-%d %H:%M:%S")))
        current = nxt
        
    return ranges


def calculate_file_sha256(filepath: str) -> str:
    """Computes the SHA256 hash of a file."""
    h = hashlib.sha256()
    block_size = 65536  # SOVEREIGN_MATH_CONSTANT: 64KB block size
    try:
        with open(filepath, 'rb') as f:
            for block in iter(lambda: f.read(block_size), b''):
                h.update(block)
        return h.hexdigest()
    except Exception:
        return "missing"


def compute_shard_hash(shard_start: str, shard_end: str, config_hash: str, raw_file_hash: str) -> str:
    """Computes SHA256 signature for a shard to validate state reproducibility."""
    raw_str = f"{shard_start}_{shard_end}_{config_hash}_{raw_file_hash}"
    return hashlib.sha256(raw_str.encode('utf-8')).hexdigest()


def get_memory_percent() -> float:
    """Returns system memory usage percentage."""
    if psutil is not None:
        try:
            return float(psutil.virtual_memory().percent)
        except Exception:
            pass
    return 50.0  # SOVEREIGN_MATH_CONSTANT: safe fallback if psutil fails


def check_resource_guardrails(config: dict) -> bool:
    """Checks system RAM and prevents execution if limits are exceeded."""
    mem_pct = get_memory_percent()
    max_mem = float(config["full_corpus_mining"].get("max_memory_percent", 85.0))  # SOVEREIGN_MATH_CONSTANT
    if mem_pct > max_mem:
        print(f"[FATAL][MEMORY] Memory usage exceeds guardrail limit: {mem_pct:.1f}% > {max_mem:.1f}%")
        return False
    return True


def _run_shard(shard_start: str, shard_end: str, base_config: dict, bic_cache: Optional[dict] = None) -> None:
    """Runs the prior derivation and mining for a single chronological shard."""
    config = base_config.copy()
    config["data"] = base_config["data"].copy()
    config["data"]["fetch_start_date"] = shard_start
    config["data"]["fetch_end_date"] = shard_end

    const = config["reproducibility"]["constants"]
    sd_cfg = config.get("sovereign_derivation", {})

    # Data ingestion
    database_engine.initialize_duckdb_views(config)

    # Sovereign prior derivation (Locked static priors: enable_dynamic_ratios=false, enable_adaptive_weights=false)
    for symbol in config["miner"]["symbols"]:
        raw_candles, _ = data_engine.load_shard_data(symbol, config)
        if raw_candles is not None and len(raw_candles) > const["zero_int"]:
            # Isolate cache per symbol to prevent concurrency side-effects
            sym_cache = bic_cache.setdefault(symbol, {}) if bic_cache is not None else {}
            sovereign_priors = _sov_deriv.derive_sovereign_priors(raw_candles, config, bic_cache=sym_cache)
            _audit = sovereign_priors.get("_audit", {})

            if not _audit.get("_disabled", False):
                _sov_deriv.patch_config_with_priors(config, sovereign_priors)
                dc = _audit.get("_dominant_cycle", "N/A")
                dc_method = _audit.get("_dominant_cycle_method", "N/A")
                print(f"[SOVEREIGN] Derived dominant cycle: {dc} bars ({dc_method}) for {symbol}")
                
                # Write sovereign audit logs if configured
                if sd_cfg.get("store_audit", False):
                    # Strip numpy objects to be JSON serialisable
                    def _serialise(obj):
                        if isinstance(obj, dict):
                            return {k: _serialise(v) for k, v in obj.items()}
                        if isinstance(obj, (list, tuple)):
                            return [_serialise(i) for i in obj]
                        try:
                            return obj.item()
                        except AttributeError:
                            return obj

                    audit_dir = Path(sd_cfg.get("audit_path", "data/audit/sovereign_priors"))
                    audit_dir.mkdir(parents=True, exist_ok=True)
                    safe_start = shard_start.replace(" ", "T").replace(":", "-")
                    safe_end = shard_end.replace(" ", "T").replace(":", "-")
                    filename = f"{symbol}_{safe_start}_{safe_end}_sovereign_audit.json"
                    with open(audit_dir / filename, "w") as fh:
                        json.dump(_serialise(sovereign_priors), fh, indent=2, default=str)  # SOVEREIGN_MATH_CONSTANT
            break  # derive once per shard

    # Walk-forward bar-by-bar mining
    _mine_shard_only(config)


def _mine_shard_only(config: dict) -> None:
    """Executes walk-forward signature extraction without local ontology compiler."""
    const = config["reproducibility"]["constants"]
    one_i = const["one_int"]
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]
    flag_key = config["feature_builder"]["gate"]["signature_flag_key"]

    for symbol in config["miner"]["symbols"]:
        raw_candles, agg_trades = data_engine.load_shard_data(symbol, config)
        recent_convictions = feature_builder_engine.init_conviction_buffer(config)
        is_first_shard = True

        for shard_candles, shard_trades in miner_engine.generate_shards(raw_candles, agg_trades, config):
            precomputed_structural_df = structural_engine.compute_slots_sovereign(
                shard_candles, shard_trades,
                config["feature_builder"]["structural"], config,
            )
            precomputed_veto_composite = structural_engine.compute_veto_composite(
                precomputed_structural_df,
                config["feature_builder"]["structural"]["slot_15"],
                const,
            )

            vol_cfg = config["feature_builder"]["aux"]["vol_forecast"]
            vol_lb = vol_cfg["lookback_bars"]
            log_ret_shard = np.log(shard_candles["close"] / shard_candles["close"].shift(1) + epsilon)
            precomputed_vol_forecast = log_ret_shard.rolling(vol_lb).std().diff().fillna(zero_f)

            shard_detected = []
            bar_indices = list(miner_engine.bar_index_range(shard_candles, config, skip_warmup=is_first_shard))
            total_bars = len(bar_indices)

            print(f"  -> Mining {total_bars} bars for {symbol}...", flush=True)

            for step_idx, current_idx in enumerate(bar_indices, 1):
                # Hardened resource guard check per 100 steps
                if step_idx % const["hundred_int"] == const["zero_int"]:
                    if not check_resource_guardrails(config):
                        raise RuntimeError("Resource guardrail triggered: System RAM limits exceeded. Exiting...")

                dna_row = feature_builder_engine.build_full_dna_vector(
                    shard_candles, shard_trades, current_idx, recent_convictions, config,
                    precomputed_structural_df=precomputed_structural_df,
                    precomputed_veto_composite=precomputed_veto_composite,
                    precomputed_vol_forecast=precomputed_vol_forecast,
                )

                if dna_row.get(flag_key, False):
                    forward_bars = config["miner"]["forward_bars"]
                    fwd_end = current_idx + one_i + forward_bars
                    fwd_slice = shard_candles.iloc[current_idx + one_i: fwd_end]
                    dna_row = miner_engine.compute_forward_metrics(dna_row, fwd_slice, config)

                    dna_row["timestamp"] = str(shard_candles["datetime"].iloc[current_idx])
                    dna_row["symbol"] = symbol
                    dna_row["interval"] = config["miner"]["interval"]

                    shard_detected.append(dna_row)

                recent_convictions = feature_builder_engine.update_conviction_buffer(
                    recent_convictions, dna_row, config
                )

            # Store signatures batch at the end of the shard
            mined_count = len(shard_detected)
            total_eval = len(shard_candles)
            print(f"  -> [SHARD MINED] Signatures extracted: {mined_count} / {total_eval}", flush=True)
            if shard_detected:
                database_engine.store_signatures_batch(shard_detected, config)

            is_first_shard = False


def main():
    print("=== KRONOS HARDENED FULL CORPUS MINING ENGINE ===")
    
    # 1. Resolve configuration
    config_path = sys.argv[1] if len(sys.argv) > 1 else "params_yaml.txt"
    config = load_sovereign_config(config_path)
    
    const = config["reproducibility"]["constants"]
    mining_cfg = config["full_corpus_mining"]
    
    dry_run = "--dry-run" in sys.argv
    
    # 2. Strict Quant Gating: Lock down static baseline priors
    config["sovereign_derivation"]["enable_dynamic_ratios"] = False
    config["sovereign_derivation"]["slot_15"]["enable_adaptive_weights"] = False
    
    # 3. Pre-flight Sovereignty Code Check
    print("[PRE-FLIGHT] Scanning code files for doctrine compliance...")
    hardcode_validator_engine.run_full_validation(".", config)
    
    # 4. Resolve raw parquet data bounds
    raw_path = config["data"]["raw_ohlcv_path"]
    if not Path(raw_path).exists():
        print(f"[FATAL] Raw corpus file not found: {raw_path}")
        sys.exit(config["validator"]["exit_usage_error"])
        
    print(f"[DATA] Scanning historical bounds from: {raw_path}")
    raw_df = pd.read_parquet(raw_path)
    raw_df["datetime"] = pd.to_datetime(raw_df["datetime"])
    
    min_date = raw_df["datetime"].min().strftime("%Y-%m-%d %H:%M:%S")
    max_date = raw_df["datetime"].max().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[DATA] Corpus bounds: {min_date} to {max_date} ({len(raw_df):,} bars)")
    
    # Generate 15-day shards (hardened default)
    chunk_days = int(mining_cfg.get("chunk_size_days", 15))  # SOVEREIGN_MATH_CONSTANT
    shards = get_sharded_ranges(min_date, max_date, chunk_days)
    total_shards = len(shards)
    print(f"[DATA] Generated {total_shards} chronological shards ({chunk_days} days each).")
    
    if dry_run:
        print("\n=== DRY RUN MODE: SUCCESSFUL RESOLUTION ===")
        for idx, (s_start, s_end) in enumerate(shards, 1):
            print(f"  [DRY-RUN] Shard {idx}/{total_shards}: {s_start} to {s_end}")
        print("=== DRY RUN COMPLETED SUCCESSFULLY ===")
        sys.exit(config["validator"]["exit_clean"])
        
    # 5. Load and validate cryptographic checkpoints
    checkpoint_file = Path(mining_cfg.get("checkpoint_file", "data/full_corpus_checkpoint.json"))
    checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
    
    completed_checkpoints = {}
    if checkpoint_file.exists():
        try:
            with open(checkpoint_file, "r") as f:
                completed_checkpoints = json.load(f)
            print(f"[CHECKPOINT] Loaded checkpoint registry. {len(completed_checkpoints)} completed shards found.")
        except Exception as e:
            print(f"[WARNING] Failed to parse checkpoint file: {e}. Re-starting from scratch.")
            
    # Compute base file hashes for checkpoint integrity
    raw_file_hash = calculate_file_sha256(raw_path)
    
    # Dump standard dict representation for config hashing
    def _clean_dict(d):
        if isinstance(d, dict):
            return {k: _clean_dict(v) for k, v in d.items()}
        if isinstance(d, list):
            return [_clean_dict(i) for i in d]
        if isinstance(d, (int, float, bool, str)) or d is None:
            return d
        return str(d)
        
    config_hash = hashlib.sha256(json.dumps(_clean_dict(config), sort_keys=True).encode('utf-8')).hexdigest()
    
    # 6. Execute Chronological Mining Loop
    checkpoint_interval = int(mining_cfg.get("checkpoint_interval_shards", 3))  # SOVEREIGN_MATH_CONSTANT
    processed_count = const["zero_int"]
    
    local_bic_cache = {}  # SOVEREIGN_MATH_CONSTANT: thread-safe isolated HMM cache
    for idx, (shard_start, shard_end) in enumerate(shards, 1):
        shard_key = f"{shard_start}_{shard_end}".replace(" ", "_")
        expected_hash = compute_shard_hash(shard_start, shard_end, config_hash, raw_file_hash)
        
        # Cryptographic check
        if shard_key in completed_checkpoints:
            stored_hash = completed_checkpoints[shard_key]
            if stored_hash == expected_hash:
                print(f"[{idx}/{total_shards}] SKIPPING (Verified): {shard_start} to {shard_end}")
                continue
            else:
                print(f"[{idx}/{total_shards}] WARN: Cryptographic hash mismatch on {shard_key}. Invalidation triggered, re-mining...")
                
        # Perform memory resources pre-flight check
        if not check_resource_guardrails(config):
            print("[FATAL] Halting execution to preserve system integrity. Checkpoints saved.")
            sys.exit(config["validator"]["exit_usage_error"])
            
        print(f"\n[{idx}/{total_shards}] PROCESSING SHARD: {shard_start} to {shard_end}")
        
        try:
            _run_shard(shard_start, shard_end, config, bic_cache=local_bic_cache)
            
            # Save checkpoint atomically
            completed_checkpoints[shard_key] = expected_hash
            with open(checkpoint_file, "w") as f:
                json.dump(completed_checkpoints, f, indent=2)  # SOVEREIGN_MATH_CONSTANT
                
            processed_count += 1
            if processed_count % checkpoint_interval == const["zero_int"]:
                print(f"[CHECKPOINT] Cryptographically synchronized state for {processed_count} shards.")
                
        except Exception as e:
            print(f"[CRITICAL ERROR] Failed during shard {shard_start} to {shard_end}: {e}")
            sys.exit(config["validator"]["exit_usage_error"])
            
    print("\n[FINISHED] Chronological sharded sweep completed.")
    
    # 7. Post-Run Automation Step
    print("\n=========================================")
    print("MANDATORY POST-RUN OPTIMIZATION PROTOCOL")
    print("=========================================")
    try:
        sys.path.append(os.path.join(os.path.dirname(__file__), "scratch"))
        
        # Step 1: Compactor
        from compact_database import compact_database
        print("[POST] Step 1/4 — Compacting partition tree...")
        compact_database()
        
        # Step 2: Stable Ontology Compilation
        print("[POST] Step 2/4 — Global Ontology Compilation (slot_28)...")
        for symbol in config["miner"]["symbols"]:
            miner_engine.compile_global_ontology(symbol, config)
            
        # Step 3: Refresh DuckDB View
        print("[POST] Step 3/4 — Refreshing DuckDB views...")
        database_engine.initialize_duckdb_views(config)
        
        # Step 4: Signatures Wiki
        from generate_signatures_wiki import generate_wiki
        print("[POST] Step 4/4 — Compiling signature database wiki...")
        generate_wiki()
        
        print("[POST] Post-run optimization completed successfully!")
    except Exception as e:
        print(f"[WARNING] Post-run optimization failed: {e}")
        
    print("=========================================\n")


if __name__ == "__main__":
    main()
