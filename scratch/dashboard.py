import os
import json
import time
import glob
import pandas as pd
from datetime import datetime, timedelta

def run_dashboard():
    # Terminal ANSI Colors for premium aesthetic
    C_BLUE = "\033[94m"
    C_GREEN = "\033[92m"
    C_YELLOW = "\033[93m"
    C_RED = "\033[91m"
    C_BOLD = "\033[1m"
    C_RESET = "\033[0m"
    C_CYAN = "\033[96m"

    print(f"\n{C_BOLD}{C_CYAN}===================================================================={C_RESET}")
    print(f"{C_BOLD}{C_BLUE}            🛸 KRONOS V5 SOVEREIGN MINING LIVE DASHBOARD{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}===================================================================={C_RESET}")

    # 1. Load Checkpoint Data
    checkpoint_file = "data/shard_checkpoint.json"
    completed_shards = []
    if os.path.exists(checkpoint_file):
        try:
            with open(checkpoint_file, "r") as f:
                completed_shards = json.load(f)
        except Exception:
            pass
            
    total_shards = 79
    completed_count = len(completed_shards)
    progress_pct = (completed_count / total_shards) * 100 if total_shards > 0 else 0

    # 2. Render Progress Bar
    bar_width = 30
    filled_width = int(round(bar_width * (completed_count / total_shards))) if total_shards > 0 else 0
    progress_bar = "█" * filled_width + "░" * (bar_width - filled_width)
    
    print(f"\n{C_BOLD}📊 PIPELINE PROGRESS:{C_RESET}")
    print(f"  [{C_GREEN}{progress_bar}{C_RESET}] {C_BOLD}{progress_pct:.1f}%{C_RESET} ({completed_count}/{total_shards} Monthly Shards)")

    # 3. Determine Active & Next Shards
    print(f"\n{C_BOLD}📅 ACTIVE PROCESSING STATE:{C_RESET}")
    if completed_count == 0:
        active_shard = "Shard 1 (November 2019)"
        time_elapsed_str = "Just started"
        eta_str = "Calculating..."
    elif completed_count >= total_shards:
        active_shard = f"{C_GREEN}Pipeline Completed!{C_RESET}"
        time_elapsed_str = "Mining Finished"
        eta_str = "Done"
    else:
        # Estimate based on file modification times
        mtime = os.path.getmtime(checkpoint_file)
        ctime = os.path.getctime(checkpoint_file)
        elapsed_seconds = mtime - ctime
        
        # Average rate
        avg_seconds_per_shard = elapsed_seconds / completed_count if completed_count > 0 else 130.0
        # If ctime and mtime are almost identical, default to a realistic 130s rate
        if avg_seconds_per_shard < 10.0:
            avg_seconds_per_shard = 130.0
            
        remaining_shards = total_shards - completed_count
        eta_seconds = remaining_shards * avg_seconds_per_shard
        
        eta_time = datetime.now() + timedelta(seconds=eta_seconds)
        eta_str = eta_time.strftime("%I:%M %p (Local Time)")
        
        # Format active shard start date
        last_completed = completed_shards[-1]
        active_start = last_completed.split("_")[1]
        active_shard = f"Month {completed_count + 1} (Starting: {active_start[:10]})"
        
        hours_rem = int(eta_seconds // 3600)
        mins_rem = int((eta_seconds % 3600) // 60)
        time_elapsed_str = f"{hours_rem}h {mins_rem}m remaining"

    print(f"  - Currently Processing : {C_YELLOW}{C_BOLD}{active_shard}{C_RESET}")
    print(f"  - Estimated ETA Time   : {C_GREEN}{C_BOLD}{eta_str}{C_RESET}")
    print(f"  - Remaining Duration   : {C_CYAN}{time_elapsed_str}{C_RESET}")

    # 4. Load Signature Metrics
    sig_files = glob.glob("data/signatures/**/*.parquet", recursive=True)
    total_sig_count = 0
    null_count = 0
    min_qual, max_qual, mean_qual = 0.0, 0.0, 0.0
    active_neural = "Inactive"

    if sig_files:
        try:
            df_list = []
            for f in sig_files:
                df_list.append(pd.read_parquet(f))
            df = pd.concat(df_list)
            total_sig_count = len(df)
            null_count = df.isnull().sum().sum()
            
            if total_sig_count > 0:
                min_qual = df["slot_31"].min()
                max_qual = df["slot_31"].max()
                mean_qual = df["slot_31"].mean()
                
                emb_cols = [f"slot_{i}" for i in range(16, 24)]
                all_zeros = df[emb_cols].eq(0.0).all().all()
                active_neural = f"{C_GREEN}Active (Non-Zero){C_RESET}" if not all_zeros else f"{C_RED}Failed (All Zeros){C_RESET}"
        except Exception as e:
            pass

    print(f"\n{C_BOLD}🛡️ DATABASE & SIGNAL HEALTH:{C_RESET}")
    print(f"  - Total Signatures Mined : {C_GREEN}{C_BOLD}{total_sig_count}{C_RESET} signals saved")
    print(f"  - Database Null/NaN Check: {C_GREEN if null_count == 0 else C_RED}{C_BOLD}{null_count}{C_RESET} null values")
    print(f"  - Deep Sequence Network  : {active_neural}")
    print(f"  - Signal Quality Ranges  : Min: {C_YELLOW}{min_qual:.4f}{C_RESET} | Max: {C_GREEN}{max_qual:.4f}{C_RESET} | Mean: {C_CYAN}{mean_qual:.4f}{C_RESET}")

    print(f"\n{C_BOLD}{C_CYAN}===================================================================={C_RESET}")
    print(f"{C_YELLOW}💡 Tip: Run 'watch -n 10 python scratch/dashboard.py' for auto-updates!{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}===================================================================={C_RESET}\n")

if __name__ == "__main__":
    run_dashboard()
