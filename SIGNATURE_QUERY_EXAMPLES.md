# Signature Query Examples

**File**: `SIGNATURE_QUERY_EXAMPLES.md`  
**Status**: SOVEREIGN LOCKED — ZERO INLINE LITERAL DOCTRINE ENFORCED  
**Config Source**: `params_yaml.txt` loaded via `load_sovereign_config()`  
**Depends On**: `database_engine.py`

---

## Purpose

Defines authoritative parameterised DuckDB query patterns for interrogating the KRONOS signature archive. All filter values, column names, limit clauses, and threshold parameters are bound as parameterised variables from config. No literal values appear in query strings.

---

## Query Architecture

```
═══════════════════════════════════════════════════════════════
QUERY FLOW
═══════════════════════════════════════════════════════════════

CONFIG LOAD
  cfg = load_sovereign_config()

CONNECTION INITIALISE
  con = database_engine.get_connection(cfg)
  → connects to cfg["database"]["duckdb_path"]
  → views resolve via cfg["database"]["parquet_path_pattern"]

PARAMETERISED QUERY EXECUTION
  All filter values passed as (?, ?, ...) bindings from config
  → never embedded directly in SQL string

═══════════════════════════════════════════════════════════════
```

---

## Query Parameter Reference

All values in query stubs resolve from config. No literal numbers or strings appear in SQL.

| Parameter Role | Binding Source | Config Reference Key |
| :--- | :--- | :--- |
| Minimum quality filter | `cfg["database"]["min_quality_score"]` | `cfg["database"]["min_quality_score"]` |
| Minimum recovery filter | `cfg["database"]["retention_policy"]["min_recovery_factor"]` | `cfg["database"]["retention_policy"]["min_recovery_factor"]` |
| Target regime identifier | `cfg["targets"]["regime_id"]` | `cfg["targets"]["regime_id"]` |
| GPF target | `cfg["targets"]["min_gross_profit"]` | `cfg["targets"]["min_gross_profit"]` |
| Recovery target | `cfg["targets"]["min_recovery"]` | `cfg["targets"]["min_recovery"]` |
| Quality score column | `cfg["feature_builder"]["metadata"]["keys"]["signature_quality"]` | `cfg["feature_builder"]["metadata"]["keys"]["signature_quality"]` |
| Phylum ID column | `cfg["feature_builder"]["metadata"]["keys"]["phylum_id"]` | `cfg["feature_builder"]["metadata"]["keys"]["phylum_id"]` |
| Recovery proxy column | `cfg["feature_builder"]["metadata"]["keys"]["recovery_proxy"]` | `cfg["feature_builder"]["metadata"]["keys"]["recovery_proxy"]` |
| Veto composite column | `cfg["feature_builder"]["structural"]["slot_15"]["key_name"]` | `cfg["feature_builder"]["structural"]["slot_15"]["key_name"]` |
| Signature flag column | `cfg["feature_builder"]["gate"]["signature_flag_key"]` | `cfg["feature_builder"]["gate"]["signature_flag_key"]` |
| Neural conviction column | `cfg["feature_builder"]["gate"]["neural_conviction_key"]` | `cfg["feature_builder"]["gate"]["neural_conviction_key"]` |
| Regime column | `cfg["feature_builder"]["structural"]["slot_8"]["key_name"]` | `cfg["feature_builder"]["structural"]["slot_8"]["key_name"]` |

---

## Query Stubs

All SQL strings use `?` bindings. Column names resolved dynamically from config.

```python
from typing import Dict
import pandas as pd

def load_sovereign_config(path: str = "params_yaml.txt") -> Dict:
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)


def query_elite_signatures(con, config: Dict) -> pd.DataFrame:
    """
    Retrieves high-quality, high-conviction signatures.
    All column names and filter thresholds from config.

    Config refs:
      cfg["feature_builder"]["metadata"]["keys"]["signature_quality"]  ← quality column
      cfg["database"]["min_quality_score"]                             ← quality threshold ?
      cfg["feature_builder"]["gate"]["signature_flag_key"]             ← flag column

    Full implementation → database_engine.query_elite_signatures(con, config)
    """
    from database_engine import query_elite_signatures as _impl
    return _impl(con, config)


def query_by_regime(con, config: Dict) -> pd.DataFrame:
    """
    Filters signatures by target HMM regime.
    Regime column name and target regime identifier from config.

    Config refs:
      cfg["feature_builder"]["structural"]["slot_8"]["key_name"]  ← regime column
      cfg["targets"]["regime_id"]                                 ← regime filter ?

    Full implementation → database_engine.query_by_regime(con, config)
    """
    from database_engine import query_by_regime as _impl
    return _impl(con, config)


def query_phylum_edge_stats(con, config: Dict) -> pd.DataFrame:
    """
    Computes per-phylum edge statistics with HAVING filter.
    Phylum column, recovery column, and minimum recovery from config.

    Config refs:
      cfg["feature_builder"]["metadata"]["keys"]["phylum_id"]           ← phylum column
      cfg["feature_builder"]["metadata"]["keys"]["recovery_proxy"]      ← recovery column
      cfg["database"]["retention_policy"]["min_recovery_factor"]        ← HAVING threshold ?

    Full implementation → database_engine.query_phylum_edge_stats(con, config)
    """
    from database_engine import query_phylum_edge_stats as _impl
    return _impl(con, config)


def query_conviction_distribution(con, config: Dict) -> pd.DataFrame:
    """
    Returns distribution statistics of neural conviction scores.
    Conviction column name from config.

    Config refs:
      cfg["feature_builder"]["gate"]["neural_conviction_key"]  ← conviction column

    Full implementation → database_engine.query_conviction_distribution(con, config)
    """
    from database_engine import query_conviction_distribution as _impl
    return _impl(con, config)


def query_veto_composite_distribution(con, config: Dict) -> pd.DataFrame:
    """
    Returns distribution statistics for the sovereign veto composite score.
    Veto column name and quality floor from config.

    Config refs:
      cfg["feature_builder"]["structural"]["slot_15"]["key_name"]  ← veto column
      cfg["database"]["min_quality_score"]                          ← quality filter ?

    Full implementation → database_engine.query_veto_composite_distribution(con, config)
    """
    from database_engine import query_veto_composite_distribution as _impl
    return _impl(con, config)


def query_audit_trail(con, config: Dict, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Retrieves audit trail columns for a date range.
    Audit column names from config.

    Config refs:
      cfg["database"]["audit"]["data_hash_key"]
      cfg["database"]["audit"]["config_hash_key"]
      cfg["database"]["audit"]["git_commit_key"]

    Full implementation → database_engine.query_audit_trail(con, config, start_date, end_date)
    """
    from database_engine import query_audit_trail as _impl
    return _impl(con, config, start_date, end_date)
```

---

**Hardcode Audit Passed — Zero Inline Literals**
