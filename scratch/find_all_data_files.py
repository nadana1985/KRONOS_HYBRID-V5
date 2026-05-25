import os
from pathlib import Path

root = Path("g:/KRONOS try 13may2026/ETHreverseEngineer/")
print(f"Scanning files in {root}...")
for r, d, f in os.walk(str(root)):
    # Don't show system/cache dirs
    if any(p in r for p in [".git", ".venv", "__pycache__", "node_modules", ".pytest_cache"]):
        continue
    for filename in f:
        p = Path(r) / filename
        # Print path and size of any json, md, parquet, py, txt file under data or KRONOS_V5
        if p.suffix in [".json", ".parquet", ".md", ".txt"] or "registry" in filename.lower() or "archetype" in filename.lower():
            rel = p.relative_to(root)
            print(f"  {rel} ({p.stat().st_size} bytes)")
