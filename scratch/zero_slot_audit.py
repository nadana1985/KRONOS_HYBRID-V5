import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import os, pandas as pd

df = pd.read_parquet(os.path.join("data", "signatures_compact.parquet"))

slot_cols = ([f"slot_{i:02d}" for i in range(10)] + [f"slot_{i}" for i in range(10, 32)])
slot_cols = [s for s in slot_cols if s in df.columns]

R  = "\033[91m"; G = "\033[92m"; Y = "\033[93m"; C = "\033[96m"; BO = "\033[1m"; RS = "\033[0m"

print(f"\n{BO}{C}  ZERO-VALUE DISTRIBUTION AUDIT — All 32 Slots{RS}")
print(f"  Total signatures: {len(df):,}\n")
print(f"  {'Slot':<12} {'Zero%':>8}  {'Non-Zero':>9}  {'Min':>10}  {'Max':>10}  {'Std':>10}  Status")
print(f"  {'-'*12} {'-'*8}  {'-'*9}  {'-'*10}  {'-'*10}  {'-'*10}  ------")

full_zero = []
high_zero = []

for sc in slot_cols:
    col = df[sc]
    pct_zero = (col == 0.0).mean() * 100
    nonzero  = int((col != 0.0).sum())
    mn, mx, sd = col.min(), col.max(), col.std()

    if pct_zero == 100.0:
        status = f"{R}{BO}FULL-ZERO{RS}"
        full_zero.append(sc)
        flag = f"  {R}<-- DEAD SLOT{RS}"
    elif pct_zero >= 90.0:
        status = f"{Y}{BO}HIGH-ZERO{RS}"
        high_zero.append(sc)
        flag = f"  {Y}<-- NEAR-ZERO{RS}"
    elif pct_zero >= 50.0:
        status = f"{Y}PARTIAL  {RS}"
        flag = ""
    else:
        status = f"{G}OK       {RS}"
        flag = ""

    print(f"  {sc:<12} {pct_zero:>7.2f}%  {nonzero:>9,}  {mn:>10.4f}  {mx:>10.4f}  {sd:>10.4f}  {status}{flag}")

print(f"\n{BO}  {'='*65}{RS}")
print(f"\n  {BO}Full-zero slots  (100% zeros) : {R}{full_zero if full_zero else 'None'}{RS}")
print(f"  {BO}High-zero slots  (>= 90%     ) : {Y}{high_zero if high_zero else 'None'}{RS}")

if full_zero or high_zero:
    print(f"\n  {BO}ROOT-CAUSE ANALYSIS:{RS}")
    slot_labels = {
        "slot_08": "HMM Regime       — fires only when hidden Markov model detects extreme regime (target_regime_index=3)",
        "slot_09": "Liquidity Vacuum — fires only when order book imbalance > 0.85 threshold",
        "slot_10": "Wick Ratio       — fires only on high-wick candles above p99 quantile threshold",
        "slot_28": "Aux-5            — auxiliary slot, check neural_integration_engine.py",
    }
    for sc in full_zero + high_zero:
        label = slot_labels.get(sc, "Check structural_engine.py for slot firing condition")
        print(f"\n  {Y}{sc}{RS} — {label}")
else:
    print(f"\n  {G}{BO}All slots are healthy — no zero-dominated columns found.{RS}")

print(f"\n{BO}{C}  {'='*65}{RS}\n")
