#!/usr/bin/env bash
# =============================================================================
# KRONOS HYBRID — Mining Progress Monitor
# =============================================================================
# Shows live: shards completed, signatures mined, GPU status, disk usage.
# Usage: bash monitor_mining.sh
# =============================================================================

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECKPOINT_FILE="$REPO_DIR/data/shard_checkpoint.json"
LOG_DIR="$REPO_DIR/logs"
SESSION="kronos_mining"

clear
echo "================================================================"
echo " KRONOS HYBRID — Mining Monitor  ($(date '+%Y-%m-%d %H:%M:%S'))"
echo "================================================================"

# ── 1. Session status ───────────────────────────────────────────────
if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo " Session  : [RUNNING] $SESSION"
else
    echo " Session  : [STOPPED] $SESSION is not active."
fi

# ── 2. Checkpoint progress ──────────────────────────────────────────
if [ -f "$CHECKPOINT_FILE" ]; then
    python3 - <<PYEOF
import json, sys
with open("$CHECKPOINT_FILE") as f:
    shards = json.load(f)
completed = len(shards)
print(f" Shards   : {completed} completed")
if shards:
    first = shards[0][:10]
    last  = shards[-1][:10]
    print(f" Range    : {first} → {last}")
PYEOF
else
    echo " Shards   : 0 completed (checkpoint not yet created)"
fi

# ── 3. Signatures mined so far ──────────────────────────────────────
python3 - <<'PYEOF'
import os, glob
sig_dir = "data/signatures"
compact  = "data/signatures_compact.parquet"

try:
    import pandas as pd
    if os.path.exists(compact):
        df = pd.read_parquet(compact, columns=["timestamp"])
        print(f" Sigs DB  : {len(df):,} (compact file)")
    else:
        files = glob.glob(os.path.join(sig_dir, "**", "*.parquet"), recursive=True)
        if files:
            total = sum(len(pd.read_parquet(f, columns=["timestamp"])) for f in files)
            print(f" Sigs DB  : {total:,} (partition tree, {len(files)} files)")
        else:
            print(" Sigs DB  : 0 (no parquet files written yet)")
except Exception as e:
    print(f" Sigs DB  : unknown ({e})")
PYEOF

# ── 4. GPU utilisation ──────────────────────────────────────────────
echo ""
echo "--- GPU Status ---"
if command -v nvidia-smi &>/dev/null; then
    nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu \
               --format=csv,noheader,nounits | \
    awk -F',' '{printf " GPU       : %s | Util: %s%% | VRAM: %s/%s MiB | Temp: %s°C\n", $1, $2, $3, $4, $5}'
else
    echo " GPU       : nvidia-smi not available"
fi

# ── 5. Disk usage ──────────────────────────────────────────────────
echo ""
echo "--- Disk Usage ---"
du -sh "data/" 2>/dev/null | awk '{print " data/     : " $1}' || echo " data/     : not found"

# ── 6. Latest log lines ────────────────────────────────────────────
LATEST_LOG=$(ls -t "$LOG_DIR"/mining_*.log 2>/dev/null | head -1)
if [ -n "$LATEST_LOG" ]; then
    echo ""
    echo "--- Last 15 log lines ($LATEST_LOG) ---"
    tail -15 "$LATEST_LOG"
else
    echo ""
    echo "--- No log file found yet ---"
fi

echo ""
echo "================================================================"
echo " Attach to live session : tmux attach -t $SESSION"
echo " Re-run this monitor    : bash monitor_mining.sh"
echo "================================================================"
