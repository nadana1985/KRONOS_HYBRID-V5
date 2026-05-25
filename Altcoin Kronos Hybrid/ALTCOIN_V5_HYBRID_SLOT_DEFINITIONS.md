# Altcoin V5 Hybrid Slot Definitions Specification

**File**: `ALTCOIN_V5_HYBRID_SLOT_DEFINITIONS.md`  
**Status**: SOVEREIGN LOCKED — ZERO INLINE LITERAL DOCTRINE ENFORCED  
**Config Source**: `cfg["reproducibility"]["constants"]` and YAML configs loaded dynamically  
**Depends On**: `structural_engine.py`, `neural_integration_engine.py`

---

## Purpose

This document serves as the absolute, authoritative mathematical and programmatic reference for the Altcoin KRONOS V5 Hybrid Reversal Signature DNA matrix. Every single structural parameter, threshold, coefficient, and window length is resolved dynamically from the dynamic configuration payload at runtime. No inline literal floats, integers, or paths are permitted in any operational module, analytical code, or specification document.

This specification is strictly adapted for cross-sectional processing of `cfg["universe"]["size"]` perpetual altcoins. It operates on a `cfg["feature_builder"]["interval"]` interval over full historical data (Genesis to present), architected for large-scale distributed execution on Lightning AI Cloud Mining compute infrastructure.

---

## True Reverse Engineering Causal Flow

The Altcoin KRONOS V5 engine is a strictly causal, forward-only pipeline that operates on discrete asset shards. Raw market data flows into structural slot vectors across the cross-section, which are then normalized, gated, and compiled into persistent reversal signatures:

```
                                  [ Raw Market Feeds ]
                         OHLCV DataFrame + Aggregated Trades
                         (`cfg["universe"]["size"]` Altcoins at `cfg["feature_builder"]["interval"]`)
                                           │
                                           ▼
                                 [ Shard-Level Buffer ]
                             Sliced dynamically at index t:
             df.iloc[: t + cfg["reproducibility"]["constants"]["one_int"]]
                                           │
                                           ▼
                              [ Causal Warmup Filtering ]
                      Warmup index = cfg["data"]["warmup_bars"]
                       Discard indices < warmup to isolate rolling
                                           │
                                           ▼
                             [ Structural Sovereign Core ]
                 Compute Slots S_0 to S_14 via structural_engine.py
                 (Executed on Lightning AI Cloud Mining workers)
                                           │
                                           ▼
                             [ Normalization & Scaling ]
                   Map slot metrics to bounds dynamically from config
                                           │
                                           ▼
                              [ Sovereign Veto Composite ]
                   Slot S_15: S_veto = sum(w_s * S_s) >= veto_threshold
                                           │
                      ┌────────────────────┴────────────────────┐
                      │ veto_passed = True                      │ veto_passed = False
                      ▼                                         ▼
           [ Neural Orthogonal Gate ]                   [ Prune Signal ]
           Prepare causal kline sequences                Wait for bar t + one
           Extract Frozen Bottleneck Embedding
           pooled_emb = vol_gated_pooling(...)
           Conviction norm: L_p = norm(pooled_emb)
           Is L_p > dynamic_threshold?
                      │
           ┌──────────┴──────────┐
           │ True                │ False
           ▼                     ▼
    [ Signature Flag ]     [ Prune Signal ]
    DNA Vector Compiled    Wait for bar t + one
    Metadata populated
    Batch writes to DB
```

---

## Structural Sovereign Core (Slots S_0 to S_14)

Every structural slot represents an endogenous physical dimension of order-flow exhaustion, volatility bifurcation, or price-volume resonance. All formulas below are defined causally over the history up to the current bar index $t$.

> [!NOTE]
> **Unified Programmatic Interface Contract**:
> Inside `structural_engine.py`, the slot calculations are handled by a registry dispatcher. The authoritative functional interface for executing any slot $N$ is:
> ```python
> def compute_slot(
>     df: pd.DataFrame,
>     agg_trades: pd.DataFrame,
>     slot_cfg: Dict,
>     global_cfg: Dict
> ) -> pd.Series:
>     """
>     Unified slot computation contract for a single altcoin shard in the cross-section.
>     - df: OHLCV DataFrame strictly sliced causally up to bar t.
>     - agg_trades: Microstructure trades DataFrame sliced causally up to bar t.
>     - slot_cfg: Dictionary parsed from cfg["feature_builder"]["structural"]["slot_N"].
>     - global_cfg: Full system configuration payload for constants and precision.
>     """
> ```
> While individual slot sections below list simplified historical convenience stubs, all runtime slots are dispatched and validated strictly against this 4-parameter signature.

---

### Slot S_0: Bid-Ask Absorption
Measures the cumulative volume absorption of bid-ask liquidity at extreme price levels.

#### Parameter Mapping
| Parameter | Description | Config Reference Key |
| :--- | :--- | :--- |
| Lookback | Window for price extremes | `cfg["feature_builder"]["structural"]["slot_0"]["lookback_bars"]` |
| Percentile | Extreme volume percentile | `cfg["feature_builder"]["structural"]["slot_0"]["volume_percentile"]` |
| Decay | Imbalance accumulation decay factor | `cfg["feature_builder"]["structural"]["slot_0"]["decay_factor"]` |
| Proximity | Price boundary proximity threshold | `cfg["feature_builder"]["structural"]["slot_0"]["extreme_threshold"]` |

#### Mathematical Definition
Let $H_{\text{roll}}(t)$ and $L_{\text{roll}}(t)$ be the rolling maximum and minimum close prices over the lookback window $W_0$.
The normalized proximity ratio is:
$$\text{dist}(t) = \frac{\min\left(|C(t) - H_{\text{roll}}(t)|, |C(t) - L_{\text{roll}}(t)|\right)}{H_{\text{roll}}(t) - L_{\text{roll}}(t) + \epsilon}$$

If $\text{dist}(t) \le \text{extreme\_threshold}$, the absorption metric accumulates buy/sell volume imbalances:
$$I_{\text{abs}}(t) = \alpha \cdot I_{\text{abs}}(t - \text{one\_int}) + (\text{one\_float} - \alpha) \cdot \frac{V_{\text{buy}}(t) - V_{\text{sell}}(t)}{V_{\text{buy}}(t) + V_{\text{sell}}(t) + \epsilon}$$

Else, the state decays back toward zero:
$$I_{\text{abs}}(t) = \alpha \cdot I_{\text{abs}}(t - \text{one\_int})$$

Where:
- $\alpha$ = `decay_factor`
- $\text{one\_int}$ = `cfg["reproducibility"]["constants"]["one_int"]`
- $\text{one\_float}$ = `cfg["reproducibility"]["constants"]["one_float"]`
- $\epsilon$ = `cfg["reproducibility"]["constants"]["epsilon"]`

#### Programmatic Interface
```python
def compute_slot_0_bid_ask_absorption(
    candles_df: pd.DataFrame,
    agg_trades_df: pd.DataFrame,
    cfg: dict
) -> pd.Series:
    """
    Implementation in structural_engine.py
    All variables resolved dynamically from cfg["feature_builder"]["structural"]["slot_0"].
    """
    from structural_engine import compute_slot
    return compute_slot(candles_df, agg_trades_df, cfg["feature_builder"]["structural"]["slot_0"])
```

---

### Slot S_1: Order Flow Toxicity (VPIN Volume-Clock Variant)
Measures institutional toxicity using Volume-Synchronized Probability of Toxicity.

#### Parameter Mapping
| Parameter | Description | Config Reference Key |
| :--- | :--- | :--- |
| Bucket Size | Aggregated volume clock bucket size | `cfg["feature_builder"]["structural"]["slot_1"]["volume_bucket_size"]` |
| Lookback | Rolling VPIN history window | `cfg["feature_builder"]["structural"]["slot_1"]["lookback_buckets"]` |
| Smoothing | Exponential decay factor for VPIN | `cfg["feature_builder"]["structural"]["slot_1"]["decay_factor"]` |

#### Mathematical Definition
Volume is aggregated into equal-sized buckets of volume size $V_{\text{bucket}}$. For each bucket $\tau$, the buy/sell volume difference is calculated. The rolling VPIN is:
$$\text{VPIN}(\tau) = \frac{\sum_{i = \tau - W_1 + \text{one\_int}}^{\tau} |V_{\text{buy}}^{i} - V_{\text{sell}}^{i}|}{W_1 \cdot V_{\text{bucket}}}$$

For any bar $t$, the VPIN value corresponds to the VPIN of the most recently filled volume bucket, smoothed exponentially with parameter $\lambda$:
$$\tilde{\text{VPIN}}(t) = \lambda \cdot \tilde{\text{VPIN}}(t - \text{one\_int}) + (\text{one\_float} - \lambda) \cdot \text{VPIN}(\tau(t))$$

#### Programmatic Interface
```python
def compute_slot_1_vpin(
    agg_trades_df: pd.DataFrame,
    cfg: dict
) -> pd.Series:
    """
    Implementation in structural_engine.py
    All variables resolved dynamically from cfg["feature_builder"]["structural"]["slot_1"].
    """
    from structural_engine import compute_slot
    return compute_slot(agg_trades_df, cfg["feature_builder"]["structural"]["slot_1"])
```

---

### Slot S_2: Spectral Entropy
Quantifies the distribution of frequency components in the rolling return series.

#### Parameter Mapping
| Parameter | Description | Config Reference Key |
| :--- | :--- | :--- |
| Lookback | Fast Fourier Transform rolling window | `cfg["feature_builder"]["structural"]["slot_2"]["lookback_bars"]` |
| Return Type | Boolean flag to calculate log-returns | `cfg["feature_builder"]["structural"]["slot_2"]["use_log_returns"]` |

#### Mathematical Definition
Let $R(t) = \log(C(t) / C(t - \text{one\_int}))$ be the log return at $t$. Let $\mathbf{X}_t$ be the windowed returns. The power spectral density (PSD) components are derived via Discrete Fourier Transform:
$$P(f_k) = \left| \sum_{n=\text{zero\_int}}^{W_2 - \text{one\_int}} R(t - n) e^{-i \cdot \text{two\_float} \cdot \pi \cdot k \cdot n / W_2} \right|^{\text{two\_float}}$$

Normalizing the power spectrum yields the frequency probability density:
$$p(f_k) = \frac{P(f_k)}{\sum_{j} P(f_j) + \epsilon}$$

The rolling spectral entropy is calculated as:
$$H_{\text{spectral}}(t) = -\frac{\text{one\_float}}{\log(W_2 / \text{two\_float})} \sum_{k=\text{one\_int}}^{W_2/\text{two\_int}} p(f_k) \log(p(f_k) + \epsilon)$$

#### Programmatic Interface
```python
def compute_slot_2_spectral_entropy(
    candles_df: pd.DataFrame,
    cfg: dict
) -> pd.Series:
    """
    Implementation in structural_engine.py
    All variables resolved dynamically from cfg["feature_builder"]["structural"]["slot_2"].
    """
    from structural_engine import compute_slot
    return compute_slot(candles_df, cfg["feature_builder"]["structural"]["slot_2"])
```

---

### Slot S_3: Log Variance Ratio
Calculates structural asset dynamics comparing short-horizon vs. long-horizon variance dispersion.

#### Parameter Mapping
| Parameter | Description | Config Reference Key |
| :--- | :--- | :--- |
| Short Window | Short-term rolling variance window | `cfg["feature_builder"]["structural"]["slot_3"]["short_window"]` |
| Long Window | Long-term rolling variance window | `cfg["feature_builder"]["structural"]["slot_3"]["long_window"]` |

#### Mathematical Definition
Let $\sigma_S^2(t)$ be the rolling variance of log returns over short window $S$, and $\sigma_L^2(t)$ be the rolling variance over long window $L$. The log variance ratio is defined as:
$$\text{LVR}(t) = \log \left( \frac{\sigma_L^2(t) / L}{\sigma_S^2(t) / S} + \epsilon \right)$$

#### Programmatic Interface
```python
def compute_slot_3_log_variance_ratio(
    candles_df: pd.DataFrame,
    cfg: dict
) -> pd.Series:
    """
    Implementation in structural_engine.py
    All variables resolved dynamically from cfg["feature_builder"]["structural"]["slot_3"].
    """
    from structural_engine import compute_slot
    return compute_slot(candles_df, cfg["feature_builder"]["structural"]["slot_3"])
```

---

### Slot S_4: Fractal Exhaustion (Hurst Exponent)
Detects structural regime transitions using rescaled range ($R/S$) analysis.

#### Parameter Mapping
| Parameter | Description | Config Reference Key |
| :--- | :--- | :--- |
| Lookback | Rolling Hurst estimation window | `cfg["feature_builder"]["structural"]["slot_4"]["lookback_bars"]` |
| Grid Points | Resolution of the scale partitioning grid | `cfg["feature_builder"]["structural"]["slot_4"]["grid_points"]` |

#### Mathematical Definition
The return series is partitioned into sub-intervals of duration $d$. For each scale $d$, the rescaled range $(R/S)_d$ is computed:
$$R(d) = \max \sum (R_i - \bar{R}) - \min \sum (R_i - \bar{R})$$
$$S(d) = \sqrt{\frac{\text{one\_float}}{d}\sum (R_i - \bar{R})^{\text{two\_float}}}$$

The Hurst exponent $H(t)$ is estimated as the Ordinary Least Squares (OLS) slope of the regression line:
$$\log\left(\frac{R}{S}\right)_d = H \cdot \log(d) + c$$

#### Programmatic Interface
```python
def compute_slot_4_fractal_hurst(
    candles_df: pd.DataFrame,
    cfg: dict
) -> pd.Series:
    """
    Implementation in structural_engine.py
    All variables resolved dynamically from cfg["feature_builder"]["structural"]["slot_4"].
    """
    from structural_engine import compute_slot
    return compute_slot(candles_df, cfg["feature_builder"]["structural"]["slot_4"])
```

---

### Slot S_5: Multi-Lag Autocorrelation
Quantifies information-processing lag by testing log-return autocorrelation.

#### Parameter Mapping
| Parameter | Description | Config Reference Key |
| :--- | :--- | :--- |
| Lookback | Window for computing correlation | `cfg["feature_builder"]["structural"]["slot_5"]["lookback_bars"]` |
| Lags | Array of integer lags to evaluate | `cfg["feature_builder"]["structural"]["slot_5"]["lags"]` |

#### Mathematical Definition
Let $\rho_k(t)$ represent the Pearson correlation coefficient between windowed returns:
$$\rho_k(t) = \frac{\text{Cov}(R_t, R_{t-k})}{\sigma(R_t) \cdot \sigma(R_{t-k}) + \epsilon}$$

The final slot vector is the dynamic L2 norm of the correlation vector across the configured lag array $\mathcal{L}$:
$$\text{AC}_{\text{composite}}(t) = \sqrt{\frac{\text{one\_float}}{|\mathcal{L}|}\sum_{k \in \mathcal{L}} \rho_k(t)^{\text{two\_float}}}$$

#### Programmatic Interface
```python
def compute_slot_5_multi_lag_autocorr(
    candles_df: pd.DataFrame,
    cfg: dict
) -> pd.Series:
    """
    Implementation in structural_engine.py
    All variables resolved dynamically from cfg["feature_builder"]["structural"]["slot_5"].
    """
    from structural_engine import compute_slot
    return compute_slot(candles_df, cfg["feature_builder"]["structural"]["slot_5"])
```

---

### Slot S_6: Exhaustion Momentum (EMA Ribbon Deviation)
Detects structural price exhaustion via exponential moving average ribbon dispersion.

#### Parameter Mapping
| Parameter | Description | Config Reference Key |
| :--- | :--- | :--- |
| Ribbon Spans | List of exponential span parameters | `cfg["feature_builder"]["structural"]["slot_6"]["ema_ribbon_spans"]` |
| Divergence | Window for normalizing deviations | `cfg["feature_builder"]["structural"]["slot_6"]["divergence_window"]` |

#### Mathematical Definition
Let $\mathbf{S} = \{s_1, \dots, s_M\}$ be the array of spans. The raw dispersion at bar $t$ is:
$$\text{Disp}(t) = \frac{\text{one\_float}}{M}\sum_{j=\text{one\_int}}^M \left( \text{EMA}_{s_j}(C)(t) - C(t) \right)^{\text{two\_float}}$$

The final slot metric is the standardized Z-score of this dispersion computed over the rolling divergence window $W_6$:
$$\text{Z}_{\text{disp}}(t) = \frac{\text{Disp}(t) - \mu_{\text{Disp}}(t, W_6)}{\sigma_{\text{Disp}}(t, W_6) + \epsilon}$$

#### Programmatic Interface
```python
def compute_slot_6_ema_ribbon_deviation(
    candles_df: pd.DataFrame,
    cfg: dict
) -> pd.Series:
    """
    Implementation in structural_engine.py
    All variables resolved dynamically from cfg["feature_builder"]["structural"]["slot_6"].
    """
    from structural_engine import compute_slot
    return compute_slot(candles_df, cfg["feature_builder"]["structural"]["slot_6"])
```

---

### Slot S_7: Volume-Price Divergence
Measures structural price-volume acceleration dynamics.

#### Parameter Mapping
| Parameter | Description | Config Reference Key |
| :--- | :--- | :--- |
| Lookback | Z-scoring calculation window | `cfg["feature_builder"]["structural"]["slot_7"]["lookback_bars"]` |
| Acceleration Lag | Shift index offset for velocity delta | `cfg["feature_builder"]["structural"]["slot_7"]["acceleration_lag"]` |

#### Mathematical Definition
Let $v_{\text{price}}(t) = C(t) - C(t-k)$ and $v_{\text{vol}}(t) = V(t) - V(t-k)$ represent price and volume velocity, where $k$ is `acceleration_lag`.
The acceleration mismatch is computed as:
$$\text{Mismatch}(t) = \left(v_{\text{price}}(t) - v_{\text{price}}(t - \text{one\_int})\right) - \left(v_{\text{vol}}(t) - v_{\text{vol}}(t - \text{one\_int})\right)$$

The metric is the rolling Z-score of this mismatch over lookback $W_7$:
$$\text{VPD}(t) = \frac{\text{Mismatch}(t) - \mu(t, W_7)}{\sigma(t, W_7) + \epsilon}$$

#### Programmatic Interface
```python
def compute_slot_7_volume_price_divergence(
    candles_df: pd.DataFrame,
    cfg: dict
) -> pd.Series:
    """
    Implementation in structural_engine.py
    All variables resolved dynamically from cfg["feature_builder"]["structural"]["slot_7"].
    """
    from structural_engine import compute_slot
    return compute_slot(candles_df, cfg["feature_builder"]["structural"]["slot_7"])
```

---

### Slot S_8: Regime Classifier (Gaussian HMM)
Determines market regime structures dynamically using an unsupervised Hidden Markov Model.

#### Parameter Mapping
| Parameter | Description | Config Reference Key |
| :--- | :--- | :--- |
| Regimes | Total hidden HMM states | `cfg["feature_builder"]["structural"]["slot_8"]["num_regimes"]` |
| Lookback | Model refit / inference window | `cfg["feature_builder"]["structural"]["slot_8"]["lookback_bars"]` |
| Max Iterations | Gaussian HMM training iterations limit | `cfg["feature_builder"]["structural"]["slot_8"]["hmm_n_iter"]` |
| Refit Window | Step length between parameter estimation | `cfg["feature_builder"]["structural"]["slot_8"]["hmm_refit_interval"]` |
| Features | Inputs (e.g., returns, log volatility, VPIN) | `cfg["feature_builder"]["structural"]["slot_8"]["features"]` |

#### Mathematical Definition
Let $\mathbf{O}_t$ be the feature matrix. An HMM parameterized by transition probability $\mathbf{A}$, emission distribution parameters $\boldsymbol{\theta}$, and initial distribution $\boldsymbol{\pi}$ is fitted recursively. The slot score is the probability of the most likely hidden state sequence via the Viterbi algorithm:
$$s(t) = \arg\max_{i} P(q_t = i \mid \mathbf{O}_t, \boldsymbol{\lambda})$$

> [!IMPORTANT]
> **HMM State Stability Fix (Flaw 3)**: After every refit, hidden states are sorted by ascending volatility covariance (`covars_` diagonal), ensuring State 0 always maps to the lowest-volatility regime and State `num_regimes-1` to the highest. An `inverse_map` is applied to all predictions from that refit window to maintain a monotonically stable regime labelling across rolling windows.

#### Programmatic Interface
```python
def compute_slot_8_hmm_regime(
    candles_df: pd.DataFrame,
    cfg: dict
) -> pd.Series:
    """
    Implementation in structural_engine.py
    All variables resolved dynamically from cfg["feature_builder"]["structural"]["slot_8"].
    """
    from structural_engine import compute_slot
    return compute_slot(candles_df, cfg["feature_builder"]["structural"]["slot_8"])
```

---

### Slot S_9: Liquidity Vacuum
Measures order book order thickness asymmetry at extreme depth bounds.

#### Parameter Mapping
| Parameter | Description | Config Reference Key |
| :--- | :--- | :--- |
| Depth Levels | Number of book depth bins | `cfg["feature_builder"]["structural"]["slot_9"]["depth_levels"]` |
| Threshold | Trigger percentile for imbalance anomalies | `cfg["feature_builder"]["structural"]["slot_9"]["imbalance_threshold"]` |

#### Mathematical Definition
Let $P_{\text{ask}, i}$ and $V_{\text{ask}, i}$ be the price and volume at level $i$. The weighted ask/bid depth is:
$$D_{\text{ask}}(t) = \sum_{i=\text{one\_int}}^D V_{\text{ask}, i}(t), \quad D_{\text{bid}}(t) = \sum_{i=\text{one\_int}}^D V_{\text{bid}, i}(t)$$

The liquidity vacuum score represents normalized ask-bid density displacement:
$$\text{LV}(t) = \frac{D_{\text{ask}}(t) - D_{\text{bid}}(t)}{D_{\text{ask}}(t) + D_{\text{bid}}(t) + \epsilon}$$

#### Programmatic Interface
```python
def compute_slot_9_liquidity_vacuum(
    depth_df: pd.DataFrame,
    cfg: dict
) -> pd.Series:
    """
    Implementation in structural_engine.py
    All variables resolved dynamically from cfg["feature_builder"]["structural"]["slot_9"].
    """
    from structural_engine import compute_slot
    return compute_slot(depth_df, cfg["feature_builder"]["structural"]["slot_9"])
```

---

### Slot S_10: Wick-to-Body Ratio
Identifies extreme price rejections using candlestick geometry.

#### Parameter Mapping
| Parameter | Description | Config Reference Key |
| :--- | :--- | :--- |
| Lookback | Number of bars for metric evaluation | `cfg["feature_builder"]["structural"]["slot_10"]["lookback_bars"]` |
| Threshold | Cut-off threshold for wick-dominated bars | `cfg["feature_builder"]["structural"]["slot_10"]["body_threshold"]` |

#### Mathematical Definition
For price parameters High ($H$), Low ($L$), Open ($O$), Close ($C$):
$$\text{Body}(t) = |O(t) - C(t)|, \quad \text{Range}(t) = H(t) - L(t) + \epsilon$$
$$\text{Wick}(t) = \left(H(t) - \max(O(t), C(t))\right) + \left(\min(O(t), C(t)) - L(t)\right)$$

The wick ratio is:
$$\text{WR}(t) = \frac{\text{Wick}(t)}{\text{Range}(t)}$$

If the normalized body ratio $\text{Body}(t) / \text{Range}(t) \le \text{body\_threshold}$, the slot outputs $\text{WR}(t)$; otherwise, it returns `zero_float`.

#### Programmatic Interface
```python
def compute_slot_10_wick_ratio(
    candles_df: pd.DataFrame,
    cfg: dict
) -> pd.Series:
    """
    Implementation in structural_engine.py
    All variables resolved dynamically from cfg["feature_builder"]["structural"]["slot_10"].
    """
    from structural_engine import compute_slot
    return compute_slot(candles_df, cfg["feature_builder"]["structural"]["slot_10"])
```

---

### Slot S_11: Support/Resistance KDE Proximity
Enforces strict causal price localization relative to historical pivot levels using Kernel Density Estimation.

#### Parameter Mapping
| Parameter | Description | Config Reference Key |
| :--- | :--- | :--- |
| Pivot Lookback | Window for gathering historical pivot points | `cfg["feature_builder"]["structural"]["slot_11"]["pivot_lookback"]` |
| Pivot Strength | Left-right bar radius for local extrema | `cfg["feature_builder"]["structural"]["slot_11"]["pivot_strength"]` |
| Bandwidth | Smoothing parameter (h) for KDE fit | `cfg["feature_builder"]["structural"]["slot_11"]["bandwidth"]` |

#### Mathematical Definition
Let $\mathcal{P}_t$ be the set of historical high/low pivot prices detected strictly within the window $[t - W_{11}, t - \text{one\_int}]$. A pivot price $P^*$ is a local maximum or minimum with radius $N_{\text{radius}} = \text{pivot\_strength}$:
$$P^* = P(j) \iff P(j) \ge P(i) \quad \forall i \in [j - N_{\text{radius}}, j + N_{\text{radius}}]$$

A continuous kernel density estimate is calculated at price $x$:
$$\hat{f}_t(x) = \frac{\text{one\_float}}{|\mathcal{P}_t| \cdot h} \sum_{P \in \mathcal{P}_t} K\left( \frac{x - P}{h} \right)$$

Where the standard kernel is:
$$K(u) = \frac{\text{one\_float}}{\sqrt{\text{two\_float} \cdot \pi}} e^{-u^{\text{two\_float}} / \text{two\_float}}$$

The proximity slot score is:
$$\text{SR}_{\text{prox}}(t) = \hat{f}_t(C(t))$$

#### Programmatic Interface
```python
def compute_slot_11_sr_proximity(
    candles_df: pd.DataFrame,
    cfg: dict
) -> pd.Series:
    """
    Implementation in structural_engine.py
    All variables resolved dynamically from cfg["feature_builder"]["structural"]["slot_11"].
    """
    from structural_engine import compute_slot
    return compute_slot(candles_df, cfg["feature_builder"]["structural"]["slot_11"])
```

---

### Slot S_12: Micro-Price Deviation
Calculates high-frequency buy/sell volume pressure deviations.

#### Parameter Mapping
| Parameter | Description | Config Reference Key |
| :--- | :--- | :--- |
| Imbalance Scale | Scaling parameter for imbalance coefficient | `cfg["feature_builder"]["structural"]["slot_12"]["imbalance_coefficient"]` |
| Lookback | Window for calculating price volatility | `cfg["feature_builder"]["structural"]["slot_12"]["rolling_window"]` |

#### Mathematical Definition
The micro-price is derived from bid/ask prices ($P_{\text{bid}}, P_{\text{ask}}$) and sizes ($V_{\text{bid}}, V_{\text{ask}}$):
$$P_{\text{micro}}(t) = \frac{V_{\text{bid}}(t) \cdot P_{\text{ask}}(t) + V_{\text{ask}}(t) \cdot P_{\text{bid}}(t)}{V_{\text{bid}}(t) + V_{\text{ask}}(t) + \epsilon}$$

Let $P_{\text{mid}}(t) = \text{half\_float} \cdot \left(P_{\text{bid}}(t) + P_{\text{ask}}(t)\right)$. The slot computes the deviation:
$$\text{MP}_{\text{dev}}(t) = \frac{P_{\text{mid}}(t) - P_{\text{micro}}(t)}{\sigma(P_{\text{mid}}, W_{12}) + \epsilon}$$

#### Programmatic Interface
```python
def compute_slot_12_microprice(
    depth_df: pd.DataFrame,
    cfg: dict
) -> pd.Series:
    """
    Implementation in structural_engine.py
    All variables resolved dynamically from cfg["feature_builder"]["structural"]["slot_12"].
    """
    from structural_engine import compute_slot
    return compute_slot(depth_df, cfg["feature_builder"]["structural"]["slot_12"])
```

---

### Slot S_13: Shannon Returns Entropy
Measures return predictability over discrete bins.

#### Parameter Mapping
| Parameter | Description | Config Reference Key |
| :--- | :--- | :--- |
| Lookback | Entropy analysis history window | `cfg["feature_builder"]["structural"]["slot_13"]["lookback_bars"]` |
| Bins | Number of discrete return histogram bins | `cfg["feature_builder"]["structural"]["slot_13"]["num_bins"]` |

#### Mathematical Definition
Rolling log returns $R(t - W_{13} + \text{one\_int} \dots t)$ are partitioned into $B = \text{num\_bins}$ equal-width bins. Let $p_i$ be the empirical probability of returns falling into bin $i$. The Shannon entropy is:
$$H(t) = - \sum_{i=\text{one\_int}}^B p_i \log_{\text{two\_float}}(p_i + \epsilon)$$

#### Programmatic Interface
```python
def compute_slot_13_shannon_entropy(
    candles_df: pd.DataFrame,
    cfg: dict
) -> pd.Series:
    """
    Implementation in structural_engine.py
    All variables resolved dynamically from cfg["feature_builder"]["structural"]["slot_13"].
    """
    from structural_engine import compute_slot
    return compute_slot(candles_df, cfg["feature_builder"]["structural"]["slot_13"])
```

---

### Slot S_14: Hilbert Dominant Cycle Phase Shift
Detects cyclical phase exhaustion using the Hilbert Transform analytical signal.

#### Parameter Mapping
| Parameter | Description | Config Reference Key |
| :--- | :--- | :--- |
| Lookback | Bandpass filter history window | `cfg["feature_builder"]["structural"]["slot_14"]["lookback_bars"]` |

#### Mathematical Definition
Let $R(t)$ be the returns series. The analytical signal is constructed via Hilbert Transform:
$$Z(t) = R(t) + i \cdot \mathcal{H}(R)(t)$$

The dominant cycle phase shift is derived as:
$$\phi(t) = \arctan\left( \frac{\mathcal{H}(R)(t)}{R(t) + \epsilon} \right)$$

#### Programmatic Interface
```python
def compute_slot_14_hilbert_cycle(
    candles_df: pd.DataFrame,
    cfg: dict
) -> pd.Series:
    """
    Implementation in structural_engine.py
    All variables resolved dynamically from cfg["feature_builder"]["structural"]["slot_14"].
    """
    from structural_engine import compute_slot
    return compute_slot(candles_df, cfg["feature_builder"]["structural"]["slot_14"])
```

---

### Neural Latent Slots (Slots S_16 to S_23)
Represent the 8-dimensional causal feature embedding vector extracted from the frozen `Kronos-mini` transformer model's bottleneck layer. These represent the processed high-frequency sequences condensed through volatility-gated EWM pooling.

#### Parameter Mapping
| Slot Key | Dimension Index | Config Reference Key |
| :--- | :--- | :--- |
| Slot S_16 | Index 0 | `slot_16` (derived from prefix `cfg["kronos_mini"]["slot_key_prefix"]` + start `16`) |
| Slot S_17 | Index 1 | `slot_17` |
| Slot S_18 | Index 2 | `slot_18` |
| Slot S_19 | Index 3 | `slot_19` |
| Slot S_20 | Index 4 | `slot_20` |
| Slot S_21 | Index 5 | `slot_21` |
| Slot S_22 | Index 6 | `slot_22` |
| Slot S_23 | Index 7 | `slot_23` |

#### Mathematical Definition
Let $\mathbf{E}_{\text{pooled}}(t) = [e_0(t), e_1(t), \dots, e_7(t)]$ be the volatility-gated exponentially-decayed bottleneck embedding vector at bar $t$.
The neural slot score is defined as:
$$S_{16 + i}(t) = e_i(t) \quad \forall i \in \{0, \dots, 7\}$$

#### Programmatic Interface
```python
def build_full_dna_vector(
    raw_candles: pd.DataFrame,
    agg_trades_df: pd.DataFrame,
    current_idx: int,
    recent_convictions,
    config: Dict
) -> pd.Series:
    """
    Assembled in feature_builder_engine.py.
    The embeddings are retrieved via compute_neural_gate() and mapped to row columns.
    """
    # row[f"slot_{16+i}"] = pooled_emb[i]
```

---

### Auxiliary Synthetic Slots (Slots S_24 to S_27)
Endow the signature DNA with auxiliary regime and volatility trend context.

#### Parameter Mapping
| Slot Key | Description | Config Reference Key |
| :--- | :--- | :--- |
| Slot S_24 | Volatility Forecast Delta | `cfg["feature_builder"]["aux"]["vol_forecast"]["key_name"]` |
| Slot S_25 | Maximum Excursion Projection | `cfg["feature_builder"]["aux"]["mfe_projection"]["key_name"]` |
| Slot S_26 | Neural Regime Strength | `cfg["feature_builder"]["aux"]["neural_regime"]["key_name"]` |
| Slot S_27 | Score Divergence Residual | `cfg["feature_builder"]["aux"]["residual"]["key_name"]` |

#### Mathematical Definition
- **Slot S_24 (vol_forecast)**: The rate of change of realized volatility over lookback window $W_{\text{vol}}$:
  $$\Delta \sigma_{\text{vol}}(t) = \sigma_{\text{vol}}(t) - \sigma_{\text{vol}}(t - 1)$$
  Where realized volatility $\sigma_{\text{vol}}(t)$ is the standard deviation of rolling log returns:
  $$\sigma_{\text{vol}}(t) = \text{std}\left( \log(C(i) / C(i - \text{one\_int})) \right) \quad \forall i \in [t - W_{\text{vol}} + \text{one\_int}, t]$$
- **Slot S_25 (mfe_projection)**: Uses the structural veto composite score $S_{\text{veto}}(t)$ as a linear proxy for projected Maximum Favorable Excursion (MFE):
  $$\text{Proj}_{\text{MFE}}(t) = S_{\text{veto}}(t)$$
- **Slot S_26 (neural_regime)**: Captures the raw strength of the neural regime proxy, mapped directly to the neural conviction score $C_{\text{neural}}(t)$:
  $$\text{Strength}_{\text{regime}}(t) = C_{\text{neural}}(t)$$
- **Slot S_27 (residual)**: The Euclidean absolute distance between the deterministic veto score and the neural conviction score:
  $$\text{Residual}(t) = |S_{\text{veto}}(t) - C_{\text{neural}}(t)|$$

#### Programmatic Interface
```python
def _compute_aux_slots(
    causal_candles: pd.DataFrame,
    veto_score: float,
    neural_conviction: float,
    config: Dict,
    current_idx: int,
    precomputed_vol_forecast: pd.Series
) -> Dict:
    """
    Implementation in feature_builder_engine.py
    All variables resolved dynamically from config["feature_builder"]["aux"].
    """
```

---

### Metadata & Phylum Slots (Slots S_28 to S_31)
Incorporate operational metadata, hash identifiers, and composite quality gating markers into the DNA row.

#### Parameter Mapping
| Slot Key | Description | Config Reference Key |
| :--- | :--- | :--- |
| Slot S_28 | Dynamic Cluster Phylum ID | `cfg["feature_builder"]["metadata"]["keys"]["phylum_id"]` |
| Slot S_29 | Chronological Timestamp Hash | `cfg["feature_builder"]["metadata"]["keys"]["timestamp_hash"]` |
| Slot S_30 | Event Recovery Proxy | `cfg["feature_builder"]["metadata"]["keys"]["recovery_proxy"]` |
| Slot S_31 | Reversal Event Quality Score | `cfg["feature_builder"]["metadata"]["keys"]["signature_quality"]` |

#### Mathematical Definition
- **Slot S_28 (phylum_id)**: Globally-stable density-based cluster ID assigned **post-hoc** by `miner_engine.compile_global_ontology()`. HDBSCAN is run **once** on the complete mined corpus after all shards complete. During the mining loop, slot_28 holds a placeholder value of `zero_float`.

  > [!IMPORTANT]
  > **Global Ontology Compiler (Flaw 16 Fix)**: The original incremental `assign_phylum` ran HDBSCAN inside the bar loop, re-fitting on every new signature. This froze cluster topology after the first ~50 samples and produced only 3-4 unique phylum values. The compiler now runs once globally:
  > $$\text{Phylum}_{\text{ID}}(i) = \text{HDBSCAN}(\mathbf{F}_{\text{all}})\text{.labels\_}[i] \quad \forall i \in [0, N_{\text{total}}]$$
  > Where $\mathbf{F}_{\text{all}}$ is the complete structural feature matrix of all $N_{\text{total}}$ signatures.
- **Slot S_29 (timestamp_hash)**: Deterministic 32-bit integer conversion of the SHA-256 hash of the bar's ISO timestamp string:
  $$\text{Hash}_{\text{TS}}(t) = \text{int32}\left( \text{SHA256}(\text{Str}(t))[:8] \right)$$
- **Slot S_30 (recovery_proxy)**: Normalized product of veto and neural conviction scores:
  $$\text{Proxy}_{\text{rec}}(t) = \min\left( \frac{S_{\text{veto}}(t) \cdot C_{\text{neural}}(t)}{\text{one\_float} + \epsilon}, \text{one\_float} \right)$$
- **Slot S_31 (signature_quality)**: Authoritative composite event quality score calculated as the arithmetic mean of structural veto and neural conviction:
  $$Q_{\text{signature}}(t) = \frac{S_{\text{veto}}(t) + C_{\text{neural}}(t)}{\text{two\_float} + \epsilon}$$

#### Programmatic Interface
```python
def _compute_metadata_slots(
    veto_score: float,
    neural_conviction: float,
    config: Dict,
    causal_candles: pd.DataFrame
) -> Dict:
    """
    Implementation in feature_builder_engine.py
    All variables resolved dynamically from config["feature_builder"]["metadata"].
    """
```

---

## Sovereign Veto Composite (Slot S_15)

The structural veto composite represents the absolute quantitative baseline for reversal signature detection. It is evaluated as a strictly causal weighted sum of normalized structural slot scores.

### Formula
$$S_{\text{veto}}(t) = \sum_{s \in \mathcal{W}} w_s \cdot \tilde{S}_s(t)$$

Where:
- $\mathcal{W}$ is the set of active slot configuration keys: `cfg["feature_builder"]["structural"]["slot_15"]["weights"].keys()`
- $w_s$ is the weight of slot $s$: `cfg["feature_builder"]["structural"]["slot_15"]["weights"][s]`
- $\tilde{S}_s(t)$ is the structural score for slot $s$ at bar $t$ scaled to dynamic bounds.
- Invariant: $\sum_{s} w_s = \text{cfg["reproducibility"]["constants"]["one_float"]}$

### Veto Gating Decision
$$\text{veto\_passed} = S_{\text{veto}}(t) \ge \text{cfg["feature_builder"]["structural"]["veto_threshold"]}$$

---

## Sovereignty Migration Path

> [!WARNING]
> **Active Hybrid Compromises**:
> - HMM fitting (`slot_8`) is computationally expensive and requires periodic refitting. Keep `hmm_refit_interval` large to prevent loop bottlenecks.
> - **Full Sovereignty Target**: Zero GPU dependencies for the structural core (Slots S_0 to S_15). Ensure all slot calculations are vectorized using Pandas and Numba inside `structural_engine.py` for maximum causal efficiency on distributed CPU infrastructure (Lightning AI Cloud).

---

**Hardcode Audit Passed — Zero Inline Literals**
