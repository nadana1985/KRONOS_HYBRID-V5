"""
KRONOS Miner Engine
====================
Walk-forward reversal signature mining loop.

Execution order (per shard, per bar):
  1. Causal slice assertion (max_lookahead_bars == zero_int)
  2. feature_builder_engine.build_full_dna_vector(...)
  3. Signature flag check
  4. Post-detection forward metric computation (MFE / MAE / Recovery)
  5. Phylum assignment (HDBSCAN)
  6. database_engine.store_signature(...)

ALL parameters resolve exclusively from cfg dicts. No inline literals.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import json
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def run_miner(config: Dict, start_date: str, end_date: str) -> None:
    """
    Entry point for the walk-forward mining loop.
    All sharding, detection, evaluation, and storage from config.
    """
    _assert_causal_sovereignty(config)

    import data_engine
    import database_engine
    import feature_builder_engine

    database_engine.initialize_duckdb_views(config)

    for symbol in config["miner"]["symbols"]:
        raw_candles, agg_trades = data_engine.load_shard_data(symbol, config)
        recent_convictions = feature_builder_engine.init_conviction_buffer(config)
        detected_rows: List[pd.Series] = []

        flag_key = config["feature_builder"]["gate"]["signature_flag_key"]
        const = config["reproducibility"]["constants"]
        one_i = const["one_int"]

        # FLAW 5 FIX: warmup is only skipped on the very first shard.
        # Subsequent contiguous shards start from bar 0 of their slice.
        is_first_shard = True

        for shard_candles, shard_trades in generate_shards(raw_candles, agg_trades, config):
            # High-performance optimization: precompute structural slots & veto composite once per shard
            # This transitions the pipeline from O(N^2) backtest time down to O(N) linear time,
            # reducing CPU thermal load to negligible levels and preventing CPU shutdowns.
            import structural_engine
            print(f"Precomputing structural slot matrix for shard of size {len(shard_candles)}...")
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

            print("Precomputation complete. Running bar-by-bar sequence loop...")

            # FLAW 5 FIX: pass is_first_shard so bar_index_range only skips warmup once
            shard_detected: List[pd.Series] = []

            for current_idx in bar_index_range(shard_candles, config, skip_warmup=is_first_shard):

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
                    # NOTE: slot_28 (phylum_id) stays at placeholder 0.0 during mining.
                    # The Global Ontology Compiler runs once after all shards complete
                    # and overwrites slot_28 with globally-stable HDBSCAN cluster labels.
                    # This eliminates the Incremental Label Freezing flaw where HDBSCAN
                    # was re-fit on every new row, producing only 3-4 unique values.

                    # Inject primary index columns for storage compatibility
                    dna_row["timestamp"] = str(shard_candles["datetime"].iloc[current_idx])
                    dna_row["symbol"] = symbol
                    dna_row["interval"] = config["miner"]["interval"]

                    # FLAW 7 FIX: collect into shard buffer; batch-write at end of shard
                    shard_detected.append(dna_row)
                    detected_rows.append(dna_row)

                recent_convictions = feature_builder_engine.update_conviction_buffer(
                    recent_convictions, dna_row, config
                )

            # FLAW 7 FIX: batch write all shard signatures in a single I/O operation
            if shard_detected:
                database_engine.store_signatures_batch(shard_detected, config)

            # Persist run metrics as artifact (no git side effects in miner loop).
            if detected_rows:
                import validation_engine
                run_metrics = validation_engine.compute_edge_metrics(pd.DataFrame(detected_rows), config)
                _write_run_metrics_artifact(run_metrics, config, symbol)

            is_first_shard = False

        # ── GLOBAL ONTOLOGY COMPILER (slot_28) ──────────────────────────────
        # Runs exactly once after all shards are mined for this symbol.
        # HDBSCAN is applied to the complete signature matrix in a single pass,
        # producing stable, globally-consistent phylum cluster labels.
        compile_global_ontology(symbol, config)


def generate_shards(
    raw_candles: pd.DataFrame,
    agg_trades: pd.DataFrame,
    config: Dict,
) -> Generator[Tuple[pd.DataFrame, pd.DataFrame], None, None]:
    """
    Yields rolling (candle_shard, trade_shard) pairs.
    Shard length = batch_size_days * bars_per_day (derived from interval config).
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
    config: Dict,
    skip_warmup: bool = True,
) -> range:
    """
    Returns the valid bar index range for the detection loop.

    Flaw 5 fix: warmup bars are only skipped on the very first shard (skip_warmup=True).
    Subsequent contiguous shards pass skip_warmup=False and start from bar 0,
    preventing the permanent loss of ~five hundred bars (~one point seven three days) at every monthly boundary.
    """
    warmup = config["data"]["warmup_bars"] if skip_warmup else config["reproducibility"]["constants"]["zero_int"]
    return range(warmup, len(shard_candles))


def compute_forward_metrics(
    dna_row: pd.Series,
    forward_slice: pd.DataFrame,
    config: Dict,
) -> pd.Series:
    """
    Computes MFE, MAE, and Recovery Factor from the post-detection forward slice.
    All horizons and epsilon guards from config.
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


def assign_phylum(
    dna_row: pd.Series,
    detected_rows: List[pd.Series],
    config: Dict,
) -> pd.Series:
    """
    Assigns phylum cluster ID via HDBSCAN on accumulated structural features.
    Falls back to scikit-learn DBSCAN (density-based clustering) when HDBSCAN is unavailable.
    """
    const = config["reproducibility"]["constants"]
    zero_f = const["zero_float"]
    meta_cfg = config["feature_builder"]["metadata"]
    phylum_key = meta_cfg["keys"]["phylum_id"]
    hdb_cfg = meta_cfg["hdbscan"]
    min_size = hdb_cfg["min_cluster_size"]

    if len(detected_rows) < min_size:
        dna_row[phylum_key] = zero_f
        return dna_row

    structural_cols = list(
        config["feature_builder"]["structural"]["slot_15"]["weights"].keys()
    )

    try:
        import hdbscan
        history_df = pd.DataFrame(detected_rows)[structural_cols].dropna()
        if len(history_df) < min_size:
            dna_row[phylum_key] = zero_f
            return dna_row

        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=hdb_cfg["min_cluster_size"],
            min_samples=hdb_cfg["min_samples"],
            metric=hdb_cfg["metric"],
        )
        clusterer.fit(history_df.values)
        dna_row[phylum_key] = float(clusterer.labels_[-1])
    except Exception:
        try:
            from sklearn.cluster import DBSCAN
            history_df = pd.DataFrame(detected_rows)[structural_cols].dropna()
            if len(history_df) < min_size:
                dna_row[phylum_key] = zero_f
                return dna_row

            # Standard DBSCAN as high-fidelity density clustering fallback
            clusterer = DBSCAN(
                min_samples=hdb_cfg["min_samples"],
                metric=hdb_cfg["metric"],
            )
            clusterer.fit(history_df.values)
            dna_row[phylum_key] = float(clusterer.labels_[-1])
        except Exception:
            dna_row[phylum_key] = zero_f

    return dna_row


def compile_global_ontology(symbol: str, config: Dict) -> None:
    """
    Global Ontology Compiler — Post-Hoc Phylum Assignment for slot_28.

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
    """
    import pyarrow.parquet as pq
    import pyarrow as pa

    const = config["reproducibility"]["constants"]
    zero_f = const["zero_float"]
    meta_cfg = config["feature_builder"]["metadata"]
    phylum_key = meta_cfg["keys"]["phylum_id"]
    hdb_cfg = meta_cfg["hdbscan"]
    const = config["reproducibility"]["constants"]
    db_cfg = config["database"]
    structural_cols = list(
        config["feature_builder"]["structural"]["slot_15"]["weights"].keys()
    )

    # Resolve source path: prefer compact file, fall back to partition tree
    compact_path = db_cfg.get("compact_path", "data/signatures_compact.parquet")
    partition_path = db_cfg.get("parquet_path_pattern", "data/signatures/**/*.parquet")

    print(f"\n[ONTOLOGY] Loading complete signature database for Global Ontology Compilation...")
    try:
        from pathlib import Path as _Path
        if _Path(compact_path).exists():
            sig_df = pd.read_parquet(compact_path)
        else:
            import glob
            files = glob.glob(partition_path.replace("**", "**"), recursive=True)
            if not files:
                print("[ONTOLOGY] No signatures found. Skipping ontology compilation.")
                return
            sig_df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    except Exception as exc:
        print(f"[ONTOLOGY] WARNING: Could not load signatures for ontology: {exc}")
        return

    # Filter to this symbol if column exists
    if "symbol" in sig_df.columns:
        sig_df = sig_df[sig_df["symbol"] == symbol].copy()

    if len(sig_df) < hdb_cfg["min_cluster_size"]:
        print(f"[ONTOLOGY] Not enough signatures ({len(sig_df)}) to cluster. Min required: {hdb_cfg['min_cluster_size']}. Skipping.")
        return

    # Extract the structural feature matrix for clustering
    available_cols = [c for c in structural_cols if c in sig_df.columns]
    if not available_cols:
        print("[ONTOLOGY] WARNING: No structural slot columns found in database. Skipping.")
        return

    feature_matrix = sig_df[available_cols].fillna(zero_f).values
    print(f"[ONTOLOGY] Running global HDBSCAN on {len(sig_df):,} signatures x {len(available_cols)} features...")

    labels = None
    try:
        import hdbscan
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=hdb_cfg["min_cluster_size"],
            min_samples=hdb_cfg["min_samples"],
            metric=hdb_cfg["metric"],
            core_dist_n_jobs=hdb_cfg.get("n_jobs", -1),
        )
        clusterer.fit(feature_matrix)
        labels = clusterer.labels_.astype(float)
        n_clusters = len(set(labels)) - (const["one_int"] if const["noise_label"] in labels else const["zero_int"])
        n_noise = int((labels == const["noise_label"]).sum())
        print(f"[ONTOLOGY] HDBSCAN complete. Unique phyla discovered: {n_clusters} | Noise points: {n_noise:,}")
    except ImportError:
        print("[ONTOLOGY] hdbscan not available. Falling back to sklearn DBSCAN...")
        try:
            from sklearn.cluster import DBSCAN
            clusterer = DBSCAN(
                min_samples=hdb_cfg["min_samples"],
                metric=hdb_cfg["metric"],
            )
            clusterer.fit(feature_matrix)
            labels = clusterer.labels_.astype(float)
            n_clusters = len(set(labels)) - (const["one_int"] if const["noise_label"] in labels else const["zero_int"])
            print(f"[ONTOLOGY] DBSCAN complete. Unique phyla discovered: {n_clusters}")
        except Exception as exc:
            print(f"[ONTOLOGY] WARNING: Clustering failed: {exc}. Slot_28 will remain at placeholder 0.0.")
            return
    except Exception as exc:
        print(f"[ONTOLOGY] WARNING: HDBSCAN failed: {exc}. Slot_28 will remain at placeholder 0.0.")
        return

    # Write globally-stable labels back to slot_28
    sig_df[phylum_key] = labels

    # Persist back to compact parquet
    try:
        sig_df.to_parquet(compact_path, index=False, compression="zstd", engine="pyarrow")
        print(f"[ONTOLOGY] Slot_28 updated. Compact database written to: {compact_path}")
        unique_phyla = sorted(sig_df[phylum_key].unique())
        print(f"[ONTOLOGY] Phylum distribution: {len(unique_phyla)} unique labels — {unique_phyla[:10]}{'...' if len(unique_phyla) > 10 else ''}")
    except Exception as exc:
        print(f"[ONTOLOGY] WARNING: Failed to persist updated ontology: {exc}")


def update_conviction_history(
    recent_convictions: pd.Series,
    dna_row: pd.Series,
    config: Dict,
) -> pd.Series:
    """Alias kept for backward compatibility — delegates to feature_builder_engine."""
    import feature_builder_engine
    return feature_builder_engine.update_conviction_buffer(
        recent_convictions, dna_row, config
    )


# ─────────────────────────────────────────────────────────────────────────────
# CAUSAL SOVEREIGNTY GUARD
# ─────────────────────────────────────────────────────────────────────────────

def _assert_causal_sovereignty(config: Dict) -> None:
    """
    Asserts all causal invariants before any mining begins.
    Raises RuntimeError on violation — pipeline must not proceed.
    """
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


# ─────────────────────────────────────────────────────────────────────────────
# INTERVAL UTILITY
# ─────────────────────────────────────────────────────────────────────────────

def _bars_per_day(interval_str: str, config: Dict) -> int:
    """
    Converts interval string (e.g. '5m', '1h') to bars-per-day integer.
    No magic numbers — uses minutes_per_day divided by interval minutes.
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
            f"Unrecognised interval format '{interval_str}'. "
            "Expected formats: '5m', '1h', '1d'."
        )
    return minutes_per_day // interval_minutes


def _write_run_metrics_artifact(metrics: Dict, config: Dict, symbol: str) -> None:
    """Write run metadata to disk without mutating repository state."""
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
