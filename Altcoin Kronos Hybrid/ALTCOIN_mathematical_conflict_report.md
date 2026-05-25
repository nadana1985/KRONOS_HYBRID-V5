# ALTCOIN KRONOS HYBRID Mathematical & Structural Conflict Report

This document presents the authoritative quantitative audit of the Altcoin Kronos Hybrid engine codebase. It details mathematical inconsistencies, scale mismatches, lookahead leaks, coding errors, and dead-code blocks found across the structural, neural, validation, and data engines. The system operates on `cfg["universe"]["size"]` perpetual altcoins for cross-sectional processing, at a `cfg["feature_builder"]["interval"]` resolution over full historical data (Genesis to present) using Lightning AI Cloud Mining compute infrastructure.

---

## Severity Assessment Matrix

| ID | Conflict Summary | Location | Severity | Type |
|---|---|---|---|---|
| 1 | Sign cancellation in `slot_15` weighted sum | [structural_engine.py](file:///g:/KRONOS%20HYBRID/structural_engine.py#L84-L115) | **Critical** | Mathematical |
| 2 | Scale & magnitude mismatch in `slot_15` | [structural_engine.py](file:///g:/KRONOS%20HYBRID/structural_engine.py#L84-L115) | **Critical** | Mathematical |
| 3 | Path-dependent expanding max in `slot_10` | [structural_engine.py](file:///g:/KRONOS%20HYBRID/structural_engine.py#L584-L585) | High | Statistical |
| 4 | Lookahead leak via `quantile` in `slot_10` | [structural_engine.py](file:///g:/KRONOS%20HYBRID/structural_engine.py#L583) | **Critical** | Causal |
| 5 | Invalid annualised Sharpe on trade returns | [backtest_engine.py](file:///g:/KRONOS%20HYBRID/backtest_engine.py#L79-L88) | High | Mathematical |
| 6 | Dead global vol reference window (Flaw 13 loop bypass) | [neural_integration_engine.py](file:///g:/KRONOS%20HYBRID/neural_integration_engine.py#L372-L380) | High | Logic |
| 7 | Conviction threshold temporal lag across regime shifts | [neural_integration_engine.py](file:///g:/KRONOS%20HYBRID/neural_integration_engine.py#L276-L300) | High | Statistical |
| 8 | Information-free synthetic volume splits | [data_engine.py](file:///g:/KRONOS%20HYBRID/data_engine.py#L182-L201) | **Critical** | Conceptual |
| 9 | `slot_25` (MFE Projection) is a tautological copy of `slot_15` | [feature_builder_engine.py](file:///g:/KRONOS%20HYBRID/feature_builder_engine.py#L217-L218) | High | Conceptual |
| 10 | `slot_26` (Neural Regime) stores conviction norm vs. regime index | [feature_builder_engine.py](file:///g:/KRONOS%20HYBRID/feature_builder_engine.py#L221-L222) | High | Conceptual |
| 11 | `slot_29` hash overflows float16 and dominates clustering | [feature_builder_engine.py](file:///g:/KRONOS%20HYBRID/feature_builder_engine.py#L260-L261) | **Critical** | Numerical |
| 12 | YAML key collision on `one_day_int` | [params_yaml.txt](file:///g:/KRONOS%20HYBRID/params_yaml.txt#L146-L155) | Medium | Config |
| 13 | Cold-start buffer zeros cause neural gate warm-up leaks | [feature_builder_engine.py](file:///g:/KRONOS%20HYBRID/feature_builder_engine.py#L142-L152) | High | Statistical |
| 14 | Long-only MFE/MAE bias discards all valid short signatures | [miner_engine.py](file:///g:/KRONOS%20HYBRID/miner_engine.py#L207-L217) | **Critical** | Conceptual |
| 15 | Unbounded recovery factor corrupts GPF and HDBSCAN distances | [miner_engine.py](file:///g:/KRONOS%20HYBRID/miner_engine.py#L213-L217) | High | Numerical |
| 16 | Log-return vs. pct-change units mismatch in `slot_7` | [structural_engine.py](file:///g:/KRONOS%20HYBRID/structural_engine.py#L409-L421) | High | Mathematical |
| 17 | HMM ordinal labels treated as cardinal values in `slot_8` | [structural_engine.py](file:///g:/KRONOS%20HYBRID/structural_engine.py#L517-L518) | High | Mathematical |
| 18 | `slot_31` quality score divisor epsilon guard is semantically incorrect | [feature_builder_engine.py](file:///g:/KRONOS%20HYBRID/feature_builder_engine.py#L269-L271) | Low | Code Quality |

---

## 1. Sign Cancellation in Weighted Linear Composite (`slot_15`)
*   **File References**: [structural_engine.py:L84-L115](file:///g:/KRONOS%20HYBRID/structural_engine.py#L84-L115), [params_yaml.txt:L35-L52](file:///g:/KRONOS%20HYBRID/params_yaml.txt#L35-L52)
*   **Severity**: **Critical**
*   **Formula**:
    $$S_{\text{veto}}(t) = \text{clip}\left(\sum_{i=0}^{\text{cfg["structural_engine"]["max_linear_slot"]}} w_i \cdot S_i(t), \text{cfg["constants"]["zero_f"]}, \text{cfg["constants"]["one_f"]}\right)$$

### Detailed Conflict
The composite veto score ($S_{\text{veto}}$) is designed as a raw anomaly intensity index where a higher score indicates a stronger reversal signal. However, several component slots yield **signed** indicators that can be negative, while other slots are strictly positive. Specifically:
*   `slot_0` (`bid_ask_absorb`) outputs in $[-\text{cfg["constants"]["one_f"]}, \text{cfg["constants"]["one_f"]}]$.
*   `slot_3` (`log_var_ratio`) outputs unbounded positive or negative values depending on volatility compression/expansion.
*   `slot_4` (`fractal_hurst`) outputs positive values for mean reversion ($H < \text{cfg["structural_engine"]["hurst_threshold"]}$) and negative values for trend persistence ($H > \text{cfg["structural_engine"]["hurst_threshold"]}$).
*   `slot_7` (`volume_price_divergence`) and `slot_12` (`microprice_deviation`) both return signed, unbounded z-scores.

If any of these slots output a strong negative signal (e.g. severe trend persistence or extreme bearish delta absorption), their negative terms **subtract** from the weighted sum. This cancels out positive anomaly signals from other slots, lowering $S_{\text{veto}}$ and preventing the veto gate from triggering on valid directional extremes.

### Solution
Take the absolute values of all signed indicators, or map them onto a strict $[\text{cfg["constants"]["zero_f"]}, \text{cfg["constants"]["one_f"]}]$ range representing deviation magnitude before performing the weighted summation.

---

## 2. Scale & Magnitude Mismatch in Linear Summation (`slot_15`)
*   **File References**: [structural_engine.py:L84-L115](file:///g:/KRONOS%20HYBRID/structural_engine.py#L84-L115), [params_yaml.txt:L19-L33](file:///g:/KRONOS%20HYBRID/params_yaml.txt#L19-L33)
*   **Severity**: **Critical**

### Detailed Conflict
The weights assigned to slots $\text{cfg["structural_engine"]["min_slot"]}$ to $\text{cfg["structural_engine"]["max_linear_slot"]}$ sum to $\text{cfg["constants"]["one_f"]}$ (enforced at runtime). However, the slot outputs are completely un-aligned in magnitude and range:
*   `slot_2` (`spectral_entropy`) returns raw Shannon entropy. For a window of `cfg["structural_engine"]["spectral_window"]` bars, its maximum value is $\log_e(\text{cfg["structural_engine"]["spectral_bins"]})$.
*   `slot_13` (`shannon_entropy`) returns raw Shannon entropy over `cfg["structural_engine"]["shannon_bins"]` bins, yielding values up to $\log_e(\text{cfg["structural_engine"]["shannon_bins"]})$.
*   `slot_6` (`ema_ribbon_deviation`), `slot_7` (`volume_price_divergence`), and `slot_12` (`microprice_deviation`) return raw z-scores which frequently exceed $\pm \text{cfg["structural_engine"]["max_z_score"]}$.
*   Other slots (such as `slot_1` and `slot_9`) are strictly bounded in $[\text{cfg["constants"]["zero_f"]}, \text{cfg["constants"]["one_f"]}]$.

Because raw, unaligned magnitudes are summed, slots with larger natural bounds (like Spectral Entropy and Z-scores) dominate the composite score, rendering the configured configuration weights mathematically meaningless.

### Solution
Map each slot output onto a uniform $[\text{cfg["constants"]["zero_f"]}, \text{cfg["constants"]["one_f"]}]$ range (e.g. using a rolling CDF or percentile transformation) prior to weighted aggregation.

---

## 3. Non-Stationary, Path-Dependent Normalization in Wick Prominence (`slot_10`)
*   **File References**: [structural_engine.py:L584-L585](file:///g:/KRONOS%20HYBRID/structural_engine.py#L584-L585)
*   **Severity**: High
*   **Implementation**:
    ```python
    norm = score.expanding().max().clip(lower=epsilon)
    return (score / norm).clip(zero_f, one_f).fillna(zero_f)
    ```

### Detailed Conflict
`slot_10` normalizes wick ratios using an expanding maximum. This introduces two mathematical issues:
1.  **Path Dependency**: If a massive wick occurs early in the full historical backtest (Genesis to present) processing on Lightning AI Cloud Mining, `norm` is locked at a high value. All subsequent wick ratios across the `cfg["universe"]["size"]` cross-sectional coins are compressed to near-zero, starving the engine of wick signals.
2.  **Scale Variance**: The representation of a bar at index $t$ changes depending on its position in the full multi-year run, breaking the temporal consistency of the signatures database.

### Solution
Replace the expanding maximum with a rolling window maximum (`rolling(W).max()`).

---

## 4. Causal Boundary Violation (Lookahead Leak) in Wick Prominence (`slot_10`)
*   **File References**: [structural_engine.py:L583](file:///g:/KRONOS%20HYBRID/structural_engine.py#L583)
*   **Severity**: **Critical**
*   **Implementation**:
    ```python
    score = (wick_ratio * exhaustion_flag).clip(upper=wick_ratio.quantile(cfg["structural_engine"]["quantile_threshold"]))
    ```

### Detailed Conflict
The function calls `wick_ratio.quantile(cfg["structural_engine"]["quantile_threshold"])` on the raw series. In python, this calculates the specified percentile across the **entire Series** passed to the function (which, during a full historical run, corresponds to the entire Genesis to present dataset). This leaks future price distribution metrics into the calculation of the current bar $t$, violating the causal boundary constraint (`max_lookahead_bars == cfg["causal_boundary"]["max_lookahead_bars"]`).

### Solution
Calculate the percentile dynamically over a rolling lookback window (`rolling(W).quantile(cfg["structural_engine"]["quantile_threshold"])`) or use a fixed configuration parameter.

---

## 5. Mathematically Invalid Annualised Sharpe Ratio
*   **File References**: [backtest_engine.py:L79-L88](file:///g:/KRONOS%20HYBRID/backtest_engine.py#L79-L88)
*   **Severity**: High
*   **Implementation**:
    ```python
    returns = (test_slice["mfe"].values - test_slice["mae"].values).astype(float)
    ...
    fold_sharpe = (mean_r / (std_r + epsilon)) * float(np.sqrt(annualisation_factor))
    ```

### Detailed Conflict
The Sharpe Ratio is calculated directly on individual signature returns (`returns = mfe - mae`). Because signatures represent sparse, irregularly spaced trade entry signals at `cfg["feature_builder"]["interval"]` resolution, trade-level returns do not represent periodic returns. 
Multiplying a trade-level Sharpe Ratio by the square root of a daily calendar factor (`annualisation_factor: cfg["backtest"]["annualisation_factor"]`) is mathematically incorrect. It assumes a constant trade frequency. If a strategy trades multiple times per day across the `cfg["universe"]["size"]` altcoins, the annualised Sharpe is deflated; if it trades sparsely, it is inflated.

### Solution
Reconstruct a daily continuous PnL series from the signature timestamps and durations, and calculate the Sharpe Ratio on the resulting daily return series.

---

## 6. Dead Volatility Gate Reference Window (Bypassed Flaw 13 Fix)
*   **File References**: [neural_integration_engine.py:L192-L193](file:///g:/KRONOS%20HYBRID/neural_integration_engine.py#L192-L193), [neural_integration_engine.py:L372-L380](file:///g:/KRONOS%20HYBRID/neural_integration_engine.py#L372-L380)
*   **Severity**: High
*   **Implementation**:
    ```python
    start = max(zero_i, current_idx + one_i - context_length)
    window_df = causal_candles.iloc[start: current_idx + one_i]
    ...
    global_ref_bars = kronos_cfg.get("global_vol_ref_bars", cfg["neural_engine"]["global_vol_ref_bars"])
    if len(window_df) >= global_ref_bars:
        # Long-term global reference std...
    else:
        # Fall back to local std of window_df...
    ```

### Detailed Conflict
The "Flaw 13 Fix" was designed to anchor the neural pooling volatility gate using a long-term reference window (`global_vol_ref_bars = cfg["neural_engine"]["global_vol_ref_bars"]`). However, because the input `window_df` is pre-sliced to the transformer's maximum context length (`context_length = cfg["neural_engine"]["context_length"]`), `len(window_df)` can never exceed `cfg["neural_engine"]["context_length"]`. 
Consequently, the `if` condition is always `False`, making the global reference window logic dead code. The engine is forced to fall back to the `else` block, which computes standard deviation on local context window returns. This subjects the pooling gate to the exact local micro-structure distortions the fix was intended to eliminate.

### Solution
Pass the full historical price series directly to the volatility computation helper instead of slicing the dataframe to the transformer's `context_length` beforehand.

---

## 7. Temporal Lag in Dynamic Conviction Thresholding
*   **File References**: [neural_integration_engine.py:L276-L300](file:///g:/KRONOS%20HYBRID/neural_integration_engine.py#L276-L300)
*   **Severity**: High

### Detailed Conflict
The dynamic threshold is computed using `np.median(recent_convictions)` over the last `cfg["neural_integration"]["conviction_buffer"]` signatures. Because signature signals are triggered sparsely at `cfg["feature_builder"]["interval"]` resolution, a count-based buffer can span weeks of real-time trading. 
During a sudden volatility regime shift across the `cfg["universe"]["size"]` universe, the buffer will retain high conviction scores from the previous regime for days. This keeps the threshold artificially high, starving the pipeline of signatures. Conversely, a transition from low-vol to high-vol will leave the threshold too low, letting in low-conviction noise.

### Solution
Shift from a count-based rolling buffer to a time-based rolling window (e.g., last `cfg["neural_integration"]["time_window_days"]` calendar days), or scale the threshold directly by a rolling volatility index.

---

## 8. Information-Free Synthetic Trades Volume Splits
*   **File References**: [data_engine.py:L182-L201](file:///g:/KRONOS%20HYBRID/data_engine.py#L182-L201)
*   **Severity**: **Critical**

### Detailed Conflict
Synthetic buy/sell volume splits are generated using the SHA-256 hash of a bar's timestamp. This generates a random, uniform distribution in $[\text{cfg["constants"]["zero_f"]}, \text{cfg["constants"]["one_f"]})$.
While deterministic and reproducible, this volume split has zero correlation with price movements or order-book pressure. As a result, microstructural metrics calculated from these synthetic volumes (like VPIN or Liquidity Vacuum) contain no empirical price-discovery information. They act as pure statistical noise, conflicting with the underlying physical models of slots 0, 1, 7, 9, and 12.

### Solution
Model the synthetic volume split as a function of price returns and volume spreads (e.g., using a Lee-Ready or bulk volume classification algorithm) instead of pure pseudo-random timestamp hashing.

---

## 9. `slot_25` (MFE Projection) is a Tautological Copy of `slot_15`
*   **File References**: [feature_builder_engine.py:L217-L218](file:///g:/KRONOS%20HYBRID/feature_builder_engine.py#L217-L218), [params_yaml.txt:L65](file:///g:/KRONOS%20HYBRID/params_yaml.txt#L65)
*   **Severity**: High

### Detailed Conflict
The configuration in `params_yaml.txt` declares `mfe_projection: {samples: cfg["feature_builder"]["mfe_samples"], horizon_bars: cfg["feature_builder"]["horizon_bars"]}`, implying a forward Monte Carlo price excursion projection over the `cfg["feature_builder"]["interval"]` timeframe. The implementation, however, stores the `veto_score` (from `slot_15`) directly. As a result, `slot_25` is a redundant copy of `slot_15`, showing a $+\text{cfg["constants"]["one_f"]}$ correlation. During distance calculations in HDBSCAN clustering, this redundant feature biases distances towards structural anomaly indicators.

### Solution
Implement a proper forward volatility-scaled excursion projection using the `horizon_bars` and `samples` parameters, or deprecate the slot.

---

## 10. `slot_26` (Neural Regime) stores Conviction Norm instead of Regime State
*   **File References**: [feature_builder_engine.py:L221-L222](file:///g:/KRONOS%20HYBRID/feature_builder_engine.py#L221-L222), [params_yaml.txt:L66](file:///g:/KRONOS%20HYBRID/params_yaml.txt#L66)
*   **Severity**: High

### Detailed Conflict
The configuration defines `neural_regime: {latent_states: cfg["feature_builder"]["latent_states"]}`, representing a discrete regime classifier with multiple states. However, the code stores `neural_conviction` (the $L_2$ norm of the embedding vector). Instead of mapping to an ordinal regime index, `slot_26` duplicates the continuous, unbounded conviction metric.

### Solution
Perform a classification mapping to return a state index in $\{0, 1, \ldots, \text{cfg["feature_builder"]["latent_states"]} - 1\}$ (normalised to $[\text{cfg["constants"]["zero_f"]}, \text{cfg["constants"]["one_f"]}]$), or use posterior probabilities from the model.

---

## 11. `slot_29` (Timestamp Hash) Overflows Float16 Precision Limits
*   **File References**: [feature_builder_engine.py:L260-L261](file:///g:/KRONOS%20HYBRID/feature_builder_engine.py#L260-L261), [params_yaml.txt:L11](file:///g:/KRONOS%20HYBRID/params_yaml.txt#L11)
*   **Severity**: **Critical**

### Detailed Conflict
The timestamp hash is derived from the first `cfg["feature_builder"]["hash_chars"]` hex characters of SHA-256, yielding an integer up to $\text{cfg["feature_builder"]["hash_max_int"]}$. When the pipeline casts features to `precision: "float16"`, this value exceeds the float16 maximum limit of $\text{cfg["precision"]["float16_max"]}$, causing it to saturate to `inf` or clamp. This destroys the uniqueness property of the hash. Furthermore, because of its large magnitude, it dominates Euclidean distances in downstream HDBSCAN clustering across the `cfg["universe"]["size"]` coins.

### Solution
Normalise the hash by dividing by the maximum hex integer ($\text{cfg["feature_builder"]["hash_max_int"]}$), mapping it to $[\text{cfg["constants"]["zero_f"]}, \text{cfg["constants"]["one_f"]})$, or exclude `slot_29` from clustering features.

---

## 12. YAML Key Collision in `params_yaml.txt`
*   **File References**: [params_yaml.txt:L146-L155](file:///g:/KRONOS%20HYBRID/params_yaml.txt#L146-L155)
*   **Severity**: Medium

### Detailed Conflict
The key `one_day_int: cfg["constants"]["one_day_int"]` is defined twice within the reproducibility constants block (lines 146 and 155). YAML parsers silently overwrite the first key with the second. While both keys currently share the same value, duplicate keys introduce configuration vulnerabilities if modified independently on Cloud Mining deployments.

### Solution
Remove the duplicate key definition from the config file.

---

## 13. Cold-Start Buffers Cause Neural Gate Warm-Up Leaks
*   **File References**: [feature_builder_engine.py:L142-L152](file:///g:/KRONOS%20HYBRID/feature_builder_engine.py#L142-L152), [neural_integration_engine.py:L276-L299](file:///g:/KRONOS%20HYBRID/neural_integration_engine.py#L276-L299)
*   **Severity**: High

### Detailed Conflict
The conviction history buffer is initialized with `cfg["neural_integration"]["conviction_buffer"]` zeros. Since the dynamic neural threshold is calculated as the rolling median of this buffer times a multiplier, the threshold remains `cfg["constants"]["zero_f"]` for the first ~`cfg["neural_integration"]["warmup_signatures"]` signatures. As a result, every signature candidate that passes the structural veto during this warm-up period is unconditionally accepted by the neural gate, letting noisy signals leak into the database at the start of the full historical processing run.

### Solution
Initialize the conviction buffer by pre-warming over the initial warmup window across the Genesis data, or establish a non-zero minimum floor for the neural gate.

---

## 14. Long-Only MFE/MAE Bias Discards Bearish Reversal Signatures
*   **File References**: [miner_engine.py:L207-L217](file:///g:/KRONOS%20HYBRID/miner_engine.py#L207-L217)
*   **Severity**: **Critical**

### Detailed Conflict
The forward excursion metrics calculate Maximum Favorable Excursion (MFE) strictly above entry and Maximum Adverse Excursion (MAE) strictly below entry:
$$\text{MFE} = \frac{P_{\max} - P_{\text{entry}}}{P_{\text{entry}}}, \quad \text{MAE} = \frac{P_{\text{entry}} - P_{\min}}{P_{\text{entry}}}$$
This formulation is valid only for long signals. When the structural engine detects bearish reversals across the `cfg["universe"]["size"]` perpetual altcoins (e.g. negative `slot_0` absorption or negative `slot_12` deviation), the correct short predictions are marked as failures (low MFE, high MAE) and discarded. The archive is thus biased towards long-only signatures.

### Solution
Implement directional checks using the signs of the input slots to swap the MFE and MAE calculations for bearish signals.

---

## 15. Unbounded Recovery Factor Corrupts Statistics and Distances
*   **File References**: [miner_engine.py:L213-L217](file:///g:/KRONOS%20HYBRID/miner_engine.py#L213-L217)
*   **Severity**: High

### Detailed Conflict
The recovery factor is computed as:
$$\text{recovery} = \frac{\text{MFE}}{\text{MAE} + \text{cfg["constants"]["epsilon"]}}$$
When a signature is followed by a strong, clean upward trend, $\text{MAE}$ is close to zero. The division by $\text{cfg["constants"]["epsilon"]}$ yields extremely large recovery values. This skews the median recovery metrics in the validation engine and dominates the distance metrics during clustering.

### Solution
Clip the recovery factor at a high sentinel value (e.g., `cfg["miner_engine"]["max_recovery_clip"]`), or use log-ratios.

---

## 16. Log-Return vs. Arithmetic Return Mismatch in Volume-Price Divergence (`slot_7`)
*   **File References**: [structural_engine.py:L409-L421](file:///g:/KRONOS%20HYBRID/structural_engine.py#L409-L421)
*   **Severity**: High

### Detailed Conflict
`slot_7` compares price acceleration in log return space ($r_{\log} = \ln(P_t/P_{t-k})$) against volume changes computed as arithmetic percentage changes ($r_{\%} = (V_t - V_{t-k})/V_{t-k}$). The subtraction of these two mismatched scales is dominated entirely by volume swings at the `cfg["feature_builder"]["interval"]` interval, rendering the price signal ineffectual.

### Solution
Calculate both price acceleration and volume change in log-return space to maintain scaling consistency.

---

## 17. HMM categorical labels treated as Cardinal Intensities in `slot_8`
*   **File References**: [structural_engine.py:L517-L518](file:///g:/KRONOS%20HYBRID/structural_engine.py#L517-L518)
*   **Severity**: High

### Detailed Conflict
The rolling HMM state index is divided by `max_label` to normalize it to $[\text{cfg["constants"]["zero_f"]}, \text{cfg["constants"]["one_f"]}]$. This converts a categorical state identifier (e.g. regime 3 vs. regime 1) into a continuous intensity. When summed in `slot_15`, this introduces a systematic bias where high-volatility regimes artificially inflate the composite veto score relative to low-volatility regimes.

### Solution
Use one-hot encoded slot channels for each HMM state, or normalize using regime posterior probabilities.

---

## 18. Epsilon Division Guard on Constant Denominator in `slot_31`
*   **File References**: [feature_builder_engine.py:L269-L271](file:///g:/KRONOS%20HYBRID/feature_builder_engine.py#L269-L271)
*   **Severity**: Low

### Detailed Conflict
The denominator is hardcoded as `cfg["constants"]["two_int"] + cfg["constants"]["epsilon"]`. Adding epsilon to a non-zero compile-time constant is mathematically redundant, reflecting an unnecessary application of the division-by-zero protection pattern.

### Solution
Simplify the division to use a clean integer divisor of `cfg["constants"]["two_int"]`.
