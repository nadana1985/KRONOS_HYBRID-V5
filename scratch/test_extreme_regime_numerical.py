import sys
from pathlib import Path

import numpy as np
import pandas as pd

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from load_sovereign_config import load_sovereign_config
from structural_engine import compute_slots_sovereign, compute_veto_composite
from neural_integration_engine import dynamic_threshold


def _build_synthetic_regime_shard(cfg: dict, bars: int = 2880) -> tuple[pd.DataFrame, pd.DataFrame]:
    const = cfg["reproducibility"]["constants"]
    seed = cfg["reproducibility"]["random_seed"]
    epsilon = const["epsilon"]
    zero_f = const["zero_float"]
    baseline_vol = const["vol_baseline_default"]
    high_vol = baseline_vol * const["ten_int"]

    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=bars, freq=cfg["feature_builder"]["interval"])

    seg = bars // 3
    flat_returns = rng.normal(loc=zero_f, scale=epsilon, size=seg)
    shock_returns = rng.normal(loc=zero_f, scale=high_vol, size=seg)
    normal_returns = rng.normal(loc=zero_f, scale=baseline_vol, size=bars - (seg * 2))
    log_ret = np.concatenate([flat_returns, shock_returns, normal_returns])

    close = 1000.0 * np.exp(np.cumsum(log_ret))
    open_ = np.r_[close[0], close[:-1]]
    body_noise = rng.normal(zero_f, baseline_vol, size=bars)
    close = close * (1.0 + body_noise.clip(-0.01, 0.01))

    spread = np.abs(rng.normal(loc=baseline_vol, scale=baseline_vol, size=bars))
    high = np.maximum(open_, close) * (1.0 + spread)
    low = np.minimum(open_, close) * (1.0 - spread)
    volume = np.abs(rng.normal(loc=500.0, scale=120.0, size=bars)).clip(min=1.0)

    df = pd.DataFrame(
        {
            "timestamp": idx,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=idx,
    )

    buy_frac = rng.uniform(0.35, 0.65, size=bars)
    buy_vol = (volume * buy_frac).clip(min=epsilon)
    sell_vol = (volume - buy_vol).clip(min=epsilon)
    agg = pd.DataFrame({"buy_vol": buy_vol, "sell_vol": sell_vol}, index=idx)
    return df, agg


def run_extreme_regime_audit() -> None:
    cfg = load_sovereign_config(str(root_dir / "params_yaml.txt"))
    structural_cfg = cfg["feature_builder"]["structural"]
    const = cfg["reproducibility"]["constants"]
    gate_cfg = cfg["feature_builder"]["gate"]

    df, agg = _build_synthetic_regime_shard(cfg)
    structural_df = compute_slots_sovereign(df, agg, structural_cfg, cfg)
    slot_15 = compute_veto_composite(structural_df, structural_cfg["slot_15"], const)

    finite_ok = np.isfinite(structural_df.to_numpy(dtype=float)).all() and np.isfinite(slot_15.to_numpy(dtype=float)).all()
    assert finite_ok, "Non-finite values detected in structural outputs or slot_15."

    buy_zero_ratio = float((agg["buy_vol"] <= const["epsilon"]).mean())
    sell_zero_ratio = float((agg["sell_vol"] <= const["epsilon"]).mean())
    assert buy_zero_ratio < 0.05 and sell_zero_ratio < 0.05, "buy_vol/sell_vol collapsed toward mass zero."

    veto_threshold = structural_cfg["veto_threshold"]
    veto_pass_rate = float((slot_15 >= veto_threshold).mean())
    assert 0.05 <= veto_pass_rate <= 0.95, "slot_15 veto scores are unstable/collapsed."

    recent_convictions = []
    neural_passes = []
    roll_vol = np.log((df["close"] + const["epsilon"]) / (df["close"].shift(1).fillna(df["close"]) + const["epsilon"])).rolling(24, min_periods=1).std().fillna(const["zero_float"])
    for i in range(len(slot_15)):
        conv = float(slot_15.iloc[i])
        recent_convictions.append(conv)
        threshold = dynamic_threshold(
            pd.Series(recent_convictions[-gate_cfg["recent_conviction_window"]:]),
            {"feature_builder": {"gate": gate_cfg}, "reproducibility": {"constants": const}},
            current_vol=float(roll_vol.iloc[i]),
        )
        neural_passes.append(conv > threshold)

    neural_pass_rate = float(np.mean(neural_passes))
    assert 0.02 <= neural_pass_rate <= 0.08, (
        f"Neural pass rate out of expected 2-8% band: {neural_pass_rate:.4f}"
    )

    print("Extreme regime numerical audit passed.")
    print(f"finite_ok={finite_ok}")
    print(f"buy_zero_ratio={buy_zero_ratio:.4f} sell_zero_ratio={sell_zero_ratio:.4f}")
    print(f"veto_pass_rate={veto_pass_rate:.4f}")
    print(f"neural_pass_rate={neural_pass_rate:.4f}")


if __name__ == "__main__":
    run_extreme_regime_audit()
