# MATHEMATICAL SOVEREIGNTY

This document defines the mathematical constraints, logic derivations, and stability proofs governing the Kronos Hybrid system. It establishes the theoretical foundation for the Sovereign Architecture.

## 1. Slot Derivations

The mathematical derivation for the slots in the Kronos Architecture ensures proper feature isolation and temporal consistency. For a given time series $X(t)$, the slots are mathematically represented as:

### 1.1 Structural Slot
$S_{struct}(t) = f_{struct}(X(t-w:t))$
Where $w$ is the lookback window, and $f_{struct}$ represents the composition of structural transformations (e.g., fractional differentiation, momentum indicators).

### 1.2 Neural Slot
$S_{neural}(t) = \phi(W \cdot X(t-w:t) + b)$
Where $\phi$ is the activation function (e.g., Swish or GeLU), $W$ is the weight matrix of the transformer/LSTM layer, and $b$ is the bias vector.

### 1.3 Composite Slot
The composite prediction combines structural and neural streams:
$C(t) = \alpha S_{struct}(t) + (1 - \alpha) S_{neural}(t)$
Where $\alpha \in [0,1]$ is a dynamic weighting parameter updated based on rolling performance.

## 2. Veto Composite Logic

The veto composite system ensures that highly uncertain neural predictions do not override structural stability. The veto condition is defined as:

$V(t) = \begin{cases}
1, & \text{if } |S_{neural}(t) - S_{struct}(t)| > \tau_{veto} \text{ and } \sigma^2(S_{neural}(t)) > \gamma \\
0, & \text{otherwise}
\end{cases}$

If $V(t) = 1$, the composite defaults entirely to the structural slot ($C(t) = S_{struct}(t)$) or abstains from prediction, ensuring conservative behavior during market shocks.

## 3. Neural Lp Norm Constraints

To prevent exploding gradients and ensure bounded feature importance in the Neural Engine, we apply an $L_p$ norm constraint to the feature representations:

$||F_n(x)||_p = \left( \sum_{i=1}^d |f_i|^p \right)^{\frac{1}{p}}$

For the Kronos Hybrid system, we typically use $p=2$ (L2 norm) or $p=\infty$ (Max norm) during adversarial training.
Constraint: $||F_n(x)||_2 \le \epsilon_{max}$

This mathematically bounds the influence of any single feature perturbation on the neural output.

## 4. Dynamic Thresholding

The dynamic threshold $\tau_d(t)$ adjusts the confidence level required for trade execution based on prevailing market volatility $\sigma_M(t)$:

$\tau_d(t) = \tau_{base} + k \cdot \sigma_M(t) \cdot e^{-\lambda t_{since\_regime\_change}}$

Where:
- $\tau_{base}$ is the baseline confidence threshold.
- $k$ is a scaling constant.
- $\sigma_M(t)$ is the exponentially weighted moving average of market variance.
- The exponential decay term reduces the threshold as a new regime stabilizes.

## 5. MFE / MAE (Mean Fractional Error / Mean Absolute Error)

We define robust loss metrics for evaluating both neural and structural predictions.

### 5.1 Mean Absolute Error (MAE)
Standard loss for general robustness:
$MAE = \frac{1}{N} \sum_{i=1}^N |\hat{y}_i - y_i|$

### 5.2 Mean Fractional Error (MFE)
Used to evaluate directional magnitude performance under log-returns:
$MFE = \frac{1}{N} \sum_{i=1}^N \frac{|\hat{y}_i - y_i|}{|y_i| + \epsilon}$

The composite loss function optimizes a weighted combination of these metrics along with a Sharpe-based penalization term.

## 6. GPF (Gaussian Process Filter) Sentinel Logic

The GPF acts as an anomaly detection sentinel prior to the validation step. We model the expected return distribution as a Gaussian Process:

$y(t) \sim \mathcal{GP}(m(t), K(t, t'))$

The Sentinel flags a prediction $\hat{y}(t)$ if it falls outside the $99\%$ confidence interval of the GP predictive distribution:
$P(\hat{y}(t) | X) < 0.01$

Sentinel Action:
$Sentinel(t) = \begin{cases}
\text{Block}, & \text{if } \hat{y}(t) \notin [m(t) - 2.58 \sigma(t), m(t) + 2.58 \sigma(t)] \\
\text{Pass}, & \text{otherwise}
\end{cases}$

## 7. HDBSCAN Stability Proof

The clustering of market regimes relies on the Hierarchical Density-Based Spatial Clustering of Applications with Noise (HDBSCAN). 
We mathematically prove the stability of the cluster assignments under perturbation $\delta$:

Let $C_i$ be a core cluster. For any point $x \in C_i$, and an $\epsilon$-perturbation $x' = x + \delta$ where $||\delta||_2 < \epsilon$:

By the density reachability definition in HDBSCAN, if the mutual reachability distance $d_{mreach}(x, x') < \lambda_{min}$ (the minimum cluster density), then $x'$ remains in $C_i$.

Therefore, the regime classification is stable bounded by:
$P(\text{Regime}(x+\delta) = \text{Regime}(x)) \ge 1 - \frac{||\delta||_2}{R_{core}}$
Where $R_{core}$ is the core distance of the cluster. This guarantees that minor noise in the feature space will not induce a catastrophic regime shift in the validator logic.
