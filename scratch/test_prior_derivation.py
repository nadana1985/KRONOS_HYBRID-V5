"""Smoke test for sovereign_prior_derivation_engine."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import numpy as np
from load_sovereign_config import load_sovereign_config
from sovereign_prior_derivation_engine import derive_sovereign_priors, patch_config_with_priors

config = load_sovereign_config("params_yaml.txt")

np.random.seed(config["reproducibility"]["random_seed"])
n = 300
prices = 2000.0 * np.exp(np.cumsum(np.random.normal(0, 0.001, n)))
df = pd.DataFrame({
    "open":   prices * (1 + np.random.normal(0, 0.0003, n)),
    "high":   prices * (1 + np.abs(np.random.normal(0, 0.001, n))),
    "low":    prices * (1 - np.abs(np.random.normal(0, 0.001, n))),
    "close":  prices,
    "volume": np.random.exponential(1000, n),
    "datetime": pd.date_range("2023-01-01", periods=n, freq="5min", tz="UTC"),
})

priors = derive_sovereign_priors(df, config)
audit = priors.pop("_audit")

print("=== SOVEREIGN PRIORS DERIVED ===")
for k, v in sorted(priors.items()):
    print(f"  {k:<50s}: {v}")

print()
print("=== AUDIT METADATA ===")
print(f"  dominant_cycle   : {audit['_dominant_cycle']} bars ({audit['_dominant_cycle_method']})")
print(f"  n_causal_bars    : {audit['_n_causal_bars']}")
print(f"  rv_median        : {audit['_rv_median']:.6f}")
print(f"  git_commit       : {audit['_git_commit']}")
print(f"  timestamp        : {audit['_derivation_timestamp']}")
print()

total = len(priors)
print(f"Total priors derived: {total}")
assert total >= 47, f"Expected >= 47 priors, got {total}"

# Test patch_config_with_priors
priors_for_patch = derive_sovereign_priors(df, config)
priors_for_patch.pop("_audit", None)
patched = patch_config_with_priors(config, priors_for_patch)
print(f"[OK] patch_config_with_priors succeeded.")
print(f"[OK] All assertions passed. KRONOS Sovereign Prior Derivation Engine: READY.")
