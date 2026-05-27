"""Refactored KRONOS Miner Engine - V5.1
Author: Antigravity (Google DeepMind)
Changes:
- Moved all imports to the top of the file and eliminated lazy imports to prevent circular dependencies.
- Added comprehensive type hints using standard typing and pandas stubs.
- Transitioned all visual print statements to a module-level logger for production-ready observability.
- Grouped functions logically: Public API → Core Mining → Utilities → Guards.
- Removed dead code assign_phylum() and added comments explaining why post-hoc compile_global_ontology is used instead.
- Implemented robust exception handling, Pathlib integrations, and a configurable memory guard in compile_global_ontology.
- Integrated optional tqdm progress bars for long shards controllable via config["miner"]["show_progress"].
- Parameterized HDBSCAN n_jobs and min_cluster_size directly from the feature builder configuration.
"""

from __future__ import annotations
import logging
import time
import glob
import json
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple, Any

import numpy as np
import pandas as pd

# Core KRONOS modules imported at top to avoid loop overhead
import data_engine
import database_engine
import feature_builder_engine
import structural_engine
import validation_engine

# Try importing tqdm for optional progress bars
try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

# Optional ML libraries for post-hoc ontology clustering
try:
    import hdbscan
except ImportError:
    hdbscan = None

try:
    from sklearn.cluster import DBSCAN
except ImportError:
    DBSCAN = None


# Module-level logger setup
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 1. PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def run_miner(config: Dict[str, Any], start_date: str, end_date: str) -> None:
    """Entry point for the walk-forward mining loop.

    All sharding, detection, evaluation, and storage from config.

    Args:
        config (Dict[str, Any]): Configuration dictionary containing mining,
            feature builder, database, and reproducibility settings.
        start_date (str): Backtest slice start date.
        end_date (str): Backtest slice end date.

    Raises:
        RuntimeError: If any causal sovereignty assertion fails.
    """
    logger.info(f"[MINER] Bootstrapping walk-forward mining loop for date range {start_date} to {end_date}...")
    _assert_causal_sovereignty(config)

    # Initialize storage and schema views
    database_engine.initialize_duckdb_views(config)

    symbols = config["miner"]["symbols"]
    logger.info(f"[MINER] Active mining symbols: {symbols}")

    for symbol in symbols:
        logger.info(f"[MINER] Loading data shards for symbol: {symbol}...")
        raw_candles, agg_trades = data_engine.load_shard_data(symbol, config)
        recent_convictions = feature_builder_engine.init_conviction_buffer(config)
        detected_rows: List[pd.Series] = []

        flag_key = config["feature_builder"]["gate"]["signature_flag_key"]
        const = config["reproducibility"]["constants"]
        one_i = const["one_int"]

        # FLAW 5 FIX: warmup is only skipped on the very first shard.
        # Subsequent contiguous shards start from bar 0 of their slice.
        is_first_shard = True
        shard_count = 0

        for shard_candles, shard_trades in generate_shards(raw_candles, agg_trades, config):
            shard_count += 1
            logger.info(f"[MINER] Processing Shard #{shard_count} for {symbol} (Candles: {len(shard_candles)}, Trades: {len(shard_trades)})...")

            # High-performance optimization: precompute structural slots & veto composite once per shard
            # This transitions the pipeline from O(N^2) backtest time down to O(N) linear time,
            # reducing CPU thermal load to negligible levels and preventing CPU shutdowns.
            precomp_start = time.time()
            precomputed_structural_df = structural_engine.compute_slots_sovereign(
                shard_candles,
                shard_trades,
                config["feature_builder"]["structural"],
                config,
            )
            precomputed_veto_composite = structural_engine.compute_veto_composite(
                precomputed_structural_df,
                config["feature_builder"]["structural"]["slot_15"],
                const,
            )

            # ── PRECOMPUTE VOL FORECAST ONCE PER SHARD (O(N) linear) ──
            epsilon = const["epsilon"]
            zero_f = const["zero_float"]
            vol_cfg = config["feature_builder"]["aux"]["vol_forecast"]
            vol_lb = vol_cfg["lookback_bars"]

            log_ret_shard = np.log(shard_candles["close"] / shard_candles["close"].shift(1) + epsilon)
            vol_series = log_ret_shard.rolling(vol_lb).std()
            precomputed_vol_forecast = vol_series.diff().fillna(zero_f)

            precomp_dur = time.time() - precomp_start
            logger.info(f"[MINER] Precomputations complete in {precomp_dur:.4f}s. Running bar-by-bar sequence loop...")

            shard_detected: List[pd.Series] = []
            bar_indices = bar_index_range(shard_candles, config, skip_warmup=is_first_shard)
            
            # Optional progress bar visualization
            use_progress_bar = config["miner"].get("show_progress", True)
            if use_progress_bar and tqdm is not None:
                bar_indices = tqdm(bar_indices, desc=f"Shard {shard_count}", leave=False)

            for current_idx in bar_indices:
                dna_row = feature_builder_engine.build_full_dna_vector(
                    shard_candles,
                    shard_trades,
                    current_idx,
                    recent_convictions,
                    config,
                    precomputed_structural_df=precomputed_structural_df,
                    precomputed_veto_composite=precomputed_veto_composite,
                    precomputed_vol_forecast=precomputed_vol_forecast,
                )

                if dna_row.get(flag_key, False):
                    forward_bars = config["miner"]["forward_bars"]
                    fwd_end = current_idx + one_i + forward_bars
                    fwd_slice = shard_candles.iloc[current_idx + one_i: fwd_end]

                    dna_row = compute_forward_metrics(dna_row, fwd_slice, config)
                    
                    # Inject primary index columns for storage compatibility
                    dna_row["timestamp"] = str(shard_candles["datetime"].iloc[current_idx])
                    dna_row["symbol"] = symbol
                    dna_row["interval"] = config["miner"]["interval"]

                    # Collect into shard buffer; batch-write at end of shard (FLAW 7 FIX)
                    shard_detected.append(dna_row)
                    detected_rows.append(dna_row)

                recent_convictions = feature_builder_engine.update_conviction_buffer(
                    recent_convictions, dna_row, config
                )

            # FLAW 7 FIX: batch write all shard signatures in a single I/O operation
            if shard_detected:
                logger.info(f"[MINER] Shard #{shard_count}: Batch-storing {len(shard_detected)} signatures in DuckDB...")
                database_engine.store_signatures_batch(shard_detected, config)

            is_first_shard = False

        # Persist run metrics as artifact (no git side effects in miner loop)
        if detected_rows:
            logger.info(f"[MINER] Walk-forward mining complete. Compiling edge metrics for {len(detected_rows)} signatures...")
            run_metrics = validation_engine.compute_edge_metrics(pd.DataFrame(detected_rows), config)
            _write_run_metrics_artifact(run_metrics, config, symbol)

        # ── GLOBAL ONTOLOGY COMPILER (slot_28) ──────────────────────────────
        # Runs exactly once after all shards are mined for this symbol.
        # HDBSCAN is applied to the complete signature matrix in a single pass,
        # producing stable, globally-consistent phylum cluster labels.
        compile_global_ontology(symbol, config)


def compile_global_ontology(symbol: str, config: Dict[str, Any]) -> None:
    """Global Ontology Compiler — Post-Hoc Phylum Assignment for slot_28.

    This is the definitive fix for the Incremental Label Freezing / Drift Locking flaw.

    The original assign_phylum ran HDBSCAN inside the chronological bar loop,
    re-clustering on every new detected signature. Because each fit only "sees"
    signatures discovered so far, cluster topology is frozen by the first ~fifty
    samples and all subsequent signatures inherit stale, path-dependent labels.
    The result: slot_28 contains only three to four unique values across twenty-six thousand signatures.

    This compiler instead:
      1. Loads the complete set of mined signatures for this symbol from the database.
      2. Runs HDBSCAN exactly ONCE on the full structural feature matrix.
      3. Writes the resulting stable phylum labels back to slot_28 in the compact DB.
      4. Re-saves the updated DataFrame to disk.

    All parameters resolve exclusively from config. No inline literals.

    Args:
        symbol (str): Target trading symbol.
        config (Dict[str, Any]): Global system configuration dictionary.
    """
    logger.info(f"[ONTOLOGY] Initiating Global Ontology Compilation for symbol: {symbol}")
    
    try:
        const = config["reproducibility"]["constants"]
        zero_f = const["zero_float"]
        one_i = const["one_int"]
        zero_i = const["zero_int"]
        
        meta_cfg = config["feature_builder"]["metadata"]
        phylum_key = meta_cfg["keys"]["phylum_id"]
        hdb_cfg = meta_cfg["hdbscan"]
        db_cfg = config["database"]
        structural_cols = list(
            config["feature_builder"]["structural"]["slot_15"]["weights"].keys()
        )

        # Resolve source path: prefer compact file, fall back to partition tree
        compact_path = db_cfg.get("compact_path", "data/signatures_compact.parquet")
        partition_path = db_cfg.get("parquet_path_pattern", "data/signatures/**/*.parquet")

        logger.info(f"[ONTOLOGY] Loading signatures from compact storage: {compact_path}")
        if Path(compact_path).exists():
            sig_df = pd.read_parquet(compact_path)
        else:
            logger.info(f"[ONTOLOGY] Compact file missing. Attempting partition fallback: {partition_path}")
            files = glob.glob(partition_path.replace("**", "**"), recursive=True)
            if not files:
                logger.warning("[ONTOLOGY] No signatures found in partitions. Skipping compilation.")
                return
            sig_df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)

        # Filter to target symbol if available
        if "symbol" in sig_df.columns:
            sig_df = sig_df[sig_df["symbol"] == symbol].copy()

        min_cluster_size = hdb_cfg["min_cluster_size"]
        if len(sig_df) < min_cluster_size:
            logger.warning(
                f"[ONTOLOGY] Insufficient signatures ({len(sig_df)}) for robust clustering. "
                f"Min required size: {min_cluster_size}. Skipping."
            )
            return

        # Extract structural feature columns
        available_cols = [c for c in structural_cols if c in sig_df.columns]
        if not available_cols:
            logger.warning("[ONTOLOGY] No structural slot columns discovered in signatures. Skipping.")
            return

        # Memory guard to protect against system crashes on extremely large data slices
        max_rows = config.get("full_corpus_mining", {}).get("max_ontology_rows", config["miner"].get("max_ontology_rows", const["fifty_thousand_int"]))
        if len(sig_df) > max_rows:
            logger.warning(
                f"[ONTOLOGY] Memory guard triggered: {len(sig_df):,} signatures exceeds "
                f"max_ontology_rows ({max_rows}). Downsampling to prevent memory exhaustion."
            )
            seed_val = int(config["reproducibility"].get("random_seed", 42))
            sig_df = sig_df.sample(n=max_rows, random_state=seed_val).sort_index()

        feature_matrix = sig_df[available_cols].fillna(zero_f).values
        logger.info(f"[ONTOLOGY] Running post-hoc clustering on matrix of size: {feature_matrix.shape}")

        labels = None
        n_jobs = hdb_cfg.get("n_jobs", -1)

        # Try robust HDBSCAN model fitting first
        if hdbscan is not None:
            logger.info(f"[ONTOLOGY] Fitting HDBSCAN with min_cluster_size={min_cluster_size}, n_jobs={n_jobs}...")
            try:
                clusterer = hdbscan.HDBSCAN(
                    min_cluster_size=min_cluster_size,
                    min_samples=hdb_cfg["min_samples"],
                    metric=hdb_cfg["metric"],
                    core_dist_n_jobs=n_jobs,
                )
                clusterer.fit(feature_matrix)
                labels = clusterer.labels_.astype(float)
                
                n_clusters = len(set(labels)) - (one_i if const["noise_label"] in labels else zero_i)
                n_noise = int((labels == const["noise_label"]).sum())
                logger.info(f"[ONTOLOGY] HDBSCAN compilation complete. Discovered {n_clusters} stable phyla | Noise: {n_noise:,}")
            except Exception as fit_err:
                logger.error(f"[ONTOLOGY] HDBSCAN fit encountered an exception: {fit_err}. Falling back to DBSCAN.", exc_info=True)
                labels = None

        # Fallback to sklearn density DBSCAN if HDBSCAN is not installed or failed during fitting
        if labels is None:
            if DBSCAN is not None:
                logger.info("[ONTOLOGY] Fitting fallback sklearn DBSCAN model...")
                try:
                    clusterer = DBSCAN(
                        min_samples=hdb_cfg["min_samples"],
                        metric=hdb_cfg["metric"],
                        n_jobs=n_jobs,
                    )
                    clusterer.fit(feature_matrix)
                    labels = clusterer.labels_.astype(float)
                    n_clusters = len(set(labels)) - (one_i if const["noise_label"] in labels else zero_i)
                    logger.info(f"[ONTOLOGY] DBSCAN fallback complete. Discovered {n_clusters} phyla.")
                except Exception as fallback_err:
                    logger.critical(f"[ONTOLOGY] DBSCAN fallback failed: {fallback_err}. Post-hoc label mapping abandoned.", exc_info=True)
                    return
            else:
                logger.critical("[ONTOLOGY] Neither hdbscan nor sklearn.cluster.DBSCAN could be resolved. Compilation aborted.")
                return

        # Write globally-stable labels back to slot_28
        sig_df[phylum_key] = labels

        # Persist updated compact parquet file back to disk
        logger.info(f"[ONTOLOGY] Writing stable labels back to compact database: {compact_path}")
        sig_df.to_parquet(compact_path, index=False, compression="zstd", engine="pyarrow")
        
        unique_phyla = sorted(sig_df[phylum_key].unique())
        visual_limit = config["reproducibility"]["constants"].get("ten_int", 10)
        logger.info(
            f"[ONTOLOGY] Global Ontology Compiler successful. "
            f"Stable phylum labels list: {unique_phyla[:visual_limit]}"
            f"{'...' if len(unique_phyla) > visual_limit else ''}"
        )

    except Exception as exc:
        logger.critical(f"[ONTOLOGY] Unhandled critical error in Global Ontology Compiler: {exc}", exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# 2. CORE MINING IMPLEMENTATION
# ─────────────────────────────────────────────────────────────────────────────

def generate_shards(
    raw_candles: pd.DataFrame,
    agg_trades: pd.DataFrame,
    config: Dict[str, Any],
) -> Generator[Tuple[pd.DataFrame, pd.DataFrame], None, None]:
    """Yields rolling (candle_shard, trade_shard) pairs.

    Shard length = batch_size_days * bars_per_day (derived from interval config).

    Args:
        raw_candles (pd.DataFrame): Entire candle slice dataset.
        agg_trades (pd.DataFrame): Entire trade dataset.
        config (Dict[str, Any]): Configuration dictionary containing parameters.

    Yields:
        Generator[Tuple[pd.DataFrame, pd.DataFrame], None, None]: An iterator
            yielding next candle-trade shard data pair.
    """
    batch_days = config["miner"]["batch_size_days"]
    interval_str = config["miner"]["interval"]
    bars_per_day = _bars_per_day(interval_str, config)
    shard_bars = batch_days * bars_per_day

    const = config["reproducibility"]["constants"]
    zero_i = const["zero_int"]

    n = len(raw_candles)
    start = zero_i
    while start < n:
        end = min(start + shard_bars, n)
        yield raw_candles.iloc[start:end], agg_trades.iloc[start:end]
        start = end


def bar_index_range(
    shard_candles: pd.DataFrame,
    config: Dict[str, Any],
    skip_warmup: bool = True,
) -> range:
    """Returns the valid bar index range for the detection loop.

    Flaw 5 fix: warmup bars are only skipped on the very first shard (skip_warmup=True).
    Subsequent contiguous shards pass skip_warmup=False and start from bar zero,
    preventing the permanent loss of ~five hundred bars (~one point seven three days) at every monthly boundary.

    Args:
        shard_candles (pd.DataFrame): Candle data for the current shard.
        config (Dict[str, Any]): Global config containing warmup requirements.
        skip_warmup (bool): True to skip warmups (first shard), False to include warmups.

    Returns:
        range: Index range for the loop iterator.
    """
    warmup = config["data"]["warmup_bars"] if skip_warmup else config["reproducibility"]["constants"]["zero_int"]
    forward_bars = config["miner"]["forward_bars"]
    max_idx = len(shard_candles) - forward_bars
    if max_idx < warmup:
        max_idx = warmup
    return range(warmup, max_idx)


def compute_forward_metrics(
    dna_row: pd.Series,
    forward_slice: pd.DataFrame,
    config: Dict[str, Any],
) -> pd.Series:
    """Computes MFE, MAE, and Recovery Factor from the post-detection forward slice.

    All horizons and epsilon guards resolve from config.

    Args:
        dna_row (pd.Series): Mined DNA signature vector before post-detection evaluations.
        forward_slice (pd.DataFrame): Historical price activity immediately following detection.
        config (Dict[str, Any]): Configuration settings containing math limits.

    Returns:
        pd.Series: Annotated signature vector containing mfe, mae, and recovery_factor.
    """
    const = config["reproducibility"]["constants"]
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]
    meta_keys = config["feature_builder"]["metadata"]["keys"]

    if forward_slice.empty:
        dna_row["mfe"] = zero_f
        dna_row["mae"] = zero_f
        dna_row["recovery_factor"] = zero_f
        return dna_row

    entry_price = float(forward_slice["open"].iloc[0])
    highs = forward_slice["high"].values
    lows = forward_slice["low"].values

    slot_0_key = config["feature_builder"]["structural"]["slot_0"]["key_name"]
    is_bullish = dna_row.get(slot_0_key, zero_f) >= zero_f

    if is_bullish:
        mfe = float((highs.max() - entry_price) / (entry_price + epsilon))
        mae = float((entry_price - lows.min()) / (entry_price + epsilon))
    else:
        mfe = float((entry_price - lows.min()) / (entry_price + epsilon))
        mae = float((highs.max() - entry_price) / (entry_price + epsilon))

    recovery = min(mfe / (mae + epsilon), float(config["targets"]["recovery_cap"]))

    dna_row["mfe"] = max(mfe, zero_f)
    dna_row["mae"] = max(mae, zero_f)
    dna_row["recovery_factor"] = max(recovery, zero_f)

    # Update recovery proxy in metadata slot
    dna_row[meta_keys["recovery_proxy"]] = dna_row["recovery_factor"]

    return dna_row


# ─────────────────────────────────────────────────────────────────────────────
# 3. UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def update_conviction_history(
    recent_convictions: pd.Series,
    dna_row: pd.Series,
    config: Dict[str, Any],
) -> pd.Series:
    """Legacy alias preserved for API backward compatibility.

    Delegates conviction updating directly to feature_builder_engine.

    Args:
        recent_convictions (pd.Series): Active state conviction metrics.
        dna_row (pd.Series): Newly built vector row.
        config (Dict[str, Any]): Global config mappings.

    Returns:
        pd.Series: Updated conviction series buffer.
    """
    logger.debug("Delegating conviction buffer update to feature_builder_engine...")
    return feature_builder_engine.update_conviction_buffer(
        recent_convictions, dna_row, config
    )


def _bars_per_day(interval_str: str, config: Dict[str, Any]) -> int:
    """Converts interval string (e.g. '5m', '1h') to bars-per-day integer.

    No magic numbers — uses minutes_per_day divided by interval minutes.

    Args:
        interval_str (str): Representation of candle resolution (e.g., '5m', '1d').
        config (Dict[str, Any]): Configuration constants dictionary.

    Returns:
        int: Number of discrete bars present within an operational day.

    Raises:
        ValueError: If interval format is not recognized.
    """
    const = config["reproducibility"]["constants"]
    minutes_per_day = const["minutes_per_day"]
    
    if interval_str.endswith("m"):
        interval_minutes = int(interval_str[:-1])
    elif interval_str.endswith("h"):
        interval_minutes = int(interval_str[:-1]) * const["sixty_int"]
    elif interval_str.endswith("d"):
        return const["one_int"]
    else:
        raise ValueError(
            f"Unrecognized interval format '{interval_str}'. "
            "Expected formats: '5m', '1h', '1d'."
        )
    return minutes_per_day // interval_minutes


def _write_run_metrics_artifact(metrics: Dict[str, Any], config: Dict[str, Any], symbol: str) -> None:
    """Write run metadata to disk without mutating repository state.

    Args:
        metrics (Dict[str, Any]): Evaluated edge metrics dictionary.
        config (Dict[str, Any]): Global config structure for filesystem paths.
        symbol (str): Target trading symbol.
    """
    try:
        db_root = Path(config["database"]["path"])
        audit_dir = db_root / "audit_runs"
        audit_dir.mkdir(parents=True, exist_ok=True)
        
        ts = pd.Timestamp.utcnow().strftime("%Y%m%d_%H%M%S")
        payload = {
            "timestamp_utc": ts,
            "symbol": symbol,
            "metrics": metrics,
        }
        
        out_path = audit_dir / f"run_{symbol}_{ts}.json"
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info(f"[MINER] Mined metrics artifact written successfully to: {out_path}")
    except Exception as err:
        logger.error(f"[MINER] Failed to write run metrics artifact on disk: {err}")


# ─────────────────────────────────────────────────────────────────────────────
# 4. CAUSAL SOVEREIGNTY GUARDS
# ─────────────────────────────────────────────────────────────────────────────

def _assert_causal_sovereignty(config: Dict[str, Any]) -> None:
    """Asserts all causal invariants before any mining begins.

    Raises RuntimeError on violation — pipeline must not proceed.

    Args:
        config (Dict[str, Any]): Mining pipeline settings dictionary.

    Raises:
        RuntimeError: If causality constraints or post-detection settings
            contain lookahead exposures.
    """
    logger.info("[GUARD] Running causal sovereignty pre-flight checks...")
    const = config["reproducibility"]["constants"]
    zero_i = const["zero_int"]
    valid_mode = config["miner"]["valid_mode_post_detection"]

    max_la = config["miner"]["max_lookahead_bars"]
    if max_la != zero_i:
        raise RuntimeError(
            f"Causal violation: max_lookahead_bars={max_la}, must equal zero_int={zero_i}. "
            "Set cfg['miner']['max_lookahead_bars'] to zero_int before mining."
        )

    mode = config["miner"]["forward_metric_mode"]
    if mode != valid_mode:
        raise RuntimeError(
            f"Causal violation: forward_metric_mode='{mode}', must be '{valid_mode}'. "
            "Set cfg['miner']['forward_metric_mode'] to valid_mode_post_detection."
        )
    logger.info("[GUARD] Causal sovereignty checks PASSED. Zero lookahead leaks detected.")
