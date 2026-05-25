"""Integration test: ablation gate, BIC throttle, ACF spans, IQR vol, sovereign_rationale, audit JSON."""
import sys, os
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
os.chdir(ROOT)  # ensure relative paths (data/audit/) resolve correctly

import json
import numpy as np
import pandas as pd
from pathlib import Path

from load_sovereign_config import load_sovereign_config
from sovereign_prior_derivation_engine import derive_sovereign_priors, patch_config_with_priors
from run_sharded_pipeline import _persist_sovereign_audit

# ── TEST 1: Ablation gate ────────────────────────────────────────────────────
config_disabled = load_sovereign_config("params_yaml.txt")
config_disabled["sovereign_derivation"] = {"enabled": False}
dummy_df = pd.DataFrame({"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [1.0]})
priors_disabled = derive_sovereign_priors(dummy_df, config_disabled)
audit_dis = priors_disabled.get("_audit", {})
assert audit_dis.get("_disabled") is True, "Ablation gate FAILED: _disabled not True"
print("[OK] Ablation gate: engine correctly bypassed when enabled=false.")

# ── TEST 2: BIC throttle cache ───────────────────────────────────────────────
np.random.seed(42)
n = 400
prices = 2000.0 * np.exp(np.cumsum(np.random.normal(0, 0.001, n)))
df = pd.DataFrame({
    "open": prices, "high": prices * 1.001, "low": prices * 0.999,
    "close": prices, "volume": np.random.exponential(1000, n),
    "datetime": pd.date_range("2023-01-01", periods=n, freq="5min", tz="UTC"),
})

config_fresh = load_sovereign_config("params_yaml.txt")
p1 = derive_sovereign_priors(df, config_fresh)
p2 = derive_sovereign_priors(df, config_fresh)  # should hit cache (same n_bars)
a1_method = p1["_audit"]["_prior_derivations"].get("slot_8_num_regimes", {}).get("method", "?")
a2_method = p2["_audit"]["_prior_derivations"].get("slot_8_num_regimes", {}).get("method", "?")
print(f"[OK] BIC throttle: 1st call={a1_method!r}, 2nd call={a2_method!r}")
assert "cache" in a2_method or "fallback" in a2_method, f"BIC cache not hit on 2nd call: {a2_method}"

# ── TEST 3: ACF EMA spans (not Fibonacci) ───────────────────────────────────
spans_entry = p1["_audit"]["_prior_derivations"].get("slot_6_ema_ribbon_spans", {})
spans_method = spans_entry.get("method", "")
print(f"[OK] EMA spans method: {spans_method!r}")
assert "fibonacci" not in spans_method, f"Fibonacci heuristic still active: {spans_method}"

# ── TEST 4: IQR vol threshold (no magic 1.5x baseline) ──────────────────────
vol_entry = p1["_audit"]["_prior_derivations"].get("kronos_vol_threshold_percentile", {})
vol_method = vol_entry.get("method", "")
print(f"[OK] Vol threshold method: {vol_method!r}")
assert "iqr" in vol_method or "fallback" in vol_method, f"IQR method not applied: {vol_method}"

# ── TEST 5: sovereign_rationale on all config-only priors ───────────────────
sov_priors_to_check = [
    "slot_8_hmm_n_iter",
    "hdbscan_min_cluster_size",
    "hdbscan_min_samples",
    "backtest_fold_window_days",
    "backtest_fold_step_days",
    "backtest_min_fold_bars",
    "gate_conviction_multiplier",
    "gate_conviction_time_window_days",
    "kronos_global_vol_ref_bars",
]
for key in sov_priors_to_check:
    entry = p1["_audit"]["_prior_derivations"].get(key, {})
    assert "sovereign_rationale" in entry, f"Missing sovereign_rationale on: {key}"
print(f"[OK] sovereign_rationale present on all {len(sov_priors_to_check)} config-only priors.")

# ── TEST 6: Audit JSON write and round-trip ─────────────────────────────────
sd_cfg = {"audit_path": "data/audit/test_sovereign", "store_audit": True}
_persist_sovereign_audit(p1, "ETHUSDT", "2023-01-01 00:00:00", "2023-02-01 00:00:00", sd_cfg)
audit_files = list(Path("data/audit/test_sovereign").glob("*.json"))
assert len(audit_files) >= 1, "Audit JSON not written"
with open(audit_files[0], encoding="utf-8") as fh:
    loaded = json.load(fh)
assert "_audit" in loaded, "Audit JSON missing _audit block"
assert loaded["_audit"].get("_disabled") is False, "Audit JSON _disabled should be False"
print(f"[OK] Audit JSON written and validated: {audit_files[0].name}")

# ── TEST 7: patch_config_with_priors round-trip ──────────────────────────────
config_patch = load_sovereign_config("params_yaml.txt")
priors_for_patch = derive_sovereign_priors(df, config_patch)
priors_for_patch.pop("_audit", None)
patched = patch_config_with_priors(config_patch, priors_for_patch)
# Verify a derived prior is actually reflected in patched config
dc_val = p1["slot_8_lookback_bars"]
assert patched["feature_builder"]["structural"]["slot_8"]["lookback_bars"] == dc_val, "patch_config round-trip failed"
print(f"[OK] patch_config_with_priors: slot_8 lookback_bars correctly set to {dc_val}.")

print()
print("=" * 50)
print("ALL 7 INTEGRATION TESTS PASSED. Engine v2: READY.")
print("=" * 50)
