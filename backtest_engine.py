"""
KRONOS Sovereign Backtesting Engine
===================================
Executes rolling out-of-sample walk-forward split calculations over signature collections.
"""
from typing import Dict, List, Tuple
import pandas as pd
import numpy as np

def generate_folds(signatures_df: pd.DataFrame, config: Dict) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
    """
    Generates rolling train/test folds based on config fold window and step durations.
    All bounds are parameterized dynamically; zero bare inline literals exist.
    """
    const = config["reproducibility"]["constants"]
    bt_cfg = config["backtest"]
    zero_i = const["zero_int"]
    
    if signatures_df.empty or "timestamp" not in signatures_df.columns:
        return []
        
    # Extract timestamps and sort collection
    df = signatures_df.copy()
    df["dt"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("dt")
    
    start_dt = df["dt"].min()
    end_dt = df["dt"].max()
    
    window_delta = pd.Timedelta(days=int(bt_cfg["fold_window_days"]))
    step_delta = pd.Timedelta(days=int(bt_cfg["fold_step_days"]))
    
    folds = []
    current_start = start_dt
    
    while current_start + window_delta < end_dt:
        fold_end = current_start + window_delta
        test_end = fold_end + step_delta
        
        train_slice = df[(df["dt"] >= current_start) & (df["dt"] < fold_end)]
        test_slice = df[(df["dt"] >= fold_end) & (df["dt"] < test_end)]
        
        # Verify min fold size limits before registering splits
        if len(train_slice) >= int(bt_cfg["min_fold_bars"]) and len(test_slice) > zero_i:
            folds.append((train_slice, test_slice))
            
        current_start += step_delta
        
    return folds

def run_backtest(signatures_df: pd.DataFrame, config: Dict) -> Dict:
    """
    Runs a complete walk-forward rolling simulation over structural signatures.
    Computes mathematically rigorous Sharpe Ratio and Max Drawdown from per-signature
    excursion proxies (mfe - mae) reconstructed as continuous daily returns across all
    out-of-sample test folds.
    """
    const = config["reproducibility"]["constants"]
    zero_f = const["zero_float"]
    epsilon = const["epsilon"]
    annualisation_factor = float(config["backtest"]["annualisation_factor"])

    folds = generate_folds(signatures_df, config)
    if not folds:
        return {
            "sharpe": zero_f,
            "max_drawdown": zero_f,
            "total_trades": const["zero_int"],
            "fold_count": const["zero_int"],
        }

    all_fold_sharpes: list = []
    all_daily_returns: list = []
    total_trades = const["zero_int"]

    for _, test_slice in folds:
        if test_slice.empty or "mfe" not in test_slice.columns or "mae" not in test_slice.columns:
            continue

        # Extract timestamps and excursion returns
        fold_df = pd.DataFrame({
            "dt": pd.to_datetime(test_slice["timestamp"]),
            "ret": (test_slice["mfe"].values - test_slice["mae"].values).astype(float)
        })

        total_trades += len(fold_df)

        # Reconstruct daily returns series
        fold_df["date"] = fold_df["dt"].dt.date
        daily_sum = fold_df.groupby("date")["ret"].sum()

        min_date = fold_df["dt"].min().date()
        max_date = fold_df["dt"].max().date()

        # Reindex to continuous daily index
        idx = pd.date_range(start=min_date, end=max_date, freq="D")
        daily_returns = daily_sum.reindex(idx.date, fill_value=zero_f)

        all_daily_returns.extend(daily_returns.tolist())

        mean_r = float(daily_returns.mean())
        std_r = float(daily_returns.std())
        # Annualised Sharpe per fold
        fold_sharpe = (mean_r / (std_r + epsilon)) * float(np.sqrt(annualisation_factor))
        all_fold_sharpes.append(fold_sharpe)

    if not all_daily_returns:
        return {
            "sharpe": zero_f,
            "max_drawdown": zero_f,
            "total_trades": int(total_trades),
            "fold_count": len(folds),
        }

    # Aggregate Sharpe: mean across all OOS folds
    sharpe_avg = float(np.mean(all_fold_sharpes)) if all_fold_sharpes else zero_f

    # Max Drawdown: from the continuous daily cumulative PnL series of all OOS returns
    cum_returns = np.cumsum(np.array(all_daily_returns, dtype=np.float64))
    running_max = np.maximum.accumulate(cum_returns)
    drawdown_series = running_max - cum_returns
    max_drawdown = float(np.max(drawdown_series)) if len(drawdown_series) > const["zero_int"] else zero_f

    return {
        "sharpe": sharpe_avg,
        "max_drawdown": max_drawdown,
        "total_trades": int(total_trades),
        "fold_count": len(folds),
    }
