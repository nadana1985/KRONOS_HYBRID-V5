import os
from pathlib import Path
import json
import pandas as pd

# Let's search under G:/ for any files matching archetype_registry_v1.json or similar
target_files = []
possible_roots = [Path("g:/"), Path("c:/Users/perum/.gemini/antigravity")]

print("Searching for archetype registry or summaries...")
for root_path in possible_roots:
    try:
        for r, d, f in os.walk(str(root_path)):
            # Don't recurse into .git, .venv, env etc. to save time
            if any(p in r for p in [".git", ".venv", "__pycache__", "node_modules"]):
                continue
            for filename in f:
                if "archetype" in filename or "phylum" in filename or "phyla" in filename:
                    p = Path(r) / filename
                    print(f"Found match: {p}")
                    target_files.append(p)
    except Exception as e:
        print(f"Error scanning {root_path}: {e}")

# If we found any archetype_registry_v1.json, let's read it
for p in target_files:
    if p.suffix == ".json" and "registry" in p.name:
        try:
            with open(p, "r") as f:
                data = json.load(f)
            print(f"\nRegistry contents of {p.name}:")
            print(json.dumps(data, indent=2))
        except Exception as e:
            print(f"Error reading {p}: {e}")
    elif p.suffix == ".md" and "summary" in p.name:
        try:
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()
            print(f"\nSummary file {p.name} content:")
            print(content[:2000]) # First 2000 chars
        except Exception as e:
            print(f"Error reading {p}: {e}")
    elif p.suffix == ".parquet" and "profiles" in p.name:
        try:
            df = pd.read_parquet(p)
            print(f"\nParquet profiles of {p.name}:")
            print(df.to_string())
        except Exception as e:
            print(f"Error reading {p}: {e}")
