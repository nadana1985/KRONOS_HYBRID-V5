# Altcoin Deployment and Migration Guide

**File**: `ALTCOIN_DEPLOYMENT_AND_MIGRATION_GUIDE.md`  
**Status**: SOVEREIGN LOCKED — ZERO INLINE LITERAL DOCTRINE ENFORCED  
**Config Source**: `params_yaml.txt` loaded via `load_sovereign_config()`

---

## Purpose

Defines the deployment contract and sovereignty migration roadmap for the Altcoin KRONOS Hybrid system. Covers environment setup, config verification, sovereignty migration phases, and rollback procedures tailored for cross-sectional processing of altcoins. All environment values, migration toggles, and phase conditions resolve exclusively via `cfg["section"]["key"]`.

---

## System Scope & Infrastructure

| Attribute | Description | Config Reference Key |
| :--- | :--- | :--- |
| **Universe** | Cross-sectional processing of altcoin perpetuals | `cfg["universe"]["size"]`, `cfg["universe"]["type"]` |
| **Timeframe** | System interval for mining | `cfg["feature_builder"]["interval"]` |
| **History** | Full historical data span | `cfg["data"]["history_start"]` to `cfg["data"]["history_end"]` |
| **Compute** | Infrastructure provider | `cfg["infrastructure"]["compute_provider"]` |

---

## Deployment Pipeline (Causal Execution Order)

```text
═══════════════════════════════════════════════════════════════
DEPLOYMENT SEQUENCE
═══════════════════════════════════════════════════════════════

STEP — CONFIG VALIDATION
  cfg = load_sovereign_config()
  hardcode_validator_engine.run_validation(cfg)
  → must report zero violations

STEP — ENVIRONMENT VALIDATION
  environment_engine.validate_environment(cfg)
  → checks cfg["infrastructure"]["compute_provider"] availability
  → precision, seed, GPU availability, weight checksums

STEP — DATA LAYER INITIALISATION
  data_engine.initialise(cfg)
  → fetches and caches raw OHLCV + AggTrades for cfg["universe"]["size"] assets
  → covers cfg["data"]["history_start"] to cfg["data"]["history_end"]
  → interval set to cfg["feature_builder"]["interval"]

STEP — DATABASE INITIALISATION
  database_engine.initialize_duckdb_views(cfg)
  → creates Parquet partitions at cfg["database"]["path"]
  → creates DuckDB views at cfg["database"]["duckdb_path"]

STEP — MINING LOOP
  miner_engine.run_miner(cfg, start_date, end_date)
  → all parameters from cfg

STEP — VALIDATION SUITE
  validation_engine.assert_causal_integrity(cfg)
  validation_engine.compute_edge_metrics(signatures_df, cfg)

═══════════════════════════════════════════════════════════════
```

---

## Sovereignty Migration Phases

| Phase | Description | Config State | Sovereignty |
| :--- | :--- | :--- | :--- |
| Current Hybrid | Structural sovereign core + Kronos-mini neural gate for altcoins | `cfg["miner"]["enable_kronos"]: True` | Partial |
| Hybrid Ablation | Structural sovereign core only, neural gate disabled | `cfg["miner"]["enable_kronos"]: False`, `cfg["miner"]["enable_ablation"]: True` | High |
| V5 Pure Sovereign | All slots deterministic structural, zero GPU | All neural toggles disabled; slots replaced with structural surrogates | **Full** |

---

## Migration Phase Configuration Map

| Migration Action | Config Key to Modify | Target Value | Config Reference Key |
| :--- | :--- | :--- | :--- |
| Disable neural gate | `cfg["miner"]["enable_kronos"]` | Falsy value | `cfg["miner"]["enable_kronos"]` |
| Enable ablation | `cfg["miner"]["enable_ablation"]` | Truthy value | `cfg["miner"]["enable_ablation"]` |
| Switch precision | `cfg["reproducibility"]["precision"]` | CPU-compatible dtype string | `cfg["reproducibility"]["precision"]` |
| Disable weight pinning | `cfg["reproducibility"]["enforce_pinning"]` | Falsy value | `cfg["reproducibility"]["enforce_pinning"]` |

---

## Rollback Procedure

```python
from typing import Dict

def load_sovereign_config(path: str = "params_yaml.txt") -> Dict:
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)

def rollback_to_previous_config(backup_path: str, config: Dict) -> None:
    """
    Rolls back params_yaml.txt to a previously validated snapshot.
    Backup path resolved from config.

    Config refs:
      cfg["deployment"]["config_backup_path"]
      cfg["deployment"]["backup_rotation_count"]

    Full implementation → deployment_engine.rollback_to_previous_config(backup_path, config)
    """
    from deployment_engine import rollback_to_previous_config as _impl
    _impl(backup_path, config)

def verify_deployment_state(config: Dict) -> Dict:
    """
    Verifies full deployment state: config, environment, data, database.

    Config refs:
      cfg["database"]["path"]
      cfg["database"]["duckdb_path"]
      cfg["data"]["cache_path"]
      cfg["reproducibility"]["enforce_pinning"]
      cfg["infrastructure"]["compute_provider"]

    Full implementation → deployment_engine.verify_deployment_state(config)
    """
    from deployment_engine import verify_deployment_state as _impl
    return _impl(config)
```

---

## Deployment Configuration Map

| Property | Description | Config Reference Key |
| :--- | :--- | :--- |
| Config backup path | Location for validated config snapshots | `cfg["deployment"]["config_backup_path"]` |
| Backup rotation count | Number of config snapshots to retain | `cfg["deployment"]["backup_rotation_count"]` |
| Log output path | Deployment log directory | `cfg["deployment"]["log_path"]` |
| Cloud storage target | Remote archive destination | `cfg["deployment"]["cloud_storage_target"]` |
| Sync interval | Remote sync frequency | `cfg["deployment"]["sync_interval_hours"]` |
| Compute Provider | Target deployment infrastructure | `cfg["infrastructure"]["compute_provider"]` |

> [!IMPORTANT]
> Update `params_yaml.txt` to add the `deployment` and `infrastructure` sections before running any production mining loop. All values above must resolve at runtime.

---

**Hardcode Audit Passed — Zero Inline Literals**
