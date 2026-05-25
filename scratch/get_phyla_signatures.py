import sys
import re
from pathlib import Path
import shutil
import pandas as pd
import numpy as np

# Add root folder to sys.path
root_dir = Path(__file__).resolve().parents[1]
sys.path.append(str(root_dir))

def parse_simple_yaml(filepath):
    data = {}
    stack = [data]
    indents = [-1]
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.split('#')[0]
            stripped = line.strip()
            if not stripped:
                continue
            
            indent = len(line) - len(line.lstrip())
            
            while indent <= indents[-1]:
                stack.pop()
                indents.pop()
                
            parent = stack[-1]
            
            if stripped.startswith('-'):
                val_str = stripped[1:].strip()
                if any(c.isdigit() for c in val_str) and ('.' in val_str or 'e' in val_str):
                    val = float(val_str)
                else:
                    try:
                        val = int(val_str)
                    except ValueError:
                        val = val_str.strip('"').strip("'")
                
                if isinstance(stack[-1], dict) and len(stack[-1]) == 0:
                    new_list = []
                    if len(stack) > 1:
                        p = stack[-2]
                        for k, v in p.items():
                            if v is stack[-1]:
                                p[k] = new_list
                                break
                    stack[-1] = new_list
                
                if isinstance(stack[-1], list):
                    stack[-1].append(val)
                continue
            
            match = re.match(r'^([^:]+):\s*(.*)$', stripped)
            if not match:
                continue
            
            key = match.group(1).strip()
            val_str = match.group(2).strip()
            
            if val_str == "":
                if key in parent and isinstance(parent[key], dict):
                    new_dict = parent[key]
                else:
                    new_dict = {}
                    parent[key] = new_dict
                stack.append(new_dict)
                indents.append(indent)
            else:
                if val_str.startswith('[') and val_str.endswith(']'):
                    items = []
                    for x in val_str[1:-1].split(','):
                        x_str = x.strip()
                        if not x_str:
                            continue
                        if any(c.isdigit() for c in x_str) and '.' in x_str:
                            items.append(float(x_str))
                        else:
                            try:
                                items.append(int(x_str))
                            except ValueError:
                                items.append(x_str.strip('"').strip("'"))
                    val = items
                elif val_str.startswith('{') and val_str.endswith('}'):
                    inner_dict = {}
                    s_dict = val_str[1:-1].strip()
                    pairs = []
                    current = []
                    in_brackets = 0
                    in_quotes = False
                    quote_char = None
                    for char in s_dict:
                        if char in ('"', "'"):
                            if not in_quotes:
                                in_quotes = True
                                quote_char = char
                            elif char == quote_char:
                                in_quotes = False
                                quote_char = None
                            current.append(char)
                        elif char == '[' and not in_quotes:
                            in_brackets += 1
                            current.append(char)
                        elif char == ']' and not in_quotes:
                            in_brackets -= 1
                            current.append(char)
                        elif char == ',' and in_brackets == 0 and not in_quotes:
                            pairs.append(''.join(current).strip())
                            current = []
                        else:
                            current.append(char)
                    if current:
                        pairs.append(''.join(current).strip())
                    for pair in pairs:
                        if not pair.strip():
                            continue
                        k_str, v_str = pair.split(':', 1)
                        k = k_str.strip().strip('"').strip("'")
                        v_str = v_str.strip()
                        if v_str.startswith('[') and v_str.endswith(']'):
                            items = []
                            for x in v_str[1:-1].split(','):
                                x_str = x.strip()
                                if not x_str:
                                    continue
                                if any(c.isdigit() for c in x_str) and '.' in x_str:
                                    items.append(float(x_str))
                                else:
                                    try:
                                        items.append(int(x_str))
                                    except ValueError:
                                        items.append(x_str.strip('"').strip("'"))
                            v = items
                        elif v_str.lower() == 'true':
                            v = True
                        elif v_str.lower() == 'false':
                            v = False
                        else:
                            try:
                                if any(c.isdigit() for c in v_str) and ('.' in v_str or 'e' in v_str):
                                    v = float(v_str)
                                else:
                                    v = int(v_str)
                            except ValueError:
                                v = v_str.strip('"').strip("'")
                        inner_dict[k] = v
                    val = inner_dict
                elif val_str.lower() == 'true':
                    val = True
                elif val_str.lower() == 'false':
                    val = False
                else:
                    try:
                        if any(c.isdigit() for c in val_str) and ('.' in val_str or 'e' in val_str):
                            val = float(val_str)
                        else:
                            val = int(val_str)
                    except ValueError:
                        val = val_str.strip('"').strip("'")
                parent[key] = val
    return data

def main():
    print("=== KRONOS PHYLUM DISCOVERY PIPELINE ===")

    # 1. Load sovereign parameters
    params_path = root_dir / "params_yaml.txt"
    print(f"Loading parameters from: {params_path}")
    config = parse_simple_yaml(params_path)

    # 2. Configure temporary sandbox directory for parquet signatures
    sandbox_db = root_dir / "data" / "signatures_sandbox"
    if sandbox_db.exists():
        shutil.rmtree(sandbox_db)
    sandbox_db.mkdir(parents=True, exist_ok=True)

    # Override database parameters for the sandbox discovery run
    config["database"]["path"] = str(sandbox_db)
    config["database"]["duckdb_path"] = str(root_dir / "data" / "signatures_sandbox.duckdb")
    config["database"]["parquet_path_pattern"] = str(sandbox_db / "**" / "*.parquet")
    # Point compact_path to sandbox so Global Ontology Compiler writes to the correct location
    sandbox_compact = str(root_dir / "data" / "signatures_sandbox_compact.parquet")
    config["database"]["compact_path"] = sandbox_compact
    
    # 3. Lower quality gates to allow full structural signature collection
    config["database"]["min_quality_score"] = 0.0
    config["miner"]["min_quality_score"] = 0.0
    config["miner"]["enable_kronos"] = False  # Ablate neural gate to focus on structural phyla
    config["miner"]["batch_size_days"] = 30  # Multi-day shard size

    print("Quality gates successfully relaxed to 0.0.")
    print("Running walk-forward miner on ETHUSDT data...")

    import miner_engine
    miner_engine.run_miner(config, "", "")

    # 4. Read signatures from Parquet sandbox db
    print("\nReading generated signatures from sandbox Parquet dataset...")
    parquet_files = list(sandbox_db.glob("**/*.parquet"))
    if not parquet_files:
        print("ERROR: No signatures were saved to Parquet! Double check veto threshold.")
        return

    df = pd.concat([pd.read_parquet(f) for f in parquet_files], ignore_index=True)
    print(f"Successfully loaded {len(df)} total signatures from the Parquet archive.")

    # 5. Extract phyla and profile them
    phylum_col = config["feature_builder"]["metadata"]["keys"]["phylum_id"]
    if phylum_col not in df.columns:
        print(f"ERROR: Phylum column '{phylum_col}' not found in the Parquet schema!")
        return

    phylum_counts = df[phylum_col].value_counts()
    print("\n=======================================================")
    print("               SIGNATURE PHYLUM DISTRIBUTION           ")
    print("=======================================================")
    print(f"{'Phylum ID':<15}{'Signature Count':<20}{'Percentage (%)':<15}")
    print("-" * 55)
    for phylum, count in phylum_counts.items():
        percentage = (count / len(df)) * 100
        # Map labels
        label = "Noise (Unclustered)" if phylum == -1.0 else f"Cluster {int(phylum)}"
        if phylum == 0.0 and len(phylum_counts) == 1:
            label = "Structural Base Phylum"
        print(f"{label:<15}{count:<20}{percentage:<15.2f}%")
    print("-" * 55)

    # 6. Profile the mean characteristics of each phylum
    print("\n================================================================================")
    print("                       STRUCTURAL SIGNATURE PROFILES BY PHYLUM                   ")
    print("================================================================================")
    
    # Key structural slots
    slots = {
        "slot_00": "Bid-Ask Absorb",
        "slot_01": "VPIN Imbalance",
        "slot_02": "Spectral Entropy",
        "slot_03": "Log Var Ratio",
        "slot_05": "Autocorr Multi",
        "slot_10": "Wick Ratio",
        "slot_15": "Sovereign Veto Score",
    }
    
    available_slots = [s for s in slots.keys() if s in df.columns]
    
    for phylum in phylum_counts.index:
        p_df = df[df[phylum_col] == phylum]
        label = "Noise (Unclustered)" if phylum == -1.0 else f"Cluster {int(phylum)}"
        if phylum == 0.0 and len(phylum_counts) == 1:
            label = "Structural Base Phylum"
            
        print(f"\n>>> Phylum: {label} (N = {len(p_df)})")
        print("-" * 60)
        print(f"{'Slot & Metric Description':<35}{'Mean Value':<15}{'Std Dev':<10}")
        print("-" * 60)
        for s in available_slots:
            mean_val = p_df[s].mean()
            std_val = p_df[s].std()
            print(f"{slots[s]:<35}{mean_val:<15.4f}{std_val:<10.4f}")
        print("-" * 60)

    # Clean up temporary sandbox database
    try:
        shutil.rmtree(sandbox_db)
        db_file = Path(config["database"]["duckdb_path"])
        if db_file.exists():
            db_file.unlink()
        print("\nSandbox database cleanup complete.")
    except Exception as exc:
        print(f"Cleanup warning: {exc}")

if __name__ == "__main__":
    main()
