"""
KRONOS Orchestrator Engine — Full Sovereign Pipeline
"""

from typing import Dict

def run_full_pipeline(config: Dict) -> Dict:
    """End-to-end sovereign execution."""
    import hardcode_validator_engine
    import data_engine
    import miner_engine
    import database_engine

    const = config["reproducibility"]["constants"]

    # STAGE 1 — PRE-FLIGHT
    hardcode_validator_engine.run_full_validation(".", config)
    print("[OK] Sovereignty validator passed.")

    # STAGE 2 — DATA INGESTION
    raw_candles = data_engine.fetch_or_load_ohlcv(config)
    # The database/miner engines will reload shard data cleanly via data_engine.load_shard_data
    print(f"[OK] Data loaded: {len(raw_candles):,} bars from {raw_candles.index[const['zero_int']]} to {raw_candles.index[-const['one_int']]}")

    # STAGE 3 — DATABASE
    database_engine.initialize_duckdb_views(config)

    # STAGE 4 — MINING
    # run_miner internally executes compile_global_ontology after all shards complete,
    # which writes globally-stable slot_28 phylum labels back to signatures_compact.parquet.
    miner_engine.run_miner(config, config["data"]["fetch_start_date"], None)

    # STAGE 5 — POST-MINING VIEW REFRESH
    # Re-initialise the DuckDB view so it picks up the ontology-compiled compact parquet.
    # Without this, the view created in Stage 3 pre-dates the slot_28 update.
    database_engine.initialize_duckdb_views(config)
    print("[OK] DuckDB view refreshed post-ontology compilation.")

    stats = {"bars": len(raw_candles), "status": "completed"}
    print("[OK] Full KRONOS Pipeline completed successfully.")
    return stats


def load_sovereign_config(path: str = "params_yaml.txt") -> Dict:
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)
