import sys
import re
from pathlib import Path
import pandas as pd
import numpy as np

# Add root directory to sys.path to allow imports
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from structural_engine import compute_slots_sovereign, compute_veto_composite

def parse_simple_yaml(filepath):
    data = {}
    stack = [data]
    indents = [-1]
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            # strip comments
            line = line.split('#')[0]
            stripped = line.strip()
            if not stripped:
                continue
            
            # calculate indentation
            indent = len(line) - len(line.lstrip())
            
            # resolve hierarchy based on indentation
            while indent <= indents[-1]:
                stack.pop()
                indents.pop()
                
            parent = stack[-1]
            
            # check if list item
            if stripped.startswith('-'):
                val_str = stripped[1:].strip()
                if any(c.isdigit() for c in val_str) and ('.' in val_str or 'e' in val_str):
                    val = float(val_str)
                else:
                    try:
                        val = int(val_str)
                    except ValueError:
                        val = val_str.strip('"').strip("'")
                
                # Convert the stack[-1] from empty dict to list if needed
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
            
            # match key: value or key:
            match = re.match(r'^([^:]+):\s*(.*)$', stripped)
            if not match:
                continue
            
            key = match.group(1).strip()
            val_str = match.group(2).strip()
            
            if val_str == "":
                # new section
                if key in parent and isinstance(parent[key], dict):
                    new_dict = parent[key]
                else:
                    new_dict = {}
                    parent[key] = new_dict
                stack.append(new_dict)
                indents.append(indent)
            else:
                # key-value pair
                # parse value
                if val_str.startswith('[') and val_str.endswith(']'):
                    # parse list
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
                    # parse inline dictionary
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

def test_structural_sovereign_core():
    print("=== KRONOS V5 STRUCTURAL SOVEREIGN CORE TEST ===")
    
    # 1. Load config
    config_path = root_dir / "params_yaml.txt"
    print(f"Loading sovereign parameters from: {config_path}")
    cfg = parse_simple_yaml(config_path)
    
    print("Parsed root keys:", list(cfg.keys()))
    if "feature_builder" in cfg:
        print("feature_builder keys:", list(cfg["feature_builder"].keys()))
        print("slot_order parsed:", cfg["feature_builder"]["structural"]["slot_order"])
        
    # 2. Load raw 5m ETH data
    data_path = root_dir / "data" / "raw" / "ethusdt_5m_extension_ohlcv.parquet"
    print(f"Loading raw candlestick data from: {data_path}")
    df = pd.read_parquet(data_path)
    print(f"Candlestick rows loaded: {len(df)}")
    
    # 3. Create mock trade micro-structure data aligned to the candlestick index
    np.random.seed(cfg["reproducibility"]["random_seed"])
    mock_trades = pd.DataFrame(index=df.index)
    mock_trades["buy_vol"] = df["volume"] * np.random.uniform(0.3, 0.7, len(df))
    mock_trades["sell_vol"] = df["volume"] - mock_trades["buy_vol"]
    
    # 4. Compute slots 0-14 causally using structural_engine
    print("Computing structural slots 0-14...")
    structural_df = compute_slots_sovereign(df, mock_trades, cfg["feature_builder"]["structural"], cfg)
    print(f"Structural slot matrix shape: {structural_df.shape}")
    
    # 5. Compute Slot 15 veto composite
    print("Computing Slot 15 veto composite...")
    veto_composite = compute_veto_composite(
        structural_df,
        cfg["feature_builder"]["structural"]["slot_15"],
        cfg["reproducibility"]["constants"]
    )
    
    # 6. Check veto triggers
    veto_threshold = cfg["feature_builder"]["structural"]["veto_threshold"]
    veto_triggers = (veto_composite >= veto_threshold).sum()
    
    print("\n--- Test Results ---")
    print(f"Slot 15 Score Range: Min={veto_composite.min():.4f}, Max={veto_composite.max():.4f}, Mean={veto_composite.mean():.4f}")
    print(f"Veto Threshold: {veto_threshold}")
    print(f"Total Reversal Signatures Veto-Passed: {veto_triggers} / {len(df)} ({veto_triggers/len(df)*100:.2f}%)")
    
    # Assert slot 15 veto fires independently of any neural layer
    assert veto_triggers > 0, "Error: Veto composite never triggered! Check slot weights and signals."
    print("SUCCESS: The sovereign structural veto fires independently of the neural gate!")

if __name__ == "__main__":
    test_structural_sovereign_core()
