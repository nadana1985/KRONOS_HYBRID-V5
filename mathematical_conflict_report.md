# KRONOS V5 Mathematical & Structural Conflict Report (RESOLVED)

This document presents the authoritative quantitative audit of the KRONOS V5 hybrid engine codebase. It records the complete resolutions of the eighteen mathematical inconsistencies, scale mismatches, lookahead leaks, coding errors, and dead-code blocks previously identified across the structural, neural, validation, and data engines.

---

## Severity Assessment Matrix

| ID | Conflict Summary | Location | Severity | Type | Resolution Status |
|---|---|---|---|---|---|
| 1 | Sign cancellation in `slot_15` weighted sum | [structural_engine.py](file:///f:/KRONOS_Madurai/structural_engine.py) | **Critical** | Mathematical | **RESOLVED** (Absolute signed mapping) |
| 2 | Scale & magnitude mismatch in `slot_15` | [structural_engine.py](file:///f:/KRONOS_Madurai/structural_engine.py) | **Critical** | Mathematical | **RESOLVED** (Empirical rolling min-max) |
| 3 | Path-dependent expanding max in `slot_10` | [structural_engine.py](file:///f:/KRONOS_Madurai/structural_engine.py) | High | Statistical | **RESOLVED** (Rolling max) |
| 4 | Lookahead leak via `quantile(0.99)` in `slot_10` | [structural_engine.py](file:///f:/KRONOS_Madurai/structural_engine.py) | **Critical** | Causal | **RESOLVED** (Rolling window quantile) |
| 5 | Invalid annualised Sharpe on trade returns | [backtest_engine.py](file:///f:/KRONOS_Madurai/backtest_engine.py) | High | Mathematical | **RESOLVED** (Periodic PnL series) |
| 6 | Dead global vol reference window (Flaw 13 loop bypass) | [neural_integration_engine.py](file:///f:/KRONOS_Madurai/neural_integration_engine.py) | High | Logic | **RESOLVED** (Unrestricted tail slicing) |
| 7 | Conviction threshold temporal lag across regime shifts | [neural_integration_engine.py](file:///f:/KRONOS_Madurai/neural_integration_engine.py) | High | Statistical | **RESOLVED** (Time-based rolling windows) |
| 8 | Information-free synthetic volume splits | [data_engine.py](file:///f:/KRONOS_Madurai/data_engine.py) | **Critical** | Conceptual | **RESOLVED** (Bulk Volume Classification BVC) |
| 9 | `slot_25` (MFE Projection) is a tautological copy of `slot_15` | [feature_builder_engine.py](file:///f:/KRONOS_Madurai/feature_builder_engine.py) | High | Conceptual | **RESOLVED** (Volatility-scaled projection) |
| 10 | `slot_26` (Neural Regime) stores conviction norm vs. regime index | [feature_builder_engine.py](file:///f:/KRONOS_Madurai/feature_builder_engine.py) | High | Conceptual | **RESOLVED** (Rolling percentile ranking) |
| 11 | `slot_29` hash overflows float16 and dominates clustering | [feature_builder_engine.py](file:///f:/KRONOS_Madurai/feature_builder_engine.py) | **Critical** | Numerical | **RESOLVED** (Bounded hash + cluster exclusion) |
| 12 | YAML key collision on `one_day_int` | [params_yaml.txt](file:///f:/KRONOS_Madurai/params_yaml.txt) | Medium | Config | **RESOLVED** (Duplicate key deprecated) |
| 13 | Cold-start buffer zeros cause neural gate warm-up leaks | [feature_builder_engine.py](file:///f:/KRONOS_Madurai/feature_builder_engine.py) | High | Statistical | **RESOLVED** (Pre-warmed conviction buffer) |
| 14 | Long-only MFE/MAE bias discards all valid short signatures | [miner_engine.py](file:///f:/KRONOS_Madurai/miner_engine.py) | **Critical** | Conceptual | **RESOLVED** (Directional MFE/MAE swap) |
| 15 | Unbounded recovery factor corrupts GPF and HDBSCAN distances | [miner_engine.py](file:///f:/KRONOS_Madurai/miner_engine.py) | High | Numerical | **RESOLVED** (Capped at recovery_cap prior) |
| 16 | Log-return vs. pct-change units mismatch in `slot_7` | [structural_engine.py](file:///f:/KRONOS_Madurai/structural_engine.py) | High | Mathematical | **RESOLVED** (Symmetric log-vol space) |
| 17 | HMM ordinal labels treated as cardinal values in `slot_8` | [structural_engine.py](file:///f:/KRONOS_Madurai/structural_engine.py) | High | Mathematical | **RESOLVED** (Sorted low-to-high state map) |
| 18 | `slot_31` quality score divisor epsilon guard is semantically incorrect | [feature_builder_engine.py](file:///f:/KRONOS_Madurai/feature_builder_engine.py) | Low | Code Quality | **RESOLVED** (Clean integer divisor) |

---

## Authoritative Resolutions Details

### 1. Sign Cancellation in Weighted Linear Composite (`slot_15`)
*   **Resolution Status**: **FULLY RESOLVED**
*   **Implementation Details**: `_normalize_slot()` in `structural_engine.py` checks if `low < 0`. If a slot yields a signed indicator (e.g., Z-scores or Delta Absorption), it automatically applies `.abs()` to the series before normalisation. This guarantees extreme deviations on either side contribute positively to the composite anomaly index.

### 2. Scale & Magnitude Mismatch in Linear Summation (`slot_15`)
*   **Resolution Status**: **FULLY RESOLVED**
*   **Implementation Details**: Every slot output is now dynamically normalized to a uniform `[0.0, 1.0]` range prior to weighted aggregation. Normalized slot bounds are defined inside `per_slot_normalisation` configuration keys, with empirical rolling min-max as a standard fallback.

### 3 & 4. Path Dependency & Causal Violation (Lookahead Leak) in Wick Prominence (`slot_10`)
*   **Resolution Status**: **FULLY RESOLVED**
*   **Implementation Details**: The global expanding maximum and absolute quantile calls have been completely deprecated. Wick ratio boundaries are evaluated strictly causally using a `rolling(w).quantile()` window and `rolling(w).max()` normalisation, preserving temporal independence.

### 5. Annualised Sharpe Ratio Correctness
*   **Resolution Status**: **FULLY RESOLVED**
*   **Implementation Details**: Sharpe calculations are now evaluated on continuous daily periodic return series constructed from signature timestamps and trade hold durations, avoiding sparse calendar-mismatch distortions.

### 6. Dead Volatility Gate Reference Window
*   **Resolution Status**: **FULLY RESOLVED**
*   **Implementation Details**: Slicing has been moved downstream. The volatility gate anchor receives the entire causal series prior to standard deviation calculations, preserving the full `global_vol_ref_bars` history window.

### 7. Temporal Lag in Dynamic Conviction Thresholding
*   **Resolution Status**: **FULLY RESOLVED**
*   **Implementation Details**: Changed from a static count-based buffer to a rolling calendar-day buffer (`conviction_time_window_days: 7`). Conviction stats scale dynamically with real-time trading frequency.

### 8. Conceptual Flaw: Synthetic Volume splits
*   **Resolution Status**: **FULLY RESOLVED**
*   **Implementation Details**: Replaced random deterministic SHA-256 splits with a Bulk Volume Classification (BVC) algorithm in `data_engine.py` (rolling standard deviation of price changes mapped through a sigmoid cumulative function), aligning volumes with microstructural models.

### 9 & 10. `slot_25` and `slot_26` Conceptual Redundancy
*   **Resolution Status**: **FULLY RESOLVED**
*   **Implementation Details**: `slot_25` properly executes a volatility-adjusted excursion projection. `slot_26` calculates HMM regime probability rankings using time-based percentile distributions rather than conviction norms.

### 11. `slot_29` Hash Overflow & Distance Corruption
*   **Resolution Status**: **FULLY RESOLVED**
*   **Implementation Details**: The timestamp SHA-256 hash is normalised by the maximum hex integer boundary, clamping it to `[0.0, 1.0]`. In addition, `miner_engine.compile_global_ontology` strictly limits feature columns to structural weights, completely excluding `slot_29` from the distance matrix.

### 12. YAML Key Collision in config
*   **Resolution Status**: **FULLY RESOLVED**
*   **Implementation Details**: The redundant key definitions have been removed from `params_yaml.txt`.

### 13. Cold-Start Buffer Zeros
*   **Resolution Status**: **FULLY RESOLVED**
*   **Implementation Details**: Warm-up bars are used to pre-seed the dynamic conviction threshold prior to evaluations, preventing low-conviction leakages.

### 14 & 15. Directional Excursions & Recovery Bounds
*   **Resolution Status**: **FULLY RESOLVED**
*   **Implementation Details**: `compute_forward_metrics` evaluates directional absorption trends. Bullish reversals use standard long metrics; bearish reversals swap MFE/MAE bounds. Recovery factor calculations are safely clipped at `recovery_cap` to prevent division-by-zero overflow.

### 16. Unit Mismatches in `slot_7`
*   **Resolution Status**: **FULLY RESOLVED**
*   **Implementation Details**: Price acceleration and volume changes are both calculated inside symmetric log-return space.

### 17. HMM Ordinal Labels in `slot_8`
*   **Resolution Status**: **FULLY RESOLVED**
*   **Implementation Details**: Gaussian HMM states are mapped in ascending order of their mean volatility covariance, guaranteeing state labels represent true, sorted ordinal volatility intensities.

### 18. Divisor Epsilon Guard in `slot_31`
*   **Resolution Status**: **FULLY RESOLVED**
*   **Implementation Details**: Redundant additions are pruned, simplifying the average to a clean integer divisor.
