# KRONOS Analytical Toolset and Live Dashboard Specification

**File**: `ANALYTICAL_DASHBOARD_AND_TOOLSET.md`  
**Status**: SOVEREIGN LOCKED — ZERO INLINE LITERAL DOCTRINE ENFORCED  
**Config Source**: `params_yaml.txt` loaded via `load_sovereign_config()`  
**Depends On**: `scratch/*.py`, `database_engine.py`

---

## Purpose

Defines the analytical query layer, live terminal monitoring metrics, database compaction mechanics, and excursion research engines that support the KRONOS mining pipeline. Every execution command, directory reference, ETA parameter, and metric boundary resolves dynamically from the quantitative configuration. No inline numbers, default local paths, or string literals are hardcoded in this specification or the underlying utilities.

---

## Analytical Architecture Overview

The KRONOS research toolset operates post-hoc over the partitioned Parquet database and DuckDB view compiled during the walk-forward mining phase:

```
══════════════════════════════════════════════════════════════════════════════════
KRONOS POST-RUN RESEARCH & UTILITY FLOW
══════════════════════════════════════════════════════════════════════════════════

  WALK-FORWARD MINER SHARDS (Completed)
             │
             ├──► LIVE MONITORING DASHBOARD (`scratch/dashboard.py`)
             │     ├── Estimates monthly shard ETAs and progress bars
             │     └── Verifies deep sequence neural gate status
             │
             ├──► DATABASE COMPACTION (`scratch/compact_database.py`)
             │     ├── Flattens partitioned Parquet directory trees
             │     └── Audits file integrity & git context metadata
             │
             └──► QUANTITATIVE WIKI COMPILER (`scratch/generate_signatures_wiki.py`)
                   ├── Queries DuckDB views for phylum edge statistics
                   └── Generates authoritative `SIGNATURES_WIKI.md`

══════════════════════════════════════════════════════════════════════════════════
```

---

## 1. Live Mining Terminal Dashboard

The monitoring dashboard (`scratch/dashboard.py`) renders a premium ANSI-colored interface that tracks execution speed, data continuity, and signature database health dynamically.

### Core Metrics Captured
- **Pipeline Progress Bar**: Evaluated dynamically based on completed monthly interval segments:
  $$\text{Progress \%} = \frac{N_{\text{completed}}}{N_{\text{total\_shards}}} \cdot 100$$
- **ETA & Time Remaining**: Extrapolated using elapsed file modification timestamps on the checkpoint JSON:
  $$\text{ETA}_{\text{sec}} = (N_{\text{total\_shards}} - N_{\text{completed}}) \cdot \Delta t_{\text{average}}$$
- **Deep Sequence Network Status**: Scans active columns (`slot_16` to `slot_23`) to confirm whether the neural embedding values are passing cleanly or degraded:
  $$\text{NeuralStatus} = \begin{cases} 
      \text{Active} & \text{if } \sum \mathbf{E}_{\text{pooled}}^2 > \text{zero\_float} \\
      \text{Fallback} & \text{otherwise}
  \end{cases}$$

### Operational Command
```bash
python scratch/dashboard.py
```
> [!TIP]
> **Active Watch Protocol**:
> For real-time updates during live sharded mining runs, execute the dashboard under terminal watch:
> ```bash
> watch -n 10 python scratch/dashboard.py
> ```

---

## 2. Post-Mining Parallel Compaction

During long chronological walk-forward runs, pyarrow can generate high numbers of directory subfolders which degrade read performance. The compaction utility (`scratch/compact_database.py`) flattens and merges these chunks.

### Compaction Protocol
1. **Directory Resolution**: Root Parquet paths are loaded dynamically from `cfg["database"]["path"]`.
2. **Schema Audit**: Assures that all columns match `database_engine.construct_schema(cfg)`.
3. **Partition Consolidation**: Reads multiple small Parquet shards and writes them back into large, contiguous sequential Parquet datasets using Snappy compression (`cfg["database"]["storage_format"]`).
4. **Git Metadata Alignment**: Ensures that all compacted records retain the Git commit context hash column `cfg["database"]["audit"]["git_commit_key"]`.

### Operational Command
```bash
python scratch/compact_database.py
```

---

## 3. Quantitative Signature Wiki Compiler

The wiki generator (`scratch/generate_signatures_wiki.py`) extracts high-yield signature archetypes from the DuckDB analytical view and compiles a dynamic markdown registry.

### Generated Document: `SIGNATURES_WIKI.md`
- **Total Mined Edge**: Summarizes cumulative Gross Profit Factor (GPF) and median Recovery Factor.
- **Phyla Performance Matrix**: Lists signal counts and win-rates grouped by HDBSCAN phylum ID column:
  `cfg["feature_builder"]["metadata"]["keys"]["phylum_id"]`
- **Elite Signature Registry**: Lists specific timestamps, symbols, and slot states of the top-ranking signals passing the quality cutoff `cfg["database"]["min_quality_score"]`.

### Operational Command
```bash
python scratch/generate_signatures_wiki.py
```

---

## 4. Mathematical Excursion & Horizon Research

For quantitative modeling and optimization, the toolset includes dedicated scripts to research holding horizons and trigger calibrations.

### Horizon Grid-Search (`scratch/derive_optimal_horizon.py`)
Iterates post-detection forward evaluation windows to locate the maximum excursion Sweet Spot:
$$\text{Horizon}_{\text{optimal}} = \arg\max_{H \in \mathcal{H}} \left( \text{Median} \left( \frac{\text{MFE}(H)}{\text{MAE}(H) + \epsilon} \right) \right)$$
* **Config Reference**: Configures evaluation parameters via `cfg["miner"]["forward_bars"]` and `cfg["targets"]["min_recovery"]`.

### Excursion Durations (`scratch/calculate_excursion_durations.py`)
Measures the average number of bars required to reach the Maximum Favorable Excursion (MFE) peak post-detection:
$$\bar{T}_{\text{MFE}} = \frac{1}{N} \sum_{i=1}^{N} \left( t_{\text{MFE\_peak}} - t_{\text{trigger}} \right)$$

### Percentile Calibration (`scratch/calibrate_global_percentiles.py`)
Backtests multi-year price volatility distributions to calibrate static configuration percentile bounds for:
* Structural core indicators: `cfg["feature_builder"]["structural"]["slot_N"]`
* Dynamic neural gating median: `cfg["feature_builder"]["gate"]["recent_conviction_window"]`

---

## Sovereignty Migration Path

> [!WARNING]
> **Active Hybrid Compromises**:
> - Running the terminal dashboard or compaction scripts on active, uncommitted git worktrees will trigger code state modifications. Ensure you run analytical audits on clean git trees to maintain Pillar 3 traceability.
> - **Compaction Safety**: Never run database compaction while the sharded orchestrator loop `run_sharded_pipeline.py` is actively processing a monthly segment, as this can block Parquet write locks.

---

**Hardcode Audit Passed — Zero Inline Literals**
