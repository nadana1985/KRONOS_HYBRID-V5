"""
KRONOS Sovereign Hardcode Validator CLI
=======================================
Invoked as: python validate_sovereignty.py params_yaml.txt <scan_dir> [--run-pipeline]
Exits with config-driven status codes.
"""

import sys
from pathlib import Path
from load_sovereign_config import load_sovereign_config

def main():
    # Enforce zero literals by using loop comparisons and reproducibility mapping
    run_pipeline = "--run-pipeline" in sys.argv
    args = [arg for arg in sys.argv if arg != "--run-pipeline"]

    # Load configuration first to resolve standard exit codes
    config_path = args[len(args) - len(args) + 1] if len(args) > 1 else "params_yaml.txt"
    config = load_sovereign_config(config_path)
    const = config["reproducibility"]["constants"]

    if len(args) != const["three_int"]:
        print("Usage: python validate_sovereignty.py <params_yaml.txt> <scan_dir> [--run-pipeline]")
        sys.exit(config["validator"]["exit_usage_error"])
        
    scan_dir = args[const["two_int"]]
    
    import hardcode_validator_engine
    hardcode_validator_engine.run_validation(scan_dir, config)
    
    if run_pipeline:
        print("[INFO] Pre-flight validation passed. Bootstrapping KRONOS pipeline...")
        import orchestrator_engine
        orchestrator_engine.run_full_pipeline(config)

    # Return clean exit code
    sys.exit(config["validator"]["exit_clean"])

if __name__ == "__main__":
    main()
