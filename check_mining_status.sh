#!/usr/bin/env bash
# =============================================================================
# KRONOS HYBRID — Full Mining Intelligence Report
# =============================================================================
# Covers:
#   1. Shard progress (158 shards in full corpus — 15-day blocks)
#   2. ETA to completion
#   3. Signatures found so far
#   4. Full 32-slot audit (values + zero-value detection)
# Usage: bash check_mining_status.sh
# =============================================================================

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECKPOINT_FILE="$REPO_DIR/data/full_corpus_checkpoint.json"
COMPACT_FILE="$REPO_DIR/data/signatures_compact.parquet"
SIG_DIR="$REPO_DIR/data/signatures"

clear
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║       KRONOS HYBRID — Mining Intelligence Report                ║"
echo "║       $(date '+%Y-%m-%d %H:%M:%S')                             ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# =============================================================================
# SECTION 1 — SHARD PROGRESS + ETA
# =============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  [1]  SHARD PROGRESS & ETA"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

python3 - <<'PYEOF'
import json, os, glob, time, datetime
from pathlib import Path

checkpoint_file = "data/full_corpus_checkpoint.json"
sig_dir         = "data/signatures"
compact_file    = "data/signatures_compact.parquet"

# ── Load checkpoint ──────────────────────────────────────────────────────────
completed = []
if os.path.exists(checkpoint_file):
    try:
        with open(checkpoint_file) as f:
            completed = json.load(f)
    except Exception as e:
        print(f"  [WARN] Could not read checkpoint: {e}")

total_shards  = 158  # full corpus = 158 x 15-day shards
done          = len(completed)
remaining     = total_shards - done
pct           = (done / total_shards * 100) if total_shards else 0

print(f"  Total Shards   : {total_shards}")
print(f"  Completed      : {done}  ({pct:.1f}%)")
print(f"  Remaining      : {remaining}")

# Progress bar
bar_len = 40
filled  = int(bar_len * done / total_shards) if total_shards else 0
bar     = "█" * filled + "░" * (bar_len - filled)
print(f"  Progress       : [{bar}] {done}/{total_shards}")

# ── ETA calculation from parquet file modification times ─────────────────────
parquet_files = sorted(
    glob.glob(os.path.join(sig_dir, "**", "*.parquet"), recursive=True),
    key=lambda f: os.path.getmtime(f)
)

if len(parquet_files) >= 2 and done > 0:
    # Time per shard = total elapsed / shards done
    oldest_mtime = os.path.getmtime(parquet_files[0])
    newest_mtime = os.path.getmtime(parquet_files[-1])
    elapsed_secs = newest_mtime - oldest_mtime

    if elapsed_secs > 0 and done > 1:
        secs_per_shard  = elapsed_secs / (done - 1)
        eta_secs        = secs_per_shard * remaining
        eta_dt          = datetime.datetime.now() + datetime.timedelta(seconds=eta_secs)
        elapsed_human   = str(datetime.timedelta(seconds=int(elapsed_secs)))
        eta_human       = str(datetime.timedelta(seconds=int(eta_secs)))
        print(f"\n  Time Elapsed   : {elapsed_human}")
        print(f"  Avg/Shard      : {str(datetime.timedelta(seconds=int(secs_per_shard)))}")
        print(f"  ETA Remaining  : {eta_human}")
        print(f"  ETA Finish     : {eta_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print("\n  ETA            : Not enough shards completed yet to estimate")
elif done == 0:
    print("\n  ETA            : Mining has not started yet")
else:
    print("\n  ETA            : Estimating... (only 1 shard done so far)")

# ── Speed diagnosis ──────────────────────────────────────────────────────────
print("\n  ── Why is mining slow on L4? ──────────────────────────────────")
print("  • L4 GPU has 24 GB VRAM but only ~121 TFLOPS FP16 vs A100 312 TFLOPS")
print("  • Slot_8 (HMM) is CPU-bound → bottleneck on large lookback_bars=288")
print("  • Slot_4 (Hurst) grid_points=50 is compute-heavy per bar")
print("  • Bar-by-bar Python loop (not vectorized across bars)")
print("  • If 14 shards = ~14 months of 5m ETHUSDT data → ~120k+ bars total")
print("  ✦ TIP: Set hmm_refit_interval higher (e.g. 576) to cut Slot_8 cost")
PYEOF

echo ""

# =============================================================================
# SECTION 2 — SIGNATURES FOUND SO FAR
# =============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  [2]  SIGNATURES FOUND SO FAR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

python3 - <<'PYEOF'
import os, glob
import pandas as pd

compact  = "data/signatures_compact.parquet"
sig_dir  = "data/signatures"

try:
    if os.path.exists(compact):
        df = pd.read_parquet(compact)
        print(f"  Source         : Compact file  ({compact})")
        print(f"  Total Sigs     : {len(df):,}")
        if "symbol" in df.columns:
            print(f"  By Symbol      : {df['symbol'].value_counts().to_dict()}")
        if "timestamp" in df.columns:
            print(f"  Date Range     : {df['timestamp'].min()}  →  {df['timestamp'].max()}")
    else:
        files = sorted(glob.glob(os.path.join(sig_dir, "**", "*.parquet"), recursive=True))
        if files:
            dfs   = [pd.read_parquet(f) for f in files]
            df    = pd.concat(dfs, ignore_index=True)
            print(f"  Source         : Partition tree  ({len(files)} parquet files)")
            print(f"  Total Sigs     : {len(df):,}")
            if "symbol" in df.columns:
                print(f"  By Symbol      : {df['symbol'].value_counts().to_dict()}")
            if "timestamp" in df.columns:
                print(f"  Date Range     : {df['timestamp'].min()}  →  {df['timestamp'].max()}")
        else:
            print("  Total Sigs     : 0  (no parquet files written yet)")
            df = None
except Exception as e:
    print(f"  [ERROR] Could not read signatures: {e}")
    df = None
PYEOF

echo ""

# =============================================================================
# SECTION 3 — 32-SLOT AUDIT (all values + zero-value slots)
# =============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  [3]  32-SLOT FULL AUDIT  (mean values + zero-value detection)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

python3 - <<'PYEOF'
import os, glob
import pandas as pd
import numpy as np

compact  = "data/signatures_compact.parquet"
sig_dir  = "data/signatures"

# All 32 slots with descriptions
SLOT_META = {
    "slot_00": "Bid-Ask Absorption",
    "slot_01": "Order Flow Toxicity (VPIN)",
    "slot_02": "Spectral Entropy",
    "slot_03": "Log Variance Ratio",
    "slot_04": "Fractal Hurst Exponent",
    "slot_05": "Multi-Lag Autocorrelation",
    "slot_06": "EMA Ribbon Deviation",
    "slot_07": "Volume-Price Divergence",
    "slot_08": "HMM Regime Classifier",
    "slot_09": "Liquidity Vacuum",
    "slot_10": "Wick-to-Body Ratio",
    "slot_11": "S/R KDE Proximity",
    "slot_12": "Micro-Price Deviation",
    "slot_13": "Shannon Returns Entropy",
    "slot_14": "Hilbert Cycle Phase",
    "slot_15": "Sovereign Veto Composite",
    "slot_16": "Neural Latent Dim-0",
    "slot_17": "Neural Latent Dim-1",
    "slot_18": "Neural Latent Dim-2",
    "slot_19": "Neural Latent Dim-3",
    "slot_20": "Neural Latent Dim-4",
    "slot_21": "Neural Latent Dim-5",
    "slot_22": "Neural Latent Dim-6",
    "slot_23": "Neural Latent Dim-7",
    "slot_24": "Vol Forecast Delta",
    "slot_25": "MFE Projection",
    "slot_26": "Neural Regime Strength",
    "slot_27": "Score Divergence Residual",
    "slot_28": "Phylum ID (HDBSCAN)",
    "slot_29": "Timestamp Hash",
    "slot_30": "Recovery Proxy",
    "slot_31": "Signature Quality Score",
}

try:
    if os.path.exists(compact):
        df = pd.read_parquet(compact)
    else:
        files = sorted(glob.glob(os.path.join(sig_dir, "**", "*.parquet"), recursive=True))
        if not files:
            print("  [WARN] No signature data found. Run mining first.")
            exit()
        df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)

    print(f"\n  {'Slot':<10} {'Description':<32} {'Mean':>10} {'Std':>10} {'Min':>10} {'Max':>10}  {'Status'}")
    print(f"  {'─'*10} {'─'*32} {'─'*10} {'─'*10} {'─'*10} {'─'*10}  {'─'*15}")

    zero_slots   = []
    missing_slots = []

    for slot_key, desc in SLOT_META.items():
        if slot_key not in df.columns:
            print(f"  {slot_key:<10} {desc:<32} {'':>10} {'':>10} {'':>10} {'':>10}  ⚠ MISSING")
            missing_slots.append(slot_key)
            continue

        col    = df[slot_key].dropna()
        mean_v = col.mean()
        std_v  = col.std()
        min_v  = col.min()
        max_v  = col.max()
        pct_zero = (col == 0.0).sum() / len(col) * 100 if len(col) > 0 else 100.0

        if pct_zero >= 99.0:
            status = f"⚠ ALL ZERO ({pct_zero:.0f}%)"
            zero_slots.append(slot_key)
        elif pct_zero >= 50.0:
            status = f"⚠ MOSTLY ZERO ({pct_zero:.0f}%)"
            zero_slots.append(slot_key)
        elif pct_zero >= 10.0:
            status = f"△ {pct_zero:.0f}% zero"
        else:
            status = "✓ OK"

        print(f"  {slot_key:<10} {desc:<32} {mean_v:>10.4f} {std_v:>10.4f} {min_v:>10.4f} {max_v:>10.4f}  {status}")

    # ── Zero-slot summary ─────────────────────────────────────────────────────
    print(f"\n  {'─'*70}")
    if zero_slots:
        print(f"\n  ⚠  SLOTS WITH ALL/MOSTLY ZERO VALUES ({len(zero_slots)} slots):")
        for s in zero_slots:
            print(f"       • {s}  →  {SLOT_META[s]}")
        print()
        print("  Root Causes to Check:")
        if "slot_28" in zero_slots:
            print("    slot_28 (phylum_id)  → EXPECTED during mining. Filled after")
            print("                           compile_global_ontology() runs post-run.")
        if "slot_09" in zero_slots or "slot_12" in zero_slots:
            print("    slot_09 / slot_12    → Need live order-book depth data.")
            print("                           Check raw_aggtrades_path is not null.")
        if "slot_15" in zero_slots:
            print("    slot_15 (veto)       → veto_threshold=0.0 lets everything pass.")
            print("                           Low weights may produce ~zero composite.")
        neural_zeros = [s for s in zero_slots if s in [f"slot_{i:02d}" for i in range(16,24)]]
        if neural_zeros:
            print(f"    {', '.join(neural_zeros)} → Kronos-Mini model not loading correctly.")
            print("                           Check kronos_module/models path on L4.")
    else:
        print("\n  ✓  No all-zero slot columns detected. All slots look healthy.")

    if missing_slots:
        print(f"\n  ✗  MISSING SLOT COLUMNS ({len(missing_slots)}):")
        for s in missing_slots:
            print(f"       • {s}  →  {SLOT_META[s]}")

    # ── Unique phylum count ───────────────────────────────────────────────────
    if "slot_28" in df.columns:
        unique_phyla = df["slot_28"].nunique()
        phyla_vals   = sorted(df["slot_28"].unique().tolist())[:10]
        print(f"\n  Phylum (slot_28) unique values : {unique_phyla}")
        print(f"  Phylum sample labels           : {phyla_vals}")
        if unique_phyla <= 4:
            print("  ⚠  Very few phyla — compile_global_ontology() may not have run yet.")

except Exception as e:
    print(f"  [ERROR] Slot audit failed: {e}")
    import traceback; traceback.print_exc()
PYEOF

echo ""

# =============================================================================
# SECTION 4 — GPU STATUS (L4)
# =============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  [4]  GPU STATUS (L4)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if command -v nvidia-smi &>/dev/null; then
    nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw \
               --format=csv,noheader,nounits | \
    awk -F',' '{printf "  GPU      : %s\n  Util     : %s%%\n  VRAM     : %s / %s MiB\n  Temp     : %s°C\n  Power    : %s W\n", $1,$2,$3,$4,$5,$6}'
else
    echo "  nvidia-smi not available on this machine"
fi

echo ""

# =============================================================================
# SECTION 5 — DISK
# =============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  [5]  DISK USAGE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
du -sh data/ 2>/dev/null | awk '{print "  data/    : " $1}' || echo "  data/ not found"
du -sh data/signatures/ 2>/dev/null | awk '{print "  sigs/    : " $1}'
[ -f data/signatures_compact.parquet ] && \
    du -sh data/signatures_compact.parquet | awk '{print "  compact  : " $1}'

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  Quick Commands                                                  ║"
echo "║  Watch live log : tail -f logs/mining_*.log                     ║"
echo "║  Re-run report  : bash check_mining_status.sh                   ║"
echo "║  Attach tmux    : tmux attach -t kronos_mining                  ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
