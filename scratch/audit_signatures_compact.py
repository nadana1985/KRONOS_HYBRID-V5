# -*- coding: utf-8 -*-
"""
KRONOS V5 -- Subordinate Auditor Script
Target: data/signatures_compact.parquet + data/signatures.duckdb
Doctrine: Zero Tolerance. Every violation flagged. No assumptions.
Force UTF-8 output to avoid Windows CP1252 encoding errors.
"""

import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pandas as pd
import numpy as np
import duckdb
import warnings
import os

warnings.filterwarnings("ignore")

PARQUET_PATH = "data/signatures_compact.parquet"
DUCKDB_PATH  = "data/signatures.duckdb"

# -- Reference from params_yaml.txt ------------------------------------------
EXPECTED_SLOTS    = [f"slot_{i:02d}" for i in range(32)]
MIN_GROSS_PROFIT  = 9.5
MIN_RECOVERY      = 12.0
RECOVERY_CAP      = 50.0
MIN_QUALITY       = 0.0
MIN_CLUSTER_SIZE  = 15
VETO_THRESHOLD    = 0.0
MIN_ROW_COUNT     = 10000
VARIANCE_FLOOR    = 0.001
ZERO_PCT_FLOOR    = 0.05
ZERO_PCT_CRITICAL = 0.01

SLOT_15_WEIGHTS = {
    "slot_00": 0.08, "slot_01": 0.08, "slot_02": 0.08, "slot_03": 0.06,
    "slot_04": 0.08, "slot_05": 0.05, "slot_06": 0.08, "slot_07": 0.06,
    "slot_08": 0.10, "slot_09": 0.07, "slot_10": 0.05, "slot_11": 0.08,
    "slot_12": 0.05, "slot_13": 0.04, "slot_14": 0.04,
}

SLOT_BOUNDS = {
    "slot_00": (-1.0,  1.0),
    "slot_03": (-5.0,  5.0),
    "slot_04": ( 0.0,  1.0),
    "slot_07": (-10.0, 10.0),
    "slot_12": (-5.0,  5.0),
    "slot_15": ( 0.0,  1.0),
    "slot_28": (-1.0,  None),
    "slot_30": ( 0.0,  RECOVERY_CAP),
    "slot_31": ( 0.0,  1.0),
}

ZERO_DEGENERATION_CRITICAL = {"slot_06", "slot_12"}
AUDIT_KEYS = ["git_commit", "data_hash", "config_hash"]
SEPARATOR  = "=" * 80

def sep(title=""):
    print(f"\n{SEPARATOR}")
    if title:
        print(f"  {title}")
        print(SEPARATOR)

def WARN(msg):  print(f"  [VIOLATION] {msg}")
def OK(msg):    print(f"  [PASS] {msg}")
def INFO(msg):  print(f"  [INFO] {msg}")

# =============================================================================
sep("SECTION 2A -- PARQUET FILE LOAD & SCHEMA INSPECTION")
# =============================================================================

try:
    df = pd.read_parquet(PARQUET_PATH)
    print(f"\n  File loaded  : {PARQUET_PATH}")
    print(f"  Disk size    : {os.path.getsize(PARQUET_PATH) / 1024:.1f} KB")
    print(f"  Shape        : {df.shape[0]:,} rows x {df.shape[1]} columns\n")
except Exception as e:
    print(f"  FATAL: Cannot load parquet -- {e}")
    sys.exit(1)

if df.shape[0] < MIN_ROW_COUNT:
    WARN(f"Row count {df.shape[0]:,} < doctrine threshold {MIN_ROW_COUNT:,}. INSUFFICIENT for statistical significance.")
else:
    OK(f"Row count {df.shape[0]:,} >= {MIN_ROW_COUNT:,}.")

# =============================================================================
sep("SECTION 2B -- COLUMN INVENTORY vs EXPECTED SCHEMA")
# =============================================================================

actual_cols   = df.columns.tolist()
missing_slots = [s for s in EXPECTED_SLOTS if s not in actual_cols]
present_slots = [s for s in EXPECTED_SLOTS if s in actual_cols]
extra_cols    = [c for c in actual_cols if c not in EXPECTED_SLOTS]

print(f"\n  Total columns present : {len(actual_cols)}")
print(f"  Expected slot count   : 32 (slot_00 to slot_31)")
print(f"  Present slots         : {len(present_slots)}")
print(f"  Missing slots         : {len(missing_slots)}")
print(f"  Extra / metadata cols : {len(extra_cols)}")
print(f"\n  All columns (with dtype):")
for i, c in enumerate(actual_cols):
    print(f"    [{i:02d}] {c:<30} {str(df[c].dtype)}")

if missing_slots:
    WARN(f"MISSING slots: {missing_slots}")
else:
    OK(f"All 32 slots present.")

print(f"\n  Extra columns: {extra_cols}")

# =============================================================================
sep("SECTION 2C -- DATA TYPE AUDIT")
# =============================================================================

type_violations = []
for slot in present_slots:
    dtype = df[slot].dtype
    if dtype not in [np.float64, np.float32, np.float16]:
        type_violations.append((slot, str(dtype)))

if type_violations:
    WARN(f"Non-float slot dtypes:")
    for slot, dt in type_violations:
        print(f"    {slot}: {dt}")
else:
    OK("All present slots have float dtype.")

# =============================================================================
sep("SECTION 3A -- NaN / INF SCAN (Zero Tolerance)")
# =============================================================================

nan_report = []
inf_report = []

for col in actual_cols:
    nan_count = df[col].isna().sum()
    try:
        inf_count = np.isinf(df[col].astype(float)).sum()
    except Exception:
        inf_count = 0
    if nan_count > 0:
        nan_report.append((col, nan_count, f"{100*nan_count/len(df):.2f}%"))
    if inf_count > 0:
        inf_report.append((col, inf_count, f"{100*inf_count/len(df):.2f}%"))

if nan_report:
    WARN(f"NaN in {len(nan_report)} col(s):")
    for col, cnt, pct in nan_report:
        print(f"    {col}: {cnt:,} NaNs ({pct})")
else:
    OK("No NaN values.")

if inf_report:
    WARN(f"Inf in {len(inf_report)} col(s):")
    for col, cnt, pct in inf_report:
        print(f"    {col}: {cnt:,} Infs ({pct})")
else:
    OK("No Inf values.")

# =============================================================================
sep("SECTION 3B -- STATISTICAL SUMMARY (df.describe) -- All Slots")
# =============================================================================

slot_df = df[[s for s in present_slots]]
desc = slot_df.describe(percentiles=[0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 50)
pd.set_option("display.float_format", lambda x: f"{x:.5f}")
print()
print(desc.to_string())

# =============================================================================
sep("SECTION 3C -- ZERO-VALUE RATIO PER SLOT")
# =============================================================================

print(f"\n  {'Slot':<12} {'Zero%':>8} {'Variance':>14}  Status")
print(f"  {'-'*12} {'-'*8} {'-'*14}  {'-'*40}")

zero_ratio_violations = []
variance_violations   = []

for slot in present_slots:
    col = df[slot].dropna()
    zero_pct = (col == 0.0).sum() / len(col) if len(col) > 0 else 1.0
    variance  = float(col.var())

    is_critical = slot in ZERO_DEGENERATION_CRITICAL
    z_thresh    = ZERO_PCT_CRITICAL if is_critical else ZERO_PCT_FLOOR

    violations = []
    if zero_pct > z_thresh:
        violations.append(f"ZERO%>{z_thresh*100:.0f}%")
        zero_ratio_violations.append((slot, zero_pct, variance))
    if is_critical and variance < VARIANCE_FLOOR:
        violations.append(f"VAR<{VARIANCE_FLOOR}")
        variance_violations.append((slot, variance))

    status = "[FAIL] " + " | ".join(violations) if violations else "[PASS]"
    marker = " <-- CRITICAL" if is_critical else ""
    print(f"  {slot:<12} {zero_pct*100:>7.2f}% {variance:>14.6f}  {status}{marker}")

if zero_ratio_violations:
    print(f"\n  >>> {len(zero_ratio_violations)} slot(s) exceed zero-ratio threshold.")
if variance_violations:
    print(f"\n  >>> {len(variance_violations)} critical slot(s) with variance < {VARIANCE_FLOOR}:")
    for slot, var in variance_violations:
        print(f"      {slot}: variance = {var:.8f} -- POST-FIX DEGENERATION DETECTED")

# =============================================================================
sep("SECTION 3D -- SLOT-SPECIFIC RANGE VIOLATIONS")
# =============================================================================

print(f"\n  {'Slot':<12} {'Min':>12} {'Max':>12} {'Expected Range':<22} Status")
print(f"  {'-'*12} {'-'*12} {'-'*12} {'-'*22} {'-'*20}")

range_violations = []
for slot, (lo, hi) in SLOT_BOUNDS.items():
    if slot not in df.columns:
        print(f"  {slot:<12} {'MISSING':>12}")
        continue
    col = df[slot].dropna()
    cmin, cmax = float(col.min()), float(col.max())
    expected_str = f"[{lo}, {hi if hi is not None else 'inf'}]"
    viol = []
    if lo is not None and cmin < lo:
        viol.append(f"min={cmin:.4f}<{lo}")
    if hi is not None and cmax > hi:
        viol.append(f"max={cmax:.4f}>{hi}")
    status = "[FAIL] " + " | ".join(viol) if viol else "[PASS]"
    if viol:
        range_violations.append((slot, viol))
    print(f"  {slot:<12} {cmin:>12.4f} {cmax:>12.4f} {expected_str:<22} {status}")

# =============================================================================
sep("SECTION 3E -- slot_06 & slot_12 DEEP VARIANCE AUDIT (Primary Success Metric)")
# =============================================================================

for slot in ["slot_06", "slot_12"]:
    if slot not in df.columns:
        WARN(f"{slot} ABSENT from parquet!")
        continue

    col  = df[slot].dropna().astype(float)
    var  = float(col.var())
    std  = float(col.std())
    mean = float(col.mean())
    med  = float(col.median())
    p5   = float(col.quantile(0.05))
    p95  = float(col.quantile(0.95))
    zeros= int((col == 0.0).sum())
    zpct = zeros / len(col) * 100

    print(f"\n  -- {slot.upper()} --")
    print(f"     Count   : {len(col):,}")
    print(f"     Mean    : {mean:.6f}")
    print(f"     Median  : {med:.6f}")
    print(f"     Std Dev : {std:.6f}")
    print(f"     Variance: {var:.8f}   [mandate: >= {VARIANCE_FLOOR}]")
    print(f"     p5/p95  : {p5:.6f} / {p95:.6f}")
    print(f"     Zeros   : {zeros:,} ({zpct:.2f}%)  [mandate: <1%]")

    if var < VARIANCE_FLOOR:
        print(f"\n  [CRITICAL FAILURE] {slot} variance {var:.8f} < {VARIANCE_FLOOR}")
        print(f"     POST-FIX DEGENERATION CONFIRMED. Zero-degeneration NOT resolved.")
    elif zpct > 1.0:
        print(f"\n  [WARNING] {slot} has {zpct:.2f}% zeros (threshold: <1%)")
    else:
        print(f"\n  [PASS] {slot} variance {var:.6f} >= {VARIANCE_FLOOR} and zero% within bounds.")

# =============================================================================
sep("SECTION 3F -- SLOT_28 PHYLUM ID AUDIT")
# =============================================================================

if "slot_28" in df.columns:
    phylum     = df["slot_28"].dropna()
    n_unique   = phylum.nunique()
    all_zero   = (phylum == 0.0).all()
    noise_cnt  = (phylum == -1.0).sum()
    noise_pct  = noise_cnt / len(phylum) * 100

    print(f"\n  Phylum (slot_28) stats:")
    print(f"    Unique values : {n_unique}")
    print(f"    Noise (-1.0)  : {noise_cnt:,} ({noise_pct:.2f}%)")
    print(f"    Value counts  :\n{phylum.value_counts().head(20).to_string()}")

    if all_zero:
        WARN("slot_28 ALL ZEROS -- Global Ontology Compiler NOT run. Phylum ID is placeholder.")
    elif n_unique <= 4:
        WARN(f"slot_28 only {n_unique} unique values -- HDBSCAN may have run in bar loop (Flaw 16 not fixed).")
    elif n_unique < MIN_CLUSTER_SIZE:
        WARN(f"slot_28 only {n_unique} unique phylums -- sparse ontology below min_cluster_size={MIN_CLUSTER_SIZE}.")
    else:
        OK(f"slot_28 has {n_unique} unique phylum IDs -- ontology compiler appears active.")
else:
    WARN("slot_28 MISSING from parquet.")

# =============================================================================
sep("SECTION 3G -- TOP 10 SIGNATURES BY signature_quality (slot_31)")
# =============================================================================

qual_col = "slot_31"
if qual_col in df.columns:
    show_cols = [c for c in ["timestamp", "symbol", "interval", qual_col,
                              "slot_15", "slot_28", "slot_30", "slot_06", "slot_12"]
                 if c in df.columns]
    top10 = df.nlargest(10, qual_col)[show_cols]
    print(f"\n  Top 10 by {qual_col} (signature_quality):\n")
    pd.set_option("display.float_format", lambda x: f"{x:.6f}")
    print(top10.to_string(index=True))
else:
    WARN("slot_31 (signature_quality) not present.")

# =============================================================================
sep("SECTION 3H -- SLOT_30 RECOVERY PROXY AUDIT")
# =============================================================================

if "slot_30" in df.columns:
    rec      = df["slot_30"].dropna().astype(float)
    neg_cnt  = int((rec < 0).sum())
    above_cap= int((rec > RECOVERY_CAP).sum())

    print(f"\n  Recovery proxy (slot_30):")
    print(f"    Min     : {rec.min():.6f}")
    print(f"    Max     : {rec.max():.6f}")
    print(f"    Mean    : {rec.mean():.6f}")
    print(f"    Median  : {rec.median():.6f}")
    print(f"    Negative: {neg_cnt:,}")
    print(f"    > cap({RECOVERY_CAP}): {above_cap:,}")

    if neg_cnt > 0:
        WARN(f"slot_30 has {neg_cnt:,} NEGATIVE values. Violates doctrine [0, {RECOVERY_CAP}].")
    else:
        OK("slot_30 has no negative values.")

    if rec.max() > 1.0:
        INFO(f"slot_30 max = {rec.max():.6f} > 1.0 -- note: spec formula clamps to 1.0 (veto*neural/1). Review if post-hoc populated.")

# =============================================================================
sep("SECTION 3I -- CORRELATION HIGHLIGHTS (slot_15 and slot_30)")
# =============================================================================

corr_targets = ["slot_15", "slot_30", "slot_31"]
all_corr_cols = list(dict.fromkeys(c for c in corr_targets + present_slots if c in df.columns))
corr_df    = df[all_corr_cols].select_dtypes(include=[np.number])
corr_df    = corr_df.loc[:, ~corr_df.columns.duplicated()]   # drop any duplicate col names
corr_matrix = corr_df.corr()

for target in ["slot_15", "slot_30"]:
    if target in corr_matrix.columns:
        print(f"\n  Correlations with {target}:")
        s_corr = corr_matrix[target].drop(labels=target, errors="ignore")
        if isinstance(s_corr, pd.DataFrame):
            s_corr = s_corr.iloc[:, 0]
        sorted_idx = s_corr.abs().sort_values(ascending=False).index
        print(s_corr[sorted_idx].head(12).to_string())

# =============================================================================
sep("SECTION 3J -- DUCKDB CROSS-VALIDATION (signatures.duckdb)")
# =============================================================================

try:
    con = duckdb.connect(DUCKDB_PATH, read_only=True)
    tables = con.execute("SHOW ALL TABLES").fetchall()
    print(f"\n  DuckDB tables/views: {[t[0] for t in tables]}")

    try:
        duck_count = con.execute("SELECT COUNT(*) FROM signatures").fetchone()[0]
        print(f"\n  DuckDB 'signatures' view row count: {duck_count:,}")

        if duck_count != df.shape[0]:
            WARN(f"Row count MISMATCH: parquet={df.shape[0]:,} vs duckdb={duck_count:,}")
        else:
            OK(f"Row count consistent: {duck_count:,} rows.")

        duck_schema = con.execute("DESCRIBE signatures").fetchall()
        duck_cols   = [r[0] for r in duck_schema]
        print(f"\n  DuckDB schema col count: {len(duck_cols)}")

        for slot in ["slot_06", "slot_12"]:
            if slot in duck_cols:
                res = con.execute(
                    f"SELECT variance({slot}), avg({slot}), count(*) "
                    f"FROM signatures WHERE {slot} IS NOT NULL"
                ).fetchone()
                print(f"  DuckDB {slot}: variance={res[0]:.8f}  mean={res[1]:.6f}  count={res[2]:,}")

    except Exception as e:
        WARN(f"DuckDB 'signatures' query failed: {e}")

    con.close()
except Exception as e:
    WARN(f"Cannot open DuckDB: {e}")

# =============================================================================
sep("SECTION 4A -- DUPLICATE TIMESTAMP HASH AUDIT (slot_29)")
# =============================================================================

if "slot_29" in df.columns:
    dupe_count = int(df["slot_29"].duplicated().sum())
    print(f"\n  Duplicate slot_29 (timestamp_hash) entries: {dupe_count:,}")
    if dupe_count > 0:
        WARN(f"{dupe_count:,} duplicate timestamp hashes -- potential signature collision.")
    else:
        OK("No duplicate timestamp hashes.")

# =============================================================================
sep("SECTION 4B -- AUDIT TRAIL COLUMNS CHECK")
# =============================================================================

for key in AUDIT_KEYS:
    if key in df.columns:
        non_null = int(df[key].notna().sum())
        OK(f"Audit column '{key}' present -- {non_null:,} non-null entries.")
    else:
        WARN(f"Audit column '{key}' MISSING. Traceability compromised.")

# =============================================================================
sep("SECTION 5 -- SOVEREIGN PASS/FAIL GATE")
# =============================================================================

gates = []

gates.append(("Row Count >= 10,000",
    df.shape[0] >= MIN_ROW_COUNT,
    f"{df.shape[0]:,} rows"))

gates.append(("All 32 Slots Present",
    len(missing_slots) == 0,
    f"Missing: {missing_slots if missing_slots else 'None'}"))

gates.append(("Zero NaN",
    len(nan_report) == 0,
    f"{len(nan_report)} col(s) with NaN"))

gates.append(("Zero Inf",
    len(inf_report) == 0,
    f"{len(inf_report)} col(s) with Inf"))

if "slot_06" in df.columns:
    v06 = float(df["slot_06"].var())
    gates.append((f"slot_06 variance >= {VARIANCE_FLOOR}", v06 >= VARIANCE_FLOOR, f"variance={v06:.8f}"))

if "slot_12" in df.columns:
    v12 = float(df["slot_12"].var())
    gates.append((f"slot_12 variance >= {VARIANCE_FLOOR}", v12 >= VARIANCE_FLOOR, f"variance={v12:.8f}"))

if "slot_28" in df.columns:
    phylum_ok = not (df["slot_28"] == 0.0).all()
    n_up = df["slot_28"].nunique()
    gates.append(("slot_28 Phylum Populated (not all zero)", phylum_ok, f"{n_up} unique values"))

if "slot_30" in df.columns:
    neg_rec = int((df["slot_30"] < 0).sum())
    gates.append(("slot_30 No Negative Values", neg_rec == 0, f"{neg_rec:,} negatives"))

gates.append(("No Slot Range Violations",
    len(range_violations) == 0,
    f"{len(range_violations)} violation(s)"))

gates.append(("No Zero-Degeneration Slots",
    len(zero_ratio_violations) == 0,
    f"{len(zero_ratio_violations)} slot(s) over threshold"))

audit_present = all(k in df.columns for k in AUDIT_KEYS)
gates.append(("Audit Trail Complete",
    audit_present,
    "Complete" if audit_present else "INCOMPLETE"))

print(f"\n  {'Gate':<48} {'Result':<10} Detail")
print(f"  {'-'*48} {'-'*10} {'-'*35}")

all_pass  = True
fail_count = 0
for label, passed, detail in gates:
    symbol = "[PASS]" if passed else "[FAIL]"
    if not passed:
        all_pass  = False
        fail_count += 1
    print(f"  {label:<48} {symbol:<10} {detail}")

print()
if all_pass:
    print("  *** OVERALL: ALL GATES PASSED -- V5 SOVEREIGN READY ***")
else:
    print(f"  *** OVERALL: {fail_count} GATE(S) FAILED -- NOT PRODUCTION READY ***")

# =============================================================================
sep("END OF AUDIT -- KRONOS V5 signatures_compact.parquet")
# =============================================================================
