"""
KRONOS Sharded Orchestrator Loop
================================
Automates monthly execution of the quantitative mining pipeline.
Includes an intelligent stop-start-resume checkpointing mechanism.

Execution order:
  - Mine all monthly shards sequentially (slot twenty-eight placeholder during mining)
  - Compact the raw partition tree into compact parquet file
  - Run the Global Ontology Compiler ONCE on the full corpus → writes stable slot labels
  - Refresh DuckDB view to reflect the final compacted + ontology-compiled database
  - Generate the signatures wiki
"""
import os
import json
import pandas as pd
from pathlib import Path
from typing import Optional
from load_sovereign_config import load_sovereign_config
import orchestrator_engine
import miner_engine
import database_engine


def get_monthly_ranges(start_date_str: str, end_date_str: str):
    """Generates monthly interval tuples from start to end dates."""
    start_dt = pd.to_datetime(start_date_str)
    end_dt = pd.to_datetime(end_date_str)

    # Generate month start dates
    dates = pd.date_range(start=start_dt, end=end_dt, freq="MS")

    ranges = []
    # Add first segment if start_dt is not exactly on the first of the month
    current = start_dt
    for d in dates:
        if d > current:
            ranges.append((current.strftime("%Y-%m-%d %H:%M:%S"), d.strftime("%Y-%m-%d %H:%M:%S")))
            current = d

    # Add last segment up to end_dt
    if current < end_dt:
        ranges.append((current.strftime("%Y-%m-%d %H:%M:%S"), end_dt.strftime("%Y-%m-%d %H:%M:%S")))

    return ranges


def _run_shard(shard_start: str, shard_end: str, base_config: dict, bic_cache: Optional[dict] = None) -> None:
    """
    Runs the mining-only portion of the pipeline for a single monthly shard.
    Deliberately does NOT trigger compile_global_ontology here — that runs
    globally after all shards complete, on the full corpus.

    Sovereign Prior Derivation (when sovereign_derivation.enabled=true):
      After data ingestion, the full causal OHLCV shard is passed to
      sovereign_prior_derivation_engine.derive_sovereign_priors() which
      derives all derived priors empirically and patches them back into config
      before the bar-by-bar mining loop runs. This ensures every shard
      mines with priors adapted to the market structure visible up to that
      shard — not static researcher estimates.
    """
    import structural_engine
    import data_engine
    import feature_builder_engine
    import sovereign_prior_derivation_engine as _sov_deriv
    config = load_sovereign_config("params_yaml.txt")
    config["data"]["fetch_start_date"] = shard_start
    config["data"]["fetch_end_date"] = shard_end

    const = config["reproducibility"]["constants"]
    sd_cfg = config.get("sovereign_derivation", {})

    # Pre-flight sovereignty check
    import hardcode_validator_engine
    hardcode_validator_engine.run_full_validation(".", config)

    # Data ingestion
    database_engine.initialize_duckdb_views(config)

    # ── SOVEREIGN PRIOR DERIVATION ──────────────────────────────────────────────
    # Load the causal OHLCV slice to derive priors from observed market structure.
    # We load the raw OHLCV for the shard (no look-ahead — strictly causal).
    if sd_cfg.get("enabled", True):
        try:
            for symbol in config["miner"]["symbols"]:
                raw_candles, _ = data_engine.load_shard_data(symbol, config)
                if raw_candles is not None and len(raw_candles) > const["zero_int"]:
                    # Isolate cache per symbol to prevent concurrency side-effects
                    sym_cache = bic_cache.setdefault(symbol, {}) if bic_cache is not None else {}
                    sovereign_priors = _sov_deriv.derive_sovereign_priors(
                        raw_candles, config, bic_cache=sym_cache
                    )
                    _audit = sovereign_priors.get("_audit", {})

                    if not _audit.get("_disabled", False):
                        # Patch config in-place before mining loop
                        _sov_deriv.patch_config_with_priors(config, sovereign_priors)

                        dc = _audit.get("_dominant_cycle", "N/A")
                        dc_method = _audit.get("_dominant_cycle_method", "N/A")
                        rv_med = _audit.get("_rv_median", 0.0)
                        rv_iqr = _audit.get("_rv_iqr", 0.0)
                        print(
                            f"[SOVEREIGN] {symbol} | Shard {shard_start}–{shard_end} | "
                            f"dominant_cycle={dc} bars ({dc_method}) | "
                            f"rv_median={rv_med:.6f} rv_iqr={rv_iqr:.6f} | "
                            f"n_causal_bars={_audit.get('_n_causal_bars', 0):,}"
                        )

                        # Persist audit JSON when store_audit=true
                        if sd_cfg.get("store_audit", False):
                            _persist_sovereign_audit(
                                sovereign_priors, symbol, shard_start, shard_end, sd_cfg
                            )
                    else:
                        print(
                            f"[SOVEREIGN] DISABLED for {symbol} — ablation baseline active. "
                            f"All priors remain at params_yaml.txt values."
                        )
                    break  # derive once per shard (shared candle structure across symbols)
        except Exception as sov_exc:
            print(
                f"[SOVEREIGN][WARNING] Prior derivation failed for shard "
                f"{shard_start}–{shard_end}: {sov_exc}. "
                f"Proceeding with static params_yaml.txt priors."
            )

    # Mining only — note: compile_global_ontology is suppressed per-shard.
    # We call _mine_shard directly to bypass the per-symbol ontology call in run_miner.
    _mine_shard_only(config)


def _mine_shard_only(config: dict) -> None:
    """
    Executes the bar-by-bar mining loop for all configured symbols WITHOUT
    triggering compile_global_ontology. The Ontology Compiler is reserved for
    the single global post-run pass after all shards are complete.
    """
    import data_engine
    import feature_builder_engine
    import numpy as np
    import time

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
            import structural_engine
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
            
            start_time = time.time()
            last_print_time = start_time
            
            print(f"  -> Starting walk-forward loop on {total_bars} bars for {symbol}...", flush=True)

            for step_idx, current_idx in enumerate(bar_indices, 1):
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
                
                # Periodic step logging for background task log visibility
                current_time = time.time()
                if step_idx % const["hundred_int"] == const["zero_int"] or step_idx == const["one_int"] or step_idx == total_bars or (current_time - last_print_time) > float(const["thirty_int"]):
                    elapsed = current_time - start_time
                    latency_per_bar = elapsed / step_idx
                    pct = (step_idx / total_bars) * float(const["hundred_int"])
                    mined = len(shard_detected)
                    print(
                        f"[PROGRESS] {symbol} | Bar {step_idx}/{total_bars} ({pct:.2f}%) | "
                        f"Mined: {mined} | Elapsed: {elapsed:.1f}s | "
                        f"Speed: {latency_per_bar:.4f}s/bar | "
                        f"Candle: {shard_candles['datetime'].iloc[current_idx]}",
                        flush=True
                    )
                    last_print_time = current_time

            # Batch write at end of shard
            mined_count = len(shard_detected)
            total_eval = len(shard_candles)
            discarded = total_eval - mined_count
            print(f"  -> [SHARD STATS] Bars Evaluated: {total_eval:,} | Signatures Mined: {mined_count:,} | Discarded: {discarded:,} ({discarded/total_eval:.2%})", flush=True)
            
            if shard_detected:
                database_engine.store_signatures_batch(shard_detected, config)

            is_first_shard = False



def main():
    checkpoint_file = Path("data/shard_checkpoint.json")
    checkpoint_file.parent.mkdir(parents=True, exist_ok=True)

    # Load base configuration — single source of truth
    base_config = load_sovereign_config("params_yaml.txt")

    # Resolve start date exclusively from config — no inline literal fallback
    start_val = base_config["data"].get("fetch_start_date")
    if start_val is None or str(start_val).lower().strip() in ("null", "none", ""):
        raise RuntimeError(
            "fetch_start_date is not set in params_yaml.txt. "
            "Set data.fetch_start_date to a valid datetime string."
        )
    start_date = str(start_val)

    yesterday = (pd.Timestamp.utcnow().normalize() - pd.Timedelta(seconds=base_config["reproducibility"]["constants"]["one_int"])).strftime("%Y-%m-%d %H:%M:%S")
    end_val = base_config["data"].get("fetch_end_date")
    if end_val is None or str(end_val).lower().strip() in ("null", "none", ""):
        end_date = yesterday
    else:
        end_date = str(end_val)

    print(f"=== KRONOS SHARDED ORCHESTRATOR LOOP ===")
    print(f"Full Range: {start_date} to {end_date}")

    # Resolve all monthly shards
    shards = get_monthly_ranges(start_date, end_date)
    print(f"Total shards generated: {len(shards)} monthly blocks.")

    # Load checkpoint if exists
    completed_shards = []
    if checkpoint_file.exists():
        try:
            with open(checkpoint_file, "r") as f:
                completed_shards = json.load(f)
            print(f"Loaded checkpoint. {len(completed_shards)} shards already mined. Resuming...")
        except Exception:
            pass

    symbol_bic_caches = {symbol: {} for symbol in base_config["miner"]["symbols"]}  # SOVEREIGN_MATH_CONSTANT

    # ── PHASE 1: MINE ALL SHARDS (slot_28 = 0.0 placeholder throughout) ──────
    for idx, (shard_start, shard_end) in enumerate(shards, 1):
        shard_key = f"{shard_start}_{shard_end}"
        if shard_key in completed_shards:
            print(f"[{idx}/{len(shards)}] Skipping already completed shard: {shard_start} to {shard_end}")
            continue

        print(f"\n=========================================")
        print(f"[{idx}/{len(shards)}] PROCESSING SHARD: {shard_start} to {shard_end}")
        print(f"=========================================")

        try:
            _run_shard(shard_start, shard_end, base_config, bic_cache=symbol_bic_caches)

            completed_shards.append(shard_key)
            with open(checkpoint_file, "w") as f:
                json.dump(completed_shards, f)
            print(f"[OK] Shard {shard_start} to {shard_end} completed and checkpointed.")
        except Exception as e:
            print(f"[ERROR] Processing shard {shard_start} to {shard_end}: {e}")
            print("Stopping orchestrator loop. Restart the script to resume from this shard.")
            break

    print("\n[FINISHED] All shards mined.")

    # ── PHASE 2: POST-RUN OPTIMIZATION (only when all shards are complete) ───
    if len(completed_shards) == len(shards):
        print("\n=========================================")
        print("POST-RUN OPTIMIZATION PROTOCOL")
        print("=========================================")

        try:
            import sys
            sys.path.append(os.path.join(os.path.dirname(__file__), "scratch"))

            # STEP 1: Compact partition tree → single signatures_compact.parquet
            # This must run BEFORE the Ontology Compiler so the compiler has the full corpus.
            from compact_database import compact_database
            print("[POST] Step 1/3 — Compacting partition tree into single Parquet file...")
            compact_database()

            # STEP 2: Global Ontology Compiler — runs ONCE on the complete corpus.
            # Assigns globally-stable slot_28 phylum labels and overwrites the compact file.
            print("[POST] Step 2/3 — Running Global Ontology Compiler on full corpus...")
            final_config = load_sovereign_config("params_yaml.txt")
            for symbol in final_config["miner"]["symbols"]:
                miner_engine.compile_global_ontology(symbol, final_config)

            # STEP 3: Refresh DuckDB view to reflect updated compact parquet with slot_28 labels
            print("[POST] Step 3/3 — Refreshing DuckDB view...")
            database_engine.initialize_duckdb_views(final_config)

            # STEP 4: Generate quantitative wiki
            from generate_signatures_wiki import generate_wiki
            print("[POST] Generating quantitative signature database wiki...")
            generate_wiki()

            print("[POST] Post-run optimization completed successfully!")
        except Exception as e:
            print(f"[WARNING] Post-run optimization steps failed: {e}")

        print("=========================================\n")


def _persist_sovereign_audit(
    sovereign_priors: dict,
    symbol: str,
    shard_start: str,
    shard_end: str,
    sd_cfg: dict,
) -> None:
    """
    Writes the sovereign prior derivation audit dict to a timestamped JSON file.
    Filename: {symbol}_{shard_start}_{shard_end}_sovereign_audit.json
    The audit path is created if it does not exist.
    Errors are caught and printed without interrupting the pipeline.
    """
    import json
    from pathlib import Path

    try:
        audit_dir = Path(sd_cfg.get("audit_path", "data/audit/sovereign_priors"))
        audit_dir.mkdir(parents=True, exist_ok=True)

        # Sanitise shard timestamps for use in filenames (replace spaces/colons)
        safe_start = shard_start.replace(" ", "T").replace(":", "-")
        safe_end = shard_end.replace(" ", "T").replace(":", "-")
        filename = f"{symbol}_{safe_start}_{safe_end}_sovereign_audit.json"
        out_path = audit_dir / filename

        # Strip non-serialisable values (numpy types) before writing
        def _make_serialisable(obj):
            if isinstance(obj, dict):
                return {k: _make_serialisable(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_make_serialisable(i) for i in obj]
            try:
                # Handles numpy int64, float32, bool_, etc.
                return obj.item()
            except AttributeError:
                return obj

        payload = _make_serialisable(sovereign_priors)

        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, default=str)

        print(f"[SOVEREIGN][AUDIT] Written: {out_path}")

    except Exception as exc:
        print(f"[SOVEREIGN][AUDIT][WARNING] Failed to write audit file: {exc}")


if __name__ == "__main__":
    main()
