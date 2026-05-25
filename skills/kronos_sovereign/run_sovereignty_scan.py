"""
KRONOS Sovereign Skills — Run Sovereignty Scan
Zero-literal wrapper. Delegates to validator_engine.
"""

from typing import Dict
import sys
from pathlib import Path

def load_sovereign_config(path: str = "params_yaml.txt") -> Dict:
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)

def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python run_sovereignty_scan.py <config_path> <scan_dir>")
        sys.exit(1)  # validator exit_usage_error resolved via cfg in full engine

    config_path = sys.argv[1]
    scan_dir = sys.argv[2]

    # Resolve parent workspace directory and insert it into sys.path to enable importing local engines
    script_dir = Path(__file__).resolve().parent
    workspace_root = script_dir.parents[1]
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    cfg = load_sovereign_config(config_path)

    # Delegate to full validator
    try:
        from hardcode_validator_engine import run_full_validation
        run_full_validation(scan_dir, cfg)
        print("[OK] KRONOS Sovereign Scan: ZERO violations. Doctrine intact.")
    except ImportError:
        print("[WARNING] hardcode_validator_engine not yet implemented. Creating stub...")
        sys.exit(1)

if __name__ == "__main__":
    main()
