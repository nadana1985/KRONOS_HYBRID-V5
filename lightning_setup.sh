#!/usr/bin/env bash
# =============================================================================
# KRONOS HYBRID — Lightning AI L4 Studio Setup Script
# =============================================================================
# Run ONCE after uploading the repo to your Lightning AI Studio.
# Usage: bash lightning_setup.sh
# =============================================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$REPO_DIR/logs/setup.log"
mkdir -p "$REPO_DIR/logs"
mkdir -p "$REPO_DIR/data/signatures"
mkdir -p "$REPO_DIR/data/raw"
mkdir -p "$REPO_DIR/data/processed"
mkdir -p "$REPO_DIR/data/cache"

echo "================================================================"
echo " KRONOS HYBRID — Lightning AI L4 Environment Setup"
echo " Repo: $REPO_DIR"
echo " Log:  $LOG_FILE"
echo "================================================================"

# ── 1. System packages ──────────────────────────────────────────────
echo "[1/6] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq git curl htop screen tmux libgomp1 2>&1 | tee -a "$LOG_FILE"

# ── 2. Python version check ─────────────────────────────────────────
echo "[2/6] Checking Python version..."
python3 --version
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python: $PYTHON_VERSION" | tee -a "$LOG_FILE"

# ── 3. Install Python dependencies ──────────────────────────────────
echo "[3/6] Installing Python dependencies..."
cd "$REPO_DIR"

# Install PyTorch first with CUDA 12.1 (matches L4 driver stack on Lightning AI)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 2>&1 | tee -a "$LOG_FILE"

# Install the rest of requirements
pip install \
    "numpy>=1.24.0" \
    "pandas>=2.0.0" \
    "pyarrow>=12.0.0" \
    "duckdb>=0.9.0" \
    "scipy>=1.10.0" \
    "transformers>=4.30.0" \
    "hdbscan>=0.8.29" \
    "scikit-learn>=1.2.0" \
    "pyyaml>=6.0" \
    "requests>=2.28.0" \
    "einops>=0.6.0" \
    "python-dotenv>=1.0.0" \
    "litellm>=1.0.0" \
    2>&1 | tee -a "$LOG_FILE"

echo "[3/6] Dependencies installed." | tee -a "$LOG_FILE"

# ── 4. Verify CUDA / GPU ────────────────────────────────────────────
echo "[4/6] Verifying CUDA + L4 GPU..."
python3 - <<'PYEOF' | tee -a "$LOG_FILE"
import torch
print(f"  PyTorch version : {torch.__version__}")
print(f"  CUDA available  : {torch.cuda.is_available()}")
if torch.cuda.is_available():
    for i in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(i)
        vram = props.total_memory / (1024**3)
        print(f"  GPU [{i}]          : {props.name} | VRAM: {vram:.1f} GB")
else:
    print("  WARNING: CUDA not available. CPU-only execution will proceed.")
PYEOF

# ── 5. Validate sovereign config ────────────────────────────────────
echo "[5/6] Validating sovereign config (params_yaml.txt)..."
cd "$REPO_DIR"
python3 - <<'PYEOF' | tee -a "$LOG_FILE"
import sys, os
sys.path.insert(0, os.getcwd())
from load_sovereign_config import load_sovereign_config
cfg = load_sovereign_config("params_yaml.txt")
# Spot-check critical config nodes
assert cfg["miner"]["symbols"], "miner.symbols is empty!"
assert cfg["data"]["fetch_start_date"], "data.fetch_start_date is not set!"
assert cfg["reproducibility"]["constants"]["one_day_int"] == 1, "one_day_int missing!"
assert cfg["database"]["compact_path"], "database.compact_path not set!"
assert cfg["targets"]["perfect_gpf_sentinel"] == 999.0, "perfect_gpf_sentinel missing!"
print("  [OK] params_yaml.txt: all critical config nodes validated.")
PYEOF

# ── 6. Run sovereignty validator ────────────────────────────────────
echo "[6/6] Running hardcode sovereignty validator..."
cd "$REPO_DIR"
python3 - <<'PYEOF' | tee -a "$LOG_FILE"
import sys, os
sys.path.insert(0, os.getcwd())
from load_sovereign_config import load_sovereign_config
import hardcode_validator_engine
cfg = load_sovereign_config("params_yaml.txt")
hardcode_validator_engine.run_full_validation(".", cfg)
print("  [OK] Sovereignty validator passed. Zero inline literals detected.")
PYEOF

echo ""
echo "================================================================"
echo " SETUP COMPLETE. KRONOS HYBRID is ready to mine."
echo " Next step: bash start_mining.sh"
echo "================================================================"
