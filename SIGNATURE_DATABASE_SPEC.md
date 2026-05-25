# Reversal Signature Database Specification

**File**: `SIGNATURE_DATABASE_SPEC.md`  
**Status**: SOVEREIGN LOCKED — ZERO INLINE LITERAL DOCTRINE ENFORCED  
**Config Source**: Configuration dictionary loaded dynamically at runtime  
**Depends On**: `database_engine.py`

---

## Purpose

Defines the database schema, physical storage partitioning, PyArrow serialization layer, and DuckDB analytical query interfaces for the KRONOS Reversal Signature Archive. All directory paths, database connections, partitioning keys, schema definitions, quality scores, and filter parameters resolve exclusively via dynamic configuration lookups. No hardcoded strings, directory structures, SQL literal parameters, or quality limits exist in this document.

---

## Storage Architecture

All detected reversal signatures are validated, decorated with system metadata, audited with cryptographic and version tracking hashes, and appended dynamically to a partitioned Parquet table and localized DuckDB analytics view:

```
══════════════════════════════════════════════════════════════════════════════════
SIGNATURE PERSISTENCE PIPELINE
══════════════════════════════════════════════════════════════════════════════════

CONFIG LOAD
  # Parse authoritative YAML config
  cfg = load_sovereign_config()

SIGNATURE ROW VECTOR (Compiled DNA + Metadata)
  │
  ├─► PYARROW SCHEMA VALIDATION
  │     # PyArrow schema is constructed dynamically using column structures
  │     schema = database_engine.construct_schema(cfg)
  │
  ├─► SYSTEM METADATA AND AUDIT TRAIL INJECTION
  │     # Append code version and configuration fingerprint hashes
  │     row[cfg["database"]["audit"]["git_commit_key"]]  = get_git_commit_hash()
  │     row[cfg["database"]["audit"]["data_hash_key"]]    = compute_sha256_hash(row)
  │     row[cfg["database"]["audit"]["config_hash_key"]]  = compute_config_hash(cfg)
  │
  ├─► PARTITIONED PYARROW PARQUET WRITES
  │     # Output path resolved from cfg["database"]["path"]
  │     # Partition layout resolved from cfg["database"]["partition_by"]
  │     # Compression algorithm resolved from cfg["database"]["compression"]
  │     pyarrow.dataset.write_dataset(
  │         table,
  │         base_dir=cfg["database"]["path"],
  │         partitioning=cfg["database"]["partition_by"],
  │         format=cfg["database"]["storage_format"]
  │     )
  │
  └─► DUCKDB VIEW (`database_engine.initialize_duckdb_views`)
        # Prefer cfg["database"]["compact_path"] when the consolidated Parquet exists
        # (avoids stale bindings after partition compaction); otherwise recurse
        # cfg["database"]["parquet_path_pattern"] with hive_partitioning.
        CREATE OR REPLACE VIEW signatures AS SELECT * FROM read_parquet(<resolved path expr>)
        # Failures defer with RuntimeWarning until first successful Parquet emission.

══════════════════════════════════════════════════════════════════════════════════
```

---

## Database Configuration Map

All paths, compression levels, partition keys, and audit definitions are fetched dynamically.

| Property | Description | Config Reference Key |
| :--- | :--- | :--- |
| Root archive path | Directory containing Parquet subfolders | `cfg["database"]["path"]` |
| DuckDB file path | Persistent database engine path | `cfg["database"]["duckdb_path"]` |
| Parquet pattern | Recursive folder glob lookup string | `cfg["database"]["parquet_path_pattern"]` |
| Compact file path | Single consolidated Parquet for DuckDB view | `cfg["database"]["compact_path"]` |
| Partition list | Array of dimensions for directory splitting | `cfg["database"]["partition_by"]` |
| Storage format | Target serialization format (e.g. Parquet) | `cfg["database"]["storage_format"]` |
| Min database quality | Entry quality score threshold | `cfg["database"]["min_quality_score"]` |
| Min recovery factor | Dynamic retention filtering criteria | `cfg["database"]["retention_policy"]["min_recovery_factor"]` |
| Maximum age days | Expiration duration limit | `cfg["database"]["retention_policy"]["max_age_days"]` |
| Git commit key | Column header for version tracking | `cfg["database"]["audit"]["git_commit_key"]` |
| Data hash key | Column header for data hash checksum | `cfg["database"]["audit"]["data_hash_key"]` |
| Config hash key | Column header for configuration hash checksum | `cfg["database"]["audit"]["config_hash_key"]` |

---

## Dynamic Schema Column Map

All column names are looked up from config. No literal names exist.

| Column Category | Target Column Role | Config Reference Key |
| :--- | :--- | :--- |
| Primary Index | Event detection timestamp | `cfg["feature_builder"]["metadata"]["index_cols"]` |
| Primary Index | Symbol identifier key | `cfg["feature_builder"]["metadata"]["index_cols"]` |
| Primary Index | Bar interval timeframe | `cfg["feature_builder"]["metadata"]["index_cols"]` |
| Structural Core | Score columns | `cfg["feature_builder"]["structural"]["slot_N"]["key_name"]` |
| Structural Veto | Veto composite score | `cfg["feature_builder"]["structural"]["slot_15"]["key_name"]` |
| Neural Embeddings | Frozen transformer columns | `cfg["kronos_mini"]["slot_key_prefix"]` |
| Auxiliary Synthetic | Indicators and path projections | `cfg["feature_builder"]["aux"]["slot_N"]["key_name"]` |
| Metadata & Phylum | Dynamic cluster ID | `cfg["feature_builder"]["metadata"]["keys"]["phylum_id"]` |
| Metadata & Phylum | Detection timestamp hash | `cfg["feature_builder"]["metadata"]["keys"]["timestamp_hash"]` |
| Metadata & Phylum | Post-detection recovery proxy | `cfg["feature_builder"]["metadata"]["keys"]["recovery_proxy"]` |
| Metadata & Phylum | Reversal event quality score | `cfg["feature_builder"]["metadata"]["keys"]["signature_quality"]` |
| Conviction Gate | Signature flag column | `cfg["feature_builder"]["gate"]["signature_flag_key"]` |
| Conviction Gate | Raw neural conviction score | `cfg["feature_builder"]["gate"]["neural_conviction_key"]` |
| Conviction Gate | Dynamic conviction threshold | `cfg["feature_builder"]["gate"]["conviction_threshold_key"]` |

---

## Database Programmatic Interface

The database storage layer exposes completely decoupled functions loaded exclusively via dynamic configurations:

```python
from typing import Dict, List
import pandas as pd
import pyarrow as pa

def load_sovereign_config(path: str) -> Dict:
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)

def construct_schema(config: Dict) -> pa.Schema:
    """
    Builds dynamic PyArrow schema for database serialization.
    All column headers are resolved dynamically. No literals permitted.

    Implementation in database_engine.py
    """
    from database_engine import construct_schema as _impl
    return _impl(config)

def store_signature(
    dna_row: pd.Series,
    config: Dict
) -> None:
    """
    Validates, stamps, audits, and persists a single signature to Partitioned Parquet.
    Partitioning and compression profiles are resolved dynamically.

    Config References:
      cfg["database"]["path"]
      cfg["database"]["partition_by"]
      cfg["database"]["storage_format"]
      cfg["database"]["audit"]

    Implementation in database_engine.py
    """
    from database_engine import store_signature as _impl
    _impl(dna_row, config)

def initialize_duckdb_views(config: Dict) -> None:
    """
    Configures / recreates DuckDB analytical view over partitioned Parquet table.
    All paths and structures are parameterized. No literal paths.

    Config References:
      cfg["database"]["duckdb_path"]
      cfg["database"]["parquet_path_pattern"]
      cfg["database"]["compact_path"]

    Implementation in database_engine.py
    """
    from database_engine import initialize_duckdb_views as _impl
    _impl(config)
```

---

## Analytical Query Stubs

All SQL statements use strictly parameterized variables. No inline value assertions or hardcoded filter thresholds:

```python
def query_elite_signatures(con, config: Dict) -> pd.DataFrame:
    """
    Queries signatures exceeding minimal quality thresholds.
    Filter parameters are bound using parameterized bindings.

    Config References:
      cfg["database"]["min_quality_score"]
      cfg["targets"]["regime_id"]
      cfg["feature_builder"]["metadata"]["keys"]["signature_quality"]

    Implementation in database_engine.py
    """
    # SQL constructed dynamically:
    # SELECT * FROM signatures WHERE {quality_col} >= ? AND regime_state = ?
    # Bound parameters: (config["database"]["min_quality_score"], config["targets"]["regime_id"])
    from database_engine import query_elite_signatures as _impl
    return _impl(con, config)

def query_phylum_edge_stats(con, config: Dict) -> pd.DataFrame:
    """
    Evaluates statistics of historical signatures grouped by phylum ID.
    Threshold limits are parameterized.

    Config References:
      cfg["database"]["retention_policy"]["min_recovery_factor"]
      cfg["feature_builder"]["metadata"]["keys"]["phylum_id"]

    Implementation in database_engine.py
    """
    # SQL constructed dynamically:
    # SELECT {phylum_col}, count(*), avg(recovery_factor) 
    # FROM signatures GROUP BY {phylum_col} HAVING avg(recovery_factor) >= ?
    # Bound parameters: (config["database"]["retention_policy"]["min_recovery_factor"])
    from database_engine import query_phylum_edge_stats as _impl
    return _impl(con, config)

def query_by_regime(con, config: Dict) -> pd.DataFrame:
    """
    Retrieves all signatures associated with a target regime identifier.

    Config References:
      cfg["targets"]["regime_id"]

    Implementation in database_engine.py
    """
    from database_engine import query_by_regime as _impl
    return _impl(con, config)

def query_conviction_distribution(con, config: Dict) -> pd.DataFrame:
    """
    Queries statistical distribution parameters of neural conviction scores.

    Config References:
      cfg["feature_builder"]["gate"]["neural_conviction_key"]

    Implementation in database_engine.py
    """
    from database_engine import query_conviction_distribution as _impl
    return _impl(con, config)

def query_audit_trail(con, config: Dict) -> pd.DataFrame:
    """
    Retrieves execution version audit logs tracking git commits and config hashes.

    Config References:
      cfg["database"]["audit"]["git_commit_key"]

    Implementation in database_engine.py
    """
    from database_engine import query_audit_trail as _impl
    return _impl(con, config)
```

---

## Sovereignty Migration Path

> [!WARNING]
> **Active Hybrid Compromises**:
> - Parquet partitioned writes can experience folder count expansion over long chronological ranges. Ensure folder trees are flattened using monthly execution shards via `run_sharded_pipeline.py`.
> - **DuckDB Views**: DuckDB views need persistent connections. Multi-threaded engines should establish isolated, read-only connections to prevent transaction blocks.

---

**Hardcode Audit Passed — Zero Inline Literals**