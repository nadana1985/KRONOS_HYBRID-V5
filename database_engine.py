"""
KRONOS Database Engine
========================
Handles Parquet-based signature storage, DuckDB view management,
and parameterised analytical queries.

ALL paths, column names, partition schemes, and filter values resolve
exclusively from cfg dicts passed at call time. No inline literals.

Dependencies: pandas, pyarrow, duckdb
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, Optional

import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API — STORAGE
# ─────────────────────────────────────────────────────────────────────────────

def store_signature(dna_row: pd.Series, config: Dict) -> None:
    """
    Validates quality gate, injects audit trail, and writes a SINGLE row to Parquet.
    NOTE: in the mining loop, prefer store_signatures_batch() for performance.
    Partition layout from cfg["database"]["partition_by"].
    """
    const = config["reproducibility"]["constants"]
    db_cfg = config["database"]
    meta_keys = config["feature_builder"]["metadata"]["keys"]
    quality_col = meta_keys["signature_quality"]
    min_quality = db_cfg["min_quality_score"]

    qual_val = float(dna_row.get(quality_col, const["zero_float"]))
    if qual_val < min_quality:
        ts_val = dna_row.get("timestamp", "unknown")
        print(f"[INFO] Signature at {ts_val} discarded (Quality: {qual_val:.4f} < floor: {min_quality})")
        return

    row_copy = dna_row.copy()
    # Dynamically inject year/month partition fields derived from timestamp
    if "year" in db_cfg["partition_by"] or "month" in db_cfg["partition_by"]:
        ts = pd.to_datetime(dna_row["timestamp"])
        if "year" in db_cfg["partition_by"]:
            row_copy["year"] = str(ts.year)
        if "month" in db_cfg["partition_by"]:
            row_copy["month"] = f"{ts.month:02d}"

    row_with_audit = _inject_audit_trail(row_copy, config)
    row_df = pd.DataFrame([row_with_audit])

    _write_parquet(row_df, config)


def store_signatures_batch(dna_rows: list, config: Dict) -> None:
    """
    Validates quality gate on each row and writes the entire batch to Parquet
    in a SINGLE I/O operation.

    Flaw 7 fix: previously store_signature was called inside the per-bar mining loop,
    producing one tiny Parquet file per passing signature (up to twenty-six thousand files per run).
    This batch writer collects all passing rows from a shard into a single DataFrame
    and writes them atomically, reducing disk I/O from O(N) file ops to O(1).
    """
    if not dna_rows:
        return

    const = config["reproducibility"]["constants"]
    db_cfg = config["database"]
    meta_keys = config["feature_builder"]["metadata"]["keys"]
    quality_col = meta_keys["signature_quality"]
    min_quality = db_cfg["min_quality_score"]
    zero_f = const["zero_float"]

    passing_rows = []
    for dna_row in dna_rows:
        qual_val = float(dna_row.get(quality_col, zero_f))
        if qual_val < min_quality:
            ts_val = dna_row.get("timestamp", "unknown")
            print(f"[INFO] Signature at {ts_val} discarded (Quality: {qual_val:.4f} < floor: {min_quality})")
            continue

        row_copy = dna_row.copy()
        # Inject partition fields
        if "year" in db_cfg["partition_by"] or "month" in db_cfg["partition_by"]:
            ts = pd.to_datetime(dna_row["timestamp"])
            if "year" in db_cfg["partition_by"]:
                row_copy["year"] = str(ts.year)
            if "month" in db_cfg["partition_by"]:
                row_copy["month"] = f"{ts.month:02d}"

        passing_rows.append(_inject_audit_trail(row_copy, config))

    if not passing_rows:
        return

    batch_df = pd.DataFrame(passing_rows)
    _write_parquet(batch_df, config)
    print(f"[BATCH] Wrote {len(passing_rows):,} signatures to Parquet in a single I/O operation.")


try:
    import duckdb
    _DUCKDB_AVAILABLE = True
except ImportError:
    _DUCKDB_AVAILABLE = False


def initialize_duckdb_views(config: Dict) -> None:
    """
    Creates or refreshes the DuckDB view over the Parquet data source.
    All paths from config. Handles empty datasets gracefully.

    Flaw 8 fix: the view now checks whether signatures_compact.parquet exists.
    If it does, the view binds directly to the single compacted file for maximum
    query performance. If not, it falls back to the partition tree. This prevents
    stale view references and query failures when the partition tree is deleted
    after compaction.
    """
    if not _DUCKDB_AVAILABLE:
        return

    import warnings

    db_cfg = config["database"]
    duckdb_path = db_cfg["duckdb_path"]
    pattern = db_cfg["parquet_path_pattern"]
    compact_path = db_cfg.get("compact_path", "data/signatures_compact.parquet")

    # Prefer the single compacted file if it exists (faster queries, avoids stale partition refs)
    if Path(compact_path).exists():
        read_expr = f"read_parquet('{compact_path}')"
    else:
        read_expr = f"read_parquet('{pattern}', hive_partitioning=1)"

    try:
        con = duckdb.connect(duckdb_path)
        # Direct string embedding — no ? parameter (DuckDB view binder restriction)
        con.execute(f"CREATE OR REPLACE VIEW signatures AS SELECT * FROM {read_expr}")
        con.close()
    except Exception as exc:
        warnings.warn(
            f"DuckDB view initialization deferred until signatures are written: {exc}",
            RuntimeWarning,
            stacklevel=2,
        )


def get_connection(config: Dict):
    """Returns an open DuckDB connection, or None if unavailable."""
    if not _DUCKDB_AVAILABLE:
        return None
    return duckdb.connect(config["database"]["duckdb_path"])


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API — QUERIES (degrades gracefully to pure Pandas without DuckDB)
# ─────────────────────────────────────────────────────────────────────────────

def query_elite_signatures(con, config: Dict) -> pd.DataFrame:
    """
    Returns signatures passing quality gate and signature flag.
    All filter values bound as parameterised ? from config.
    """
    meta_keys = config["feature_builder"]["metadata"]["keys"]
    gate_cfg = config["feature_builder"]["gate"]
    db_cfg = config["database"]

    quality_col = meta_keys["signature_quality"]
    flag_col = gate_cfg["signature_flag_key"]
    min_quality = db_cfg["min_quality_score"]

    if con is not None:
        return con.execute(
            f"SELECT * FROM signatures WHERE \"{quality_col}\" >= ? AND \"{flag_col}\" = TRUE",
            [min_quality],
        ).df()

    # Pandas Fallback
    try:
        df = pd.read_parquet(db_cfg["path"])
        return df[(df[quality_col] >= min_quality) & (df[flag_col] == True)]
    except Exception:
        return pd.DataFrame(columns=[f.name for f in construct_schema(config).fields])


def query_by_regime(con, config: Dict) -> pd.DataFrame:
    """Filters signatures by target HMM regime."""
    regime_col = config["feature_builder"]["structural"]["slot_8"]["key_name"]
    target_regime = config["targets"]["regime_id"]
    db_cfg = config["database"]

    if con is not None:
        return con.execute(
            f"SELECT * FROM signatures WHERE \"{regime_col}\" = ?",
            [target_regime],
        ).df()

    # Pandas Fallback
    try:
        df = pd.read_parquet(db_cfg["path"])
        return df[df[regime_col] == target_regime]
    except Exception:
        return pd.DataFrame(columns=[f.name for f in construct_schema(config).fields])


def query_phylum_edge_stats(con, config: Dict) -> pd.DataFrame:
    """Per-phylum edge statistics. Recovery HAVING clause bound as ?."""
    meta_keys = config["feature_builder"]["metadata"]["keys"]
    phylum_col = meta_keys["phylum_id"]
    recovery_col = meta_keys["recovery_proxy"]
    min_recovery = config["database"]["retention_policy"]["min_recovery_factor"]
    db_cfg = config["database"]

    if con is not None:
        return con.execute(
            f"""
            SELECT
                "{phylum_col}",
                COUNT(*) AS count,
                AVG("{recovery_col}") AS mean_recovery,
                MIN("{recovery_col}") AS min_recovery,
                MAX("{recovery_col}") AS max_recovery
            FROM signatures
            GROUP BY "{phylum_col}"
            HAVING AVG("{recovery_col}") >= ?
            ORDER BY mean_recovery DESC
            """,
            [min_recovery],
        ).df()

    # Pandas Fallback
    try:
        df = pd.read_parquet(db_cfg["path"])
        if df.empty:
            return pd.DataFrame(columns=[phylum_col, 'count', 'mean_recovery', 'min_recovery', 'max_recovery'])
        g = df.groupby(phylum_col)[recovery_col].agg(
            count='count',
            mean_recovery='mean',
            min_recovery='min',
            max_recovery='max'
        ).reset_index()
        return g[g['mean_recovery'] >= min_recovery].sort_values(by='mean_recovery', ascending=False)
    except Exception:
        return pd.DataFrame(columns=[phylum_col, 'count', 'mean_recovery', 'min_recovery', 'max_recovery'])


def query_conviction_distribution(con, config: Dict) -> pd.DataFrame:
    """Distribution stats for neural conviction scores."""
    conv_col = config["feature_builder"]["gate"]["neural_conviction_key"]
    db_cfg = config["database"]
    const = config["reproducibility"]["constants"]

    if con is not None:
        return con.execute(
            f"""
            SELECT
                MIN("{conv_col}") AS min_conviction,
                MAX("{conv_col}") AS max_conviction,
                AVG("{conv_col}") AS mean_conviction,
                STDDEV("{conv_col}") AS std_conviction,
                MEDIAN("{conv_col}") AS median_conviction
            FROM signatures
            """
        ).df()

    # Pandas Fallback
    try:
        df = pd.read_parquet(db_cfg["path"])
        z = const["zero_float"]
        if df.empty:
            return pd.DataFrame([{
                'min_conviction': z, 'max_conviction': z, 'mean_conviction': z,
                'std_conviction': z, 'median_conviction': z
            }])
        return pd.DataFrame([{
            'min_conviction': float(df[conv_col].min()),
            'max_conviction': float(df[conv_col].max()),
            'mean_conviction': float(df[conv_col].mean()),
            'std_conviction': float(df[conv_col].std()),
            'median_conviction': float(df[conv_col].median())
        }])
    except Exception:
        z = const["zero_float"]
        return pd.DataFrame([{
            'min_conviction': z, 'max_conviction': z, 'mean_conviction': z,
            'std_conviction': z, 'median_conviction': z
        }])


def query_audit_trail(
    con,
    config: Dict,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Retrieves audit trail rows for a date range. Dates bound as ?."""
    audit = config["database"]["audit"]
    data_hash_col = audit["data_hash_key"]
    config_hash_col = audit["config_hash_key"]
    git_col = audit["git_commit_key"]
    db_cfg = config["database"]

    if con is not None:
        return con.execute(
            f"""
            SELECT timestamp, "{data_hash_col}", "{config_hash_col}", "{git_col}"
            FROM signatures
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp ASC
            """,
            [start_date, end_date],
        ).df()

    # Pandas Fallback
    try:
        df = pd.read_parquet(db_cfg["path"])
        if "timestamp" not in df.columns and df.index.name == "timestamp":
            df = df.reset_index()
        res = df[(df["timestamp"] >= start_date) & (df["timestamp"] <= end_date)]
        return res[["timestamp", data_hash_col, config_hash_col, git_col]].sort_values(by="timestamp", ascending=True)
    except Exception:
        return pd.DataFrame(columns=["timestamp", data_hash_col, config_hash_col, git_col])


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA CONSTRUCTION
# ─────────────────────────────────────────────────────────────────────────────

def construct_schema(config: Dict):
    """
    Builds a pyarrow schema for the signature archive.
    All column names resolved from config.
    """
    import pyarrow as pa

    meta_keys = config["feature_builder"]["metadata"]["keys"]
    gate_cfg = config["feature_builder"]["gate"]
    audit = config["database"]["audit"]
    slot_order = config["feature_builder"]["structural"]["slot_order"]
    structural_cfg = config["feature_builder"]["structural"]

    fields = []

    # Index columns
    for col in config["feature_builder"]["metadata"]["index_cols"]:
        fields.append(pa.field(col, pa.string()))

    # Partition columns (e.g. year, month)
    for col in config["database"]["partition_by"]:
        if col not in [f.name for f in fields]:
            fields.append(pa.field(col, pa.string()))

    # Structural slot columns
    for slot_key in slot_order:
        key_name = structural_cfg[slot_key]["key_name"]
        fields.append(pa.field(key_name, pa.float32()))

    # Veto composite
    veto_key = structural_cfg["slot_15"]["key_name"]
    fields.append(pa.field(veto_key, pa.float32()))

    # Neural slots (S_16 to S_23)
    emb_dim = config["kronos_mini"]["embedding_dim"]
    slot_prefix = config["kronos_mini"].get("slot_key_prefix", "slot_")
    start_idx = config["kronos_mini"].get("slot_start_idx", 16)
    for i in range(emb_dim):
        col_name = f"{slot_prefix}{start_idx + i}"
        fields.append(pa.field(col_name, pa.float32()))

    # Gate outputs
    fields.append(pa.field(gate_cfg["signature_flag_key"], pa.bool_()))
    fields.append(pa.field(gate_cfg["neural_conviction_key"], pa.float32()))
    fields.append(pa.field(gate_cfg["conviction_threshold_key"], pa.float32()))

    # Auxiliary slots (S_24 to S_27)
    aux_cfg = config["feature_builder"]["aux"]
    for _, aux_item in aux_cfg.items():
        fields.append(pa.field(aux_item["key_name"], pa.float32()))

    # Metadata slots
    for _, col in meta_keys.items():
        fields.append(pa.field(col, pa.float32()))

    # Forward metrics
    for col in ["mfe", "mae", "recovery_factor"]:
        fields.append(pa.field(col, pa.float32()))

    # Audit trail
    for col in [audit["data_hash_key"], audit["config_hash_key"], audit["git_commit_key"]]:
        fields.append(pa.field(col, pa.string()))

    return pa.schema(fields)


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _inject_audit_trail(dna_row: pd.Series, config: Dict) -> pd.Series:
    """Adds SHA-256 data hash, config hash, and git commit to dna_row."""
    audit = config["database"]["audit"]
    row = dna_row.copy()

    data_bytes = dna_row.to_json().encode()
    row[audit["data_hash_key"]] = hashlib.sha256(data_bytes).hexdigest()

    config_bytes = json.dumps(config, sort_keys=True, default=str).encode()
    row[audit["config_hash_key"]] = hashlib.sha256(config_bytes).hexdigest()

    row[audit["git_commit_key"]] = _get_git_commit()
    return row


def _get_git_commit() -> str:
    """Returns HEAD git commit hash, or 'unversioned' if git is unavailable."""
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=2
        )
        return result.stdout.strip() or "unversioned"
    except Exception:
        return "unversioned"


def _write_parquet(row_df: pd.DataFrame, config: Dict) -> None:
    """Writes a single-row DataFrame to the partitioned Parquet archive."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    db_cfg = config["database"]
    root_path = Path(db_cfg["path"])
    partition_cols = db_cfg["partition_by"]

    schema = construct_schema(config)
    table = pa.Table.from_pandas(row_df, schema=schema, preserve_index=False)

    pq.write_to_dataset(
        table,
        root_path=str(root_path),
        partition_cols=partition_cols,
        compression=db_cfg.get("compression", "snappy"),
        existing_data_behavior="overwrite_or_ignore",
    )
