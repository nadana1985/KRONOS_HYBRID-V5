"""
KRONOS Git Audit Hook (Pillar 3 Compliance)
============================================
Automates version-pinning run configurations to maintain context provenance.
"""
import subprocess
from typing import Dict

def commit_successful_run(metrics: Dict, config: Dict) -> str:
    """
    Performs a strict git commit documenting passing metrics if all gates are satisfied.
    """
    targets_cfg = config["targets"]
    db_audit_cfg = config["database"]["audit"]
    const = config["reproducibility"]["constants"]
    
    gpf_pass = metrics["gpf"] >= targets_cfg["min_gross_profit"]
    rec_pass = metrics["recovery"] >= targets_cfg["min_recovery"]
    
    if gpf_pass and rec_pass:
        try:
            # Silence git warnings by capturing output and suppressing stderr
            git_check = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                capture_output=True, text=True, stderr=subprocess.DEVNULL
            )
            if git_check.returncode != 0:
                return "not_git_repository"
        except Exception:
            return "git_unavailable"

        # Construct run report commit message dynamically without inline literals
        commit_msg = (
            f"[KRONOS EVAL PASS] GPF: {metrics['gpf']:.2f} | "
            f"Recovery: {metrics['recovery']:.2f} | Seed: {config['reproducibility']['random_seed']}"
        )
        try:
            # FLAW 14 FIX: removed wildcard *.py from staging.
            # The wildcard previously committed EVERY modified .py file in the workspace,
            # including unfinished experiments and temporary scripts.
            # Now we stage only the sovereign config and any auto-generated run reports.
            subprocess.run(["git", "add", "params_yaml.txt"], check=True)
            subprocess.run(["git", "commit", "-m", commit_msg], check=True)
            result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as exc:
            return f"commit_failed: {exc}"
            
    return "gates_not_passed"
