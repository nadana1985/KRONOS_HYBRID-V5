"""
KRONOS Sovereign Config Loader
==============================
Zero-dependency parser for params_yaml.txt ensuring absolute deterministic reproducibility.
"""
import os
import re
from typing import Dict

# Pillar 1 Privacy Compliance: Scopes local .env file fallback scoping automatically
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def load_sovereign_config(path: str = "params_yaml.txt") -> Dict:
    """Reads and parses params_yaml.txt into a nested dictionary structure."""
    data = {}
    stack = [data]
    indents = [-1]
    
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            # Strip comments safely (do not split on '#' inside quotes)
            in_quotes = False
            quote_char = None
            comment_idx = None
            for idx, char in enumerate(line):
                if char in ('"', "'"):
                    if not in_quotes:
                        in_quotes = True
                        quote_char = char
                    elif char == quote_char:
                        if idx > 0 and line[idx - 1] == '\\':
                            pass
                        else:
                            in_quotes = False
                            quote_char = None
                elif char == '#' and not in_quotes:
                    comment_idx = idx
                    break
            if comment_idx is not None:
                line = line[:comment_idx]
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
                try:
                    if any(c.isdigit() for c in val_str) and '.' in val_str:
                        val = float(val_str)
                    else:
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
                        try:
                            if any(c.isdigit() for c in x_str) and '.' in x_str:
                                items.append(float(x_str))
                            else:
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
                                try:
                                    if any(c.isdigit() for c in x_str) and '.' in x_str:
                                        items.append(float(x_str))
                                    else:
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
