"""
KRONOS Ablation Study Automation Script
=======================================
Runs a controlled out-of-sample small-shard (2026-04-01 to 2026-05-01) ablation test:
- Run A: Full Hybrid Mode (enable_kronos = True)
- Run B: Sovereign Structural Only (enable_kronos = False)

Computes GPF, Recovery Factor, short signature %, and phylum stability,
then prints a markdown table comparing the two runs.
Restores all original configuration and database files after completion.
"""
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import shutil
import json
import pandas as pd
import numpy as np
from pathlib import Path
from load_sovereign_config import load_sovereign_config
from validation_engine import compute_edge_metrics

def main():
    print("=== STARTING KRONOS ABLATION STUDY ===")
    
    # Define paths
    cwd = Path(".")
    params_path = cwd / "params_yaml.txt"
    checkpoint_path = cwd / "data" / "shard_checkpoint.json"
    signatures_dir = cwd / "data" / "signatures"
    compact_path = cwd / "data" / "signatures_compact.parquet"
    duckdb_path = cwd / "data" / "signatures.duckdb"
    
    # Backups
    params_bak = cwd / "params_yaml.txt.bak"
    checkpoint_bak = cwd / "data" / "shard_checkpoint.json.bak"
    signatures_bak = cwd / "data" / "signatures_bak"
    compact_bak = cwd / "data" / "signatures_compact.parquet.bak"
    duckdb_bak = cwd / "data" / "signatures.duckdb.bak"
    
    # 1. Back up original state
    print("[BACKUP] Backing up original parameters and database...")
    shutil.copy(params_path, params_bak)
    if checkpoint_path.exists():
        shutil.copy(checkpoint_path, checkpoint_bak)
    if compact_path.exists():
        shutil.copy(compact_path, compact_bak)
    if duckdb_path.exists():
        shutil.copy(duckdb_path, duckdb_bak)
    if signatures_dir.exists():
        shutil.copytree(signatures_dir, signatures_bak, dirs_exist_ok=True)
        
    results = {}
    
    try:
        # Helper function to clear run files
        def clear_run_state():
            if checkpoint_path.exists():
                os.remove(checkpoint_path)
            if signatures_dir.exists():
                shutil.rmtree(signatures_dir)
            if compact_path.exists():
                os.remove(compact_path)
                
        # Helper function to update params_yaml.txt for the test run
        def set_params(enable_kronos: bool):
            with open(params_bak, "r") as f:
                lines = f.readlines()
            
            new_lines = []
            in_gate = False
            for line in lines:
                # Override dates
                if line.strip().startswith("fetch_start_date:"):
                    new_lines.append("  fetch_start_date: \"2026-04-01 00:00:00\"\n")
                elif line.strip().startswith("fetch_end_date:"):
                    new_lines.append("  fetch_end_date: \"2026-05-01 00:00:00\"\n")
                elif line.strip().startswith("enable_kronos:"):
                    new_lines.append(f"  enable_kronos: {str(enable_kronos).lower()}\n")
                else:
                    new_lines.append(line)
            
            with open(params_path, "w") as f:
                f.writelines(new_lines)
                
        # --- RUN A: FULL HYBRID MODE ---
        print("\n=========================================")
        print("RUN A: FULL HYBRID MODE (enable_kronos=True)")
        print("=========================================")
        clear_run_state()
        set_params(enable_kronos=True)
        
        # Execute sharded pipeline
        os.system("python run_sharded_pipeline.py")
        
        # Load and compute metrics
        if compact_path.exists():
            df_hybrid = pd.read_parquet(compact_path)
            config = load_sovereign_config("params_yaml.txt")
            metrics_hybrid = compute_edge_metrics(df_hybrid, config)
            
            # Short %
            short_pct = (df_hybrid["slot_00"] < 0.0).mean() * 100.0 if not df_hybrid.empty else 0.0
            
            # Phylum stability
            stable_phyla = df_hybrid[df_hybrid["slot_28"] != -1.0]["slot_28"].nunique() if not df_hybrid.empty else 0
            stability_pct = (df_hybrid["slot_28"] != -1.0).mean() * 100.0 if not df_hybrid.empty else 0.0
            
            results["Hybrid"] = {
                "gpf": metrics_hybrid["gpf"],
                "recovery": metrics_hybrid["recovery"],
                "count": metrics_hybrid["total_signatures"],
                "short_pct": short_pct,
                "stable_phyla": stable_phyla,
                "stability_pct": stability_pct,
            }
            # Save for record
            shutil.copy(compact_path, cwd / "data" / "signatures_hybrid_test.parquet")
            print(f"[OK] Run A metrics computed: GPF={metrics_hybrid['gpf']:.4f}, Recovery={metrics_hybrid['recovery']:.4f}")
        else:
            print("[ERROR] Hybrid compaction file not generated!")
            
        # --- RUN B: SOVEREIGN STRUCTURAL ONLY ---
        print("\n=========================================")
        print("RUN B: SOVEREIGN STRUCTURAL ONLY (enable_kronos=False)")
        print("=========================================")
        clear_run_state()
        set_params(enable_kronos=False)
        
        # Execute sharded pipeline
        os.system("python run_sharded_pipeline.py")
        
        # Load and compute metrics
        if compact_path.exists():
            df_sov = pd.read_parquet(compact_path)
            config = load_sovereign_config("params_yaml.txt")
            metrics_sov = compute_edge_metrics(df_sov, config)
            
            # Short %
            short_pct = (df_sov["slot_00"] < 0.0).mean() * 100.0 if not df_sov.empty else 0.0
            
            # Phylum stability
            stable_phyla = df_sov[df_sov["slot_28"] != -1.0]["slot_28"].nunique() if not df_sov.empty else 0
            stability_pct = (df_sov["slot_28"] != -1.0).mean() * 100.0 if not df_sov.empty else 0.0
            
            results["Sovereign"] = {
                "gpf": metrics_sov["gpf"],
                "recovery": metrics_sov["recovery"],
                "count": metrics_sov["total_signatures"],
                "short_pct": short_pct,
                "stable_phyla": stable_phyla,
                "stability_pct": stability_pct,
            }
            # Save for record
            shutil.copy(compact_path, cwd / "data" / "signatures_sovereign_test.parquet")
            print(f"[OK] Run B metrics computed: GPF={metrics_sov['gpf']:.4f}, Recovery={metrics_sov['recovery']:.4f}")
        else:
            print("[ERROR] Sovereign compaction file not generated!")
            
    except Exception as e:
        print(f"[CRITICAL ERROR] Ablation run failed: {e}")
        
    finally:
        # Restore original files
        print("\n[RESTORE] Restoring original parameters and database...")
        if params_bak.exists():
            shutil.copy(params_bak, params_path)
            os.remove(params_bak)
        if checkpoint_bak.exists():
            shutil.copy(checkpoint_bak, checkpoint_path)
            os.remove(checkpoint_bak)
        else:
            if checkpoint_path.exists():
                os.remove(checkpoint_path)
        if compact_bak.exists():
            shutil.copy(compact_bak, compact_path)
            os.remove(compact_bak)
        if duckdb_bak.exists():
            shutil.copy(duckdb_bak, duckdb_path)
            os.remove(duckdb_bak)
        if signatures_bak.exists():
            if signatures_dir.exists():
                shutil.rmtree(signatures_dir)
            shutil.copytree(signatures_bak, signatures_dir, dirs_exist_ok=True)
            shutil.rmtree(signatures_bak)
            
    # Output the results comparison table
    if results:
        print("\n=========================================")
        print("ABLATION STUDY COMPARISON TABLE")
        print("=========================================")
        print("| Metric | Hybrid Baseline (Run A) | Sovereign Structural Only (Run B) |")
        print("| :--- | :---: | :---: |")
        h = results.get("Hybrid", {})
        s = results.get("Sovereign", {})
        print(f"| **Total Signatures** | {h.get('count', 'N/A')} | {s.get('count', 'N/A')} |")
        print(f"| **Gross Profit Factor (GPF)** | {h.get('gpf', 0.0):.4f}x | {s.get('gpf', 0.0):.4f}x |")
        print(f"| **Median Recovery Factor** | {h.get('recovery', 0.0):.4f}x | {s.get('recovery', 0.0):.4f}x |")
        print(f"| **Short Signature %** | {h.get('short_pct', 0.0):.2f}% | {s.get('short_pct', 0.0):.2f}% |")
        print(f"| **Stable Phyla Discovered** | {h.get('stable_phyla', 'N/A')} | {s.get('stable_phyla', 'N/A')} |")
        print(f"| **Phylum Stability (Non-Noise %)** | {h.get('stability_pct', 0.0):.2f}% | {s.get('stability_pct', 0.0):.2f}% |")
        print("=========================================\n")

if __name__ == "__main__":
    main()
