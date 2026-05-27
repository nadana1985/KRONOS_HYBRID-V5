import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import os
import pandas as pd
import numpy as np

R  = "\033[91m"; G  = "\033[92m"; Y  = "\033[93m"
B  = "\033[94m"; C  = "\033[96m"; M  = "\033[95m"
BO = "\033[1m";  RS = "\033[0m"

def hdr(t): print(f"\n{BO}{C}{'='*70}{RS}\n{BO}{B}  {t}{RS}\n{BO}{C}{'='*70}{RS}")

df = pd.read_parquet(os.path.join("data", "signatures_compact.parquet"))
df["timestamp"] = pd.to_datetime(df["timestamp"])
df["recovery_factor"] = pd.to_numeric(df["recovery_factor"], errors="coerce")
df["mfe"] = pd.to_numeric(df["mfe"], errors="coerce")
df["mae"] = pd.to_numeric(df["mae"], errors="coerce")

print(f"\n{BO}{C}  KRONOS V5 -- BEST TRADE ANALYSIS (20-Day Mining Window){RS}")
print(f"  Period : {df['timestamp'].min()} --> {df['timestamp'].max()}")
print(f"  Total  : {len(df):,} mined signatures")

# ── 1. OVERALL BEST BY COMBINED QUALITY (slot_31) ─────────────────────────
hdr("1. TOP 10 BY COMBINED QUALITY SCORE  (slot_31)")
top_quality = df.nlargest(10, "slot_31")[
    ["timestamp","slot_31","slot_15","neural_conviction","mfe","mae","recovery_factor"]
].reset_index(drop=True)

print(f"\n  {'#':<3} {'Timestamp':<28} {'Quality':>8} {'Veto':>7} {'NConv':>7} {'MFE%':>8} {'MAE%':>8} {'RecFact':>10}")
print(f"  {'-'*3} {'-'*28} {'-'*8} {'-'*7} {'-'*7} {'-'*8} {'-'*8} {'-'*10}")
for i, row in top_quality.iterrows():
    mfe_gt = G if row["mfe"] > row["mae"] else Y
    print(f"  {i+1:<3} {str(row['timestamp']):<28} "
          f"{row['slot_31']:>8.4f} {row['slot_15']:>7.4f} {row['neural_conviction']:>7.4f} "
          f"{mfe_gt}{row['mfe']*100:>7.4f}%{RS} {row['mae']*100:>7.4f}% {row['recovery_factor']:>10.4f}")

# ── 2. ABSOLUTE BEST MFE (maximum upside captured) ────────────────────────
hdr("2. TOP 10 BY MAX FAVORABLE EXCURSION  (highest upside captured)")
top_mfe = df.nlargest(10, "mfe")[
    ["timestamp","mfe","mae","recovery_factor","slot_31","slot_15","neural_conviction"]
].reset_index(drop=True)

print(f"\n  {'#':<3} {'Timestamp':<28} {'MFE%':>9} {'MAE%':>8} {'RecFact':>10} {'Quality':>8} {'Veto':>7}")
print(f"  {'-'*3} {'-'*28} {'-'*9} {'-'*8} {'-'*10} {'-'*8} {'-'*7}")
for i, row in top_mfe.iterrows():
    print(f"  {i+1:<3} {str(row['timestamp']):<28} "
          f"{G}{row['mfe']*100:>8.4f}%{RS} {row['mae']*100:>7.4f}% "
          f"{row['recovery_factor']:>10.4f} {row['slot_31']:>8.4f} {row['slot_15']:>7.4f}")

# ── 3. BEST RECOVERY FACTOR (MFE/MAE ratio — cleanest trades) ─────────────
hdr("3. TOP 10 BY RECOVERY FACTOR  (cleanest MFE/MAE ratio)")
# Exclude RF = inf/very large (mfe/mae > 0 and mae > 0.0001)
clean = df[(df["mae"] > 0.0001) & (df["mfe"] > 0)]
top_rf = clean.nlargest(10, "recovery_factor")[
    ["timestamp","recovery_factor","mfe","mae","slot_31","slot_15","neural_conviction"]
].reset_index(drop=True)

print(f"\n  {'#':<3} {'Timestamp':<28} {'RecFact':>10} {'MFE%':>9} {'MAE%':>8} {'Quality':>8} {'Veto':>7}")
print(f"  {'-'*3} {'-'*28} {'-'*10} {'-'*9} {'-'*8} {'-'*8} {'-'*7}")
for i, row in top_rf.iterrows():
    print(f"  {i+1:<3} {str(row['timestamp']):<28} "
          f"{G}{row['recovery_factor']:>10.4f}{RS} {row['mfe']*100:>8.4f}% "
          f"{row['mae']*100:>7.4f}% {row['slot_31']:>8.4f} {row['slot_15']:>7.4f}")

# ── 4. THE SINGLE BEST TRADE (highest quality + MFE > MAE + best RF) ──────
hdr("4. THE SINGLE BEST TRADE  (sovereign composite rank)")

# Composite rank: normalise quality, mfe, recovery_factor then sum
df2 = df[(df["mae"] > 0.0001) & (df["mfe"] > 0)].copy()

def minmax(s):
    rng = s.max() - s.min()
    return (s - s.min()) / rng if rng > 0 else s * 0

df2["rank_quality"] = minmax(df2["slot_31"])
df2["rank_mfe"]     = minmax(df2["mfe"])
df2["rank_rf"]      = minmax(df2["recovery_factor"].clip(upper=df2["recovery_factor"].quantile(0.99)))
df2["composite"]    = (df2["rank_quality"] * 0.4 +
                       df2["rank_mfe"]     * 0.3 +
                       df2["rank_rf"]      * 0.3)

best = df2.nlargest(1, "composite").iloc[0]

print(f"""
  {BO}{G}*** SOVEREIGN BEST TRADE ***{RS}

  Timestamp        : {BO}{best['timestamp']}{RS}
  Combined Quality : {BO}{G}{best['slot_31']:.4f}{RS}  (slot_31)
  Veto Score       : {best['slot_15']:.4f}  (slot_15 structural engine)
  Neural Conviction: {best['neural_conviction']:.4f}
  Composite Rank   : {BO}{best['composite']:.4f}{RS}  (quality 40% + MFE 30% + RF 30%)

  {BO}--- FORWARD PERFORMANCE (72-bar / 6-hour window) ---{RS}
  Max Favorable Excursion (MFE) : {BO}{G}{best['mfe']*100:.4f}%{RS}
  Max Adverse Excursion  (MAE)  : {R}{best['mae']*100:.4f}%{RS}
  Recovery Factor               : {BO}{G}{best['recovery_factor']:.4f}{RS}
  MFE > MAE                     : {G+'YES'+RS if best['mfe'] > best['mae'] else R+'NO'+RS}

  {BO}--- 32-SLOT DNA FINGERPRINT ---{RS}""")

slot_labels = {
    "slot_00": "Bid-Ask Absorb",      "slot_01": "VPIN",
    "slot_02": "Spectral Entropy",    "slot_03": "Log-Var Ratio",
    "slot_04": "Fractal Hurst",       "slot_05": "Autocorr Multi-Lag",
    "slot_06": "EMA Ribbon Dev",      "slot_07": "Vol-Price Div",
    "slot_08": "HMM Regime",          "slot_09": "Liquidity Vacuum",
    "slot_10": "Wick Ratio",          "slot_11": "SR-KDE Proximity",
    "slot_12": "Micro-Price Dev",     "slot_13": "Shannon Entropy",
    "slot_14": "Hilbert Cycle",       "slot_15": "Composite Veto",
    "slot_16": "Neural Embed-1",      "slot_17": "Neural Embed-2",
    "slot_18": "Neural Embed-3",      "slot_19": "Neural Embed-4",
    "slot_20": "Neural Embed-5",      "slot_21": "Neural Embed-6",
    "slot_22": "Neural Embed-7",      "slot_23": "Neural Embed-8",
    "slot_24": "Vol Forecast",        "slot_25": "MFE Projection",
    "slot_26": "Neural Regime",       "slot_27": "Aux-4",
    "slot_28": "Aux-5",               "slot_29": "Aux-6",
    "slot_30": "Aux-7",               "slot_31": "Combined Quality",
}

slot_cols = (["slot_00","slot_01","slot_02","slot_03","slot_04","slot_05",
              "slot_06","slot_07","slot_08","slot_09"] +
             [f"slot_{i}" for i in range(10,32)])

print(f"\n  {'Slot':<10} {'Label':<22} {'Value':>10}  {'Signal Bar':}")
print(f"  {'-'*10} {'-'*22} {'-'*10}  {'-'*30}")

for sc in slot_cols:
    if sc not in best.index: continue
    val = best[sc]
    label = slot_labels.get(sc, "")
    # Normalise to -1..1 bar width
    bar_len = int(min(abs(val), 2.0) / 2.0 * 20)
    if val >= 0:
        bar = " " * 20 + "|" + "#" * bar_len + "." * (20 - bar_len)
        color = G
    else:
        bar = "." * (20 - bar_len) + "#" * bar_len + "|" + " " * 20
        color = Y
    print(f"  {sc:<10} {label:<22} {color}{val:>10.4f}{RS}  {color}{bar}{RS}")

# ── 5. DAILY BEST SUMMARY ──────────────────────────────────────────────────
hdr("5. DAILY BEST TRADE PER DAY  (top slot_31 each day)")
df["date"] = df["timestamp"].dt.date
daily_best = (df.groupby("date", group_keys=False)
                .apply(lambda x: x.nlargest(1, "slot_31").iloc[0]))
daily_best = daily_best.reset_index(drop=True)

print(f"\n  {'Date':<14} {'Timestamp':<28} {'Quality':>8} {'MFE%':>8} {'MAE%':>8} {'RecFact':>10} {'Edge':>6}")
print(f"  {'-'*14} {'-'*28} {'-'*8} {'-'*8} {'-'*8} {'-'*10} {'-'*6}")
for _, row in daily_best.iterrows():
    ts   = row["timestamp"]
    date = str(ts)[:10]
    edge = G+"YES"+RS if row["mfe"] > row["mae"] else R+" NO"+RS
    print(f"  {date:<14} {str(ts):<28} "
          f"{row['slot_31']:>8.4f} {row['mfe']*100:>7.4f}% "
          f"{row['mae']*100:>7.4f}% {row['recovery_factor']:>10.4f}  {edge}")

print(f"\n{BO}{C}{'='*70}{RS}")
print(f"{BO}{G}  ANALYSIS COMPLETE{RS}")
print(f"{BO}{C}{'='*70}{RS}\n")
