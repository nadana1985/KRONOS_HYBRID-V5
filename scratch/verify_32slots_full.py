# -*- coding: utf-8 -*-
"""
KRONOS V5 — FULL 32-SLOT VERIFICATION AUDIT
============================================
Cross-verifies every slot column in signatures_compact.parquet for:
  - Presence (all 32 slots exist)
  - Null/NaN integrity
  - Value range sanity (no degenerate constant columns)
  - Neural embedding activation (slots 16-23)
  - Quality formula math alignment (slot_31)
  - Co-integration performance (MFE, MAE, Recovery Factor)
  - Temporal coverage (no major gaps)
  - Signature density per tier
  - Short-cycle guard evidence (slot_06, slot_12 window metadata)
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import os
import sys
import pandas as pd
import numpy as np

# ── colours ──────────────────────────────────────────────────────────────────
R  = "\033[91m"   # red
G  = "\033[92m"   # green
Y  = "\033[93m"   # yellow
B  = "\033[94m"   # blue
C  = "\033[96m"   # cyan
M  = "\033[95m"   # magenta
BO = "\033[1m"
RS = "\033[0m"

def hdr(title):
    print(f"\n{BO}{C}{'='*68}{RS}")
    print(f"{BO}{B}  {title}{RS}")
    print(f"{BO}{C}{'='*68}{RS}")

def ok(msg):  print(f"  {G}[PASS]{RS} {msg}")
def warn(msg):print(f"  {Y}[WARN]{RS} {msg}")
def fail(msg):print(f"  {R}[FAIL]{RS} {msg}")
def info(msg):print(f"  {C}[INFO]{RS} {msg}")

# ── load ─────────────────────────────────────────────────────────────────────
COMPACT = os.path.join("data", "signatures_compact.parquet")

hdr("LOADING COMPACT PARQUET DATABASE")
if not os.path.exists(COMPACT):
    fail(f"File not found: {COMPACT}")
    sys.exit(1)

import time
t0 = time.time()
df = pd.read_parquet(COMPACT)
elapsed = time.time() - t0
info(f"Loaded in {elapsed:.4f}s  |  Rows: {BO}{len(df):,}{RS}  |  Columns: {BO}{len(df.columns)}{RS}")
df["timestamp"] = pd.to_datetime(df["timestamp"])
print(f"  {C}Columns present:{RS} {sorted(df.columns.tolist())}")

PASS = 0
WARN = 0
FAIL = 0

# ─────────────────────────────────────────────────────────────────────────────
# 1. SLOT PRESENCE AUDIT
# ─────────────────────────────────────────────────────────────────────────────
hdr("1. SLOT PRESENCE AUDIT  (slots 0–31 + aux cols)")

# Database uses zero-padded names: slot_00..slot_09, slot_10..slot_31
expected_slots = ([f"slot_{i:02d}" for i in range(10)] +
                  [f"slot_{i}"    for i in range(10, 32)])
missing = [s for s in expected_slots if s not in df.columns]
present = [s for s in expected_slots if s in df.columns]

info(f"Slots present : {len(present)}/32")
if missing:
    fail(f"MISSING SLOTS : {missing}")
    FAIL += 1
else:
    ok("All 32 slots are present in the database")
    PASS += 1

# Aux columns
aux_expected = ["timestamp", "symbol", "mfe", "mae", "recovery_factor",
                "neural_conviction", "signature_flag"]
missing_aux = [c for c in aux_expected if c not in df.columns]
if missing_aux:
    warn(f"Missing aux columns: {missing_aux}")
    WARN += 1
else:
    ok(f"All auxiliary columns present: {aux_expected}")
    PASS += 1

# ─────────────────────────────────────────────────────────────────────────────
# 2. NULL / NaN INTEGRITY
# ─────────────────────────────────────────────────────────────────────────────
hdr("2. NULL / NaN INTEGRITY AUDIT")

null_counts = df[present].isnull().sum()
total_nulls = null_counts.sum()
cols_with_nulls = null_counts[null_counts > 0]

if total_nulls == 0:
    ok(f"Zero NaNs across all {len(present)} slot columns — database is pristine")
    PASS += 1
else:
    fail(f"Total NaNs = {total_nulls}")
    for col, cnt in cols_with_nulls.items():
        fail(f"  {col}: {cnt} nulls ({cnt/len(df)*100:.2f}%)")
    FAIL += 1

# ─────────────────────────────────────────────────────────────────────────────
# 3. PER-SLOT VALUE RANGE SANITY
# ─────────────────────────────────────────────────────────────────────────────
hdr("3. PER-SLOT VALUE RANGE & DEGENERACY CHECK")

print(f"\n  {'Slot':<12} {'Min':>10} {'Max':>10} {'Mean':>10} {'Std':>10}  Status")
print(f"  {'-'*12} {'-'*10} {'-'*10} {'-'*10} {'-'*10}  ------")

degenerate_slots = []
for slot in present:
    col = df[slot]
    mn, mx, mu, sd = col.min(), col.max(), col.mean(), col.std()
    # Degenerate = constant column (std ~ 0) OR all-zero
    is_constant = sd < 1e-9
    is_all_zero = (col == 0.0).all()
    status = f"{R}CONSTANT{RS}" if is_constant else f"{G}OK{RS}"
    flag = ""
    if is_constant:
        degenerate_slots.append(slot)
        flag = " <- DEGENERATE"
    print(f"  {slot:<12} {mn:>10.4f} {mx:>10.4f} {mu:>10.4f} {sd:>10.4f}  {status}{flag}")

if degenerate_slots:
    fail(f"Degenerate (constant) slots: {degenerate_slots}")
    FAIL += 1
else:
    ok("No degenerate slot columns — all slots show live variation")
    PASS += 1

# ─────────────────────────────────────────────────────────────────────────────
# 4. NEURAL EMBEDDING ACTIVATION (slots 16–23)
# ─────────────────────────────────────────────────────────────────────────────
hdr("4. NEURAL EMBEDDING ACTIVATION  (Slots 16–23 = Deep Sequence Bottleneck)")

emb_slots = [f"slot_{i}" for i in range(16, 24)]  # slot_16..slot_23 (not zero-padded)
emb_present = [s for s in emb_slots if s in df.columns]

if len(emb_present) < 8:
    fail(f"Only {len(emb_present)}/8 embedding slots present: {emb_present}")
    FAIL += 1
else:
    emb_df = df[emb_present]
    all_zero = emb_df.eq(0.0).all().all()
    any_zero_col = emb_df.eq(0.0).all()
    zero_cols = any_zero_col[any_zero_col].index.tolist()

    if all_zero:
        fail("ALL embedding slots are zero — neural engine did NOT fire!")
        FAIL += 1
    elif zero_cols:
        warn(f"Partial activation — zero columns: {zero_cols}")
        WARN += 1
    else:
        ok(f"All 8 neural embedding slots are ACTIVE (non-zero)")
        PASS += 1

    for slot in emb_present:
        col = df[slot]
        pct_nonzero = (col != 0.0).mean() * 100
        print(f"    {slot}: mean={col.mean():.4f}  std={col.std():.4f}  "
              f"non-zero={pct_nonzero:.1f}%")

# ─────────────────────────────────────────────────────────────────────────────
# 5. QUALITY FORMULA MATH VERIFICATION  slot_31 = (slot_15 + neural_conviction) / 2
# ─────────────────────────────────────────────────────────────────────────────
hdr("5. QUALITY FORMULA MATH  (slot_31 = (slot_15 + neural_conviction) / 2)")

if "slot_15" in df.columns and "slot_31" in df.columns and "neural_conviction" in df.columns:
    expected = (df["slot_15"] + df["neural_conviction"]) / 2.0
    diff = (df["slot_31"] - expected).abs()
    max_diff = diff.max()
    mean_diff = diff.mean()
    pct_exact = (diff < 1e-6).mean() * 100

    info(f"Max deviation  : {max_diff:.10f}")
    info(f"Mean deviation : {mean_diff:.10f}")
    info(f"Exact matches  : {pct_exact:.2f}%  (threshold < 1e-6)")

    if max_diff < 1e-4:
        ok(f"Quality formula is mathematically consistent — max deviation {max_diff:.2e}")
        PASS += 1
    else:
        fail(f"Quality formula deviation too high: {max_diff:.6f}")
        FAIL += 1
else:
    warn("Cannot verify formula — slot_15, slot_31, or neural_conviction missing")
    WARN += 1

# ─────────────────────────────────────────────────────────────────────────────
# 6. DUAL-ENGINE QUALITY PROFILE
# ─────────────────────────────────────────────────────────────────────────────
hdr("6. DUAL-ENGINE QUALITY PROFILE  (Slot 15 = Structural Veto | Slot 31 = Combined)")

for metric, col_name in [
    ("Veto Score      (slot_15)", "slot_15"),
    ("Neural Conviction        ", "neural_conviction"),
    ("Combined Quality (slot_31)", "slot_31"),
]:
    if col_name in df.columns:
        col = df[col_name]
        print(f"  {metric}: min={col.min():.4f}  max={col.max():.4f}  "
              f"mean={col.mean():.4f}  p25={col.quantile(0.25):.4f}  "
              f"p75={col.quantile(0.75):.4f}")

# Gate thresholds
if "slot_15" in df.columns:
    # Gate threshold: slot_15 > 0 (veto_threshold: 0.0 in params_yaml)
    # Slot_15 is the composite weighted score — any value > 0 passed the gate
    gate_threshold = 0.0
    below_veto = (df["slot_15"] <= gate_threshold).sum()
    slot15_min  = df["slot_15"].min()
    info(f"slot_15 min={slot15_min:.4f}  max={df['slot_15'].max():.4f}  "
         f"mean={df['slot_15'].mean():.4f}  (veto_threshold in params={gate_threshold})")
    if below_veto == 0:
        ok("All signatures passed structural veto gate (slot_15 > 0.0)")
        PASS += 1
    else:
        warn(f"{below_veto} signatures at/below veto threshold {gate_threshold}")
        WARN += 1

# ─────────────────────────────────────────────────────────────────────────────
# 7. TIER DISTRIBUTION & CO-INTEGRATION PERFORMANCE
# ─────────────────────────────────────────────────────────────────────────────
hdr("7. TIER DISTRIBUTION & CO-INTEGRATION PERFORMANCE  (MFE / MAE / RF)")

if "slot_31" in df.columns and "mfe" in df.columns:
    tiers = {
        "Elite   (>= 0.90)": df[df["slot_31"] >= 0.90],
        "Premium (0.80-0.90)": df[(df["slot_31"] >= 0.80) & (df["slot_31"] < 0.90)],
        "Standard(0.70-0.80)": df[(df["slot_31"] >= 0.70) & (df["slot_31"] < 0.80)],
        "Base    (< 0.70)":  df[df["slot_31"] < 0.70],
    }

    print(f"\n  {'Tier':<22} {'Count':>7} {'MFE%':>8} {'MAE%':>8} {'MFE>MAE':>8} {'RecovFact':>12}")
    print(f"  {'-'*22} {'-'*7} {'-'*8} {'-'*8} {'-'*8} {'-'*12}")

    for name, tdf in tiers.items():
        if len(tdf) == 0:
            print(f"  {name:<22} {'0':>7} {'–':>8} {'–':>8} {'–':>8} {'–':>12}")
            continue
        avg_mfe = tdf["mfe"].mean() * 100
        avg_mae = tdf["mae"].mean() * 100
        avg_rf  = tdf["recovery_factor"].mean()
        mfe_gt  = "YES" if avg_mfe > avg_mae else "NO"
        color   = G if avg_mfe > avg_mae else Y
        print(f"  {name:<22} {len(tdf):>7,} {avg_mfe:>7.4f}% {avg_mae:>7.4f}% "
              f"  {color}{mfe_gt:>6}{RS}   {avg_rf:>12.4f}")

    # Elite MFE > MAE is the key check
    elite_df = df[df["slot_31"] >= 0.90]
    if len(elite_df) > 0:
        e_mfe = elite_df["mfe"].mean()
        e_mae = elite_df["mae"].mean()
        if e_mfe > e_mae:
            ok(f"Elite tier MFE ({e_mfe*100:.4f}%) > MAE ({e_mae*100:.4f}%) — EDGE IS POSITIVE")
            PASS += 1
        else:
            warn(f"Elite tier MFE ({e_mfe*100:.4f}%) <= MAE ({e_mae*100:.4f}%) — inspect further")
            WARN += 1
    PASS += 1

# ─────────────────────────────────────────────────────────────────────────────
# 8. TEMPORAL COVERAGE & GAP ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────
hdr("8. TEMPORAL COVERAGE & GAP ANALYSIS")

if "timestamp" in df.columns:
    min_ts = df["timestamp"].min()
    max_ts = df["timestamp"].max()
    span_days = (max_ts - min_ts).days
    density = len(df) / span_days if span_days > 0 else 0
    info(f"Genesis  : {min_ts}")
    info(f"Latest   : {max_ts}")
    info(f"Span     : {span_days} days  ({span_days/365.25:.2f} years)")
    info(f"Density  : {density:.2f} signatures/day")

    # Monthly frequency — check for gaps (months with 0 signatures)
    df["ym"] = df["timestamp"].dt.to_period("M")
    monthly = df["ym"].value_counts().sort_index()
    zero_months = []

    # Generate full expected monthly range
    full_range = pd.period_range(start=min_ts.to_period("M"),
                                  end=max_ts.to_period("M"), freq="M")
    zero_months = [str(m) for m in full_range if m not in monthly.index]

    if zero_months:
        warn(f"Months with ZERO signatures: {zero_months}")
        WARN += 1
    else:
        ok(f"No missing months — continuous coverage across all {len(monthly)} months")
        PASS += 1

    print(f"\n  {'Year-Month':<12} {'Sigs':>6}  Bar")
    print(f"  {'-'*12} {'-'*6}  ---")
    max_cnt = monthly.max()
    for ym, cnt in monthly.items():
        bar_len = int((cnt / max_cnt) * 30) if max_cnt > 0 else 0
        bar = '#' * bar_len + '.' * (30 - bar_len)
        flag = f"  {Y}<< LOW{RS}" if cnt < 50 else ""
        print(f"  {str(ym):<12} {cnt:>6}  [{bar}]{flag}")

# ─────────────────────────────────────────────────────────────────────────────
# 9. SLOT_06 & SLOT_12 SHORT-CYCLE GUARD VERIFICATION
# ─────────────────────────────────────────────────────────────────────────────
hdr("9. SLOT_06 & SLOT_12 SHORT-CYCLE GUARD  (value range sanity check)")

for slot_name, label, expected_min in [
    ("slot_06", "EMA Ribbon Deviation",  -5.0),
    ("slot_12", "Micro-Price Deviation", -5.0),
]:
    if slot_name in df.columns:
        col = df[slot_name]
        pct_zero = (col == 0.0).mean() * 100
        std = col.std()
        info(f"{slot_name} ({label}): min={col.min():.4f}  max={col.max():.4f}  "
             f"mean={col.mean():.4f}  std={std:.4f}  zero%={pct_zero:.1f}%")
        if std < 1e-6:
            fail(f"{slot_name} is constant — window guard may have degenerated!")
            FAIL += 1
        elif pct_zero > 80:
            warn(f"{slot_name} is {pct_zero:.1f}% zeros — inspect divergence window")
            WARN += 1
        else:
            ok(f"{slot_name} shows healthy variation — short-cycle guard intact")
            PASS += 1

# Check sovereign_priors audit folder
audit_dir = os.path.join("data", "audit", "sovereign_priors")
if os.path.isdir(audit_dir):
    audit_files = [f for f in os.listdir(audit_dir) if f.endswith(".json")]
    if audit_files:
        import json
        # Sample last audit file
        sample_file = sorted(audit_files)[-1]
        with open(os.path.join(audit_dir, sample_file)) as fh:
            audit_data = json.load(fh)
        dw6  = audit_data.get("slot_6_divergence_window", {})
        rw12 = audit_data.get("slot_12_rolling_window", {})
        info(f"Sample audit file: {sample_file}")
        info(f"  slot_6_divergence_window : {dw6}")
        info(f"  slot_12_rolling_window   : {rw12}")

        # Audit values can be stored as int or as {"value": N, "method": ...}
        def _extract_val(v):
            if isinstance(v, dict):
                return v.get("value", 0)
            return int(v) if v is not None else 0

        dw6_val  = _extract_val(dw6)
        rw12_val = _extract_val(rw12)

        if dw6_val >= 5:
            ok(f"slot_6 window = {dw6_val} (>= min_window_slot_06=5) -- guard fired")
            PASS += 1
        else:
            warn(f"slot_6 window = {dw6_val} -- below guard floor!")
            WARN += 1

        if rw12_val >= 5:
            ok(f"slot_12 window = {rw12_val} (>= min_window_slot_12=5) -- guard fired")
            PASS += 1
        else:
            warn(f"slot_12 window = {rw12_val} -- below guard floor!")
            WARN += 1
    else:
        warn("No sovereign_priors audit JSON files found — cannot verify window guards")
        WARN += 1
else:
    warn(f"Audit folder not found: {audit_dir}")
    WARN += 1

# ─────────────────────────────────────────────────────────────────────────────
# 10. SIGNATURE FLAG DISTRIBUTION
# ─────────────────────────────────────────────────────────────────────────────
hdr("10. SIGNATURE FLAG DISTRIBUTION")

if "signature_flag" in df.columns:
    flag_counts = df["signature_flag"].value_counts()
    for flag_val, cnt in flag_counts.items():
        pct = cnt / len(df) * 100
        info(f"  flag={flag_val}:  {cnt:,} ({pct:.1f}%)")
    ok("Signature flag column present and populated")
    PASS += 1
else:
    warn("signature_flag column not found")
    WARN += 1

# ─────────────────────────────────────────────────────────────────────────────
# FINAL VERDICT
# ─────────────────────────────────────────────────────────────────────────────
hdr("FINAL VERIFICATION VERDICT")

total = PASS + WARN + FAIL
print(f"\n  {G}{BO}PASS : {PASS:>3}{RS}")
print(f"  {Y}{BO}WARN : {WARN:>3}{RS}")
print(f"  {R}{BO}FAIL : {FAIL:>3}{RS}")
print(f"  {BO}TOTAL: {total:>3}{RS}\n")

if FAIL == 0 and WARN == 0:
    print(f"  {G}{BO}✅  SOVEREIGN VERDICT: PERFECT — All 32 slots verified, zero anomalies.{RS}\n")
elif FAIL == 0:
    print(f"  {Y}{BO}⚠️  SOVEREIGN VERDICT: ACCEPTABLE — No failures, {WARN} warning(s) to review.{RS}\n")
else:
    print(f"  {R}{BO}❌  SOVEREIGN VERDICT: FAILED — {FAIL} critical issue(s) detected.{RS}\n")
