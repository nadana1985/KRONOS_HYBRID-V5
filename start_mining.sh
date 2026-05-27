#!/usr/bin/env bash
# =============================================================================
# KRONOS HYBRID — Headless Mining Launcher for Lightning AI L4
# =============================================================================
# Starts run_full_corpus_mining.py in a tmux session so it survives disconnects.
# Usage: bash start_mining.sh
# Monitor: bash monitor_mining.sh
# =============================================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION="kronos_mining"
LOG_FILE="$REPO_DIR/logs/mining_$(date +%Y%m%d_%H%M%S).log"
CHECKPOINT_FILE="$REPO_DIR/data/full_corpus_checkpoint.json"

mkdir -p "$REPO_DIR/logs"

echo "================================================================"
echo " KRONOS HYBRID — Headless Mining Launch"
echo " Session : $SESSION"
echo " Log     : $LOG_FILE"
echo " Repo    : $REPO_DIR"
echo "================================================================"

# ── Pre-flight: GPU sanity check ────────────────────────────────────
python3 - <<'PYEOF'
import torch, sys
if not torch.cuda.is_available():
    print("[WARNING] CUDA not available — proceeding CPU-only.")
else:
    props = torch.cuda.get_device_properties(0)
    vram  = props.total_memory / (1024**3)
    print(f"[OK] GPU: {props.name} | VRAM: {vram:.1f} GB | CUDA: {torch.version.cuda}")
PYEOF

# ── Pre-flight: checkpoint status ──────────────────────────────────
if [ -f "$CHECKPOINT_FILE" ]; then
    COMPLETED=$(python3 -c "import json; d=json.load(open('$CHECKPOINT_FILE')); print(len(d))")
    echo "[INFO] Resuming from checkpoint: $COMPLETED shard(s) already completed."
else
    echo "[INFO] Fresh run — no checkpoint found. Starting from the beginning."
fi

# ── Launch in tmux (survives SSH disconnects) ───────────────────────
tmux kill-session -t "$SESSION" 2>/dev/null || true
tmux new-session -d -s "$SESSION" -x 220 -y 50

# Wait for zsh shell to finish bootstrapping in the background
sleep 2

# Send the mining command into the tmux session
tmux send-keys -t "$SESSION" "cd $REPO_DIR && python3 run_full_corpus_mining.py params_yaml.txt 2>&1 | tee $LOG_FILE" Enter

echo ""
echo "================================================================"
echo " Mining launched in tmux session: '$SESSION'"
echo ""
echo " Attach to live session  : tmux attach -t $SESSION"
echo " Detach (keep running)   : Ctrl+B, then D"
echo " Live log tail           : tail -f $LOG_FILE"
echo " Monitor progress        : bash monitor_mining.sh"
echo " Kill mining             : tmux kill-session -t $SESSION"
echo "================================================================"
