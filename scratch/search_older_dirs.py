import os
from pathlib import Path

root = Path("g:/KRONOS try 13may2026/ETHreverseEngineer/")
terms = ["Alpha Trend Builder", "Compression Snap", "phylum", "phyla"]

print(f"Searching for terms in {root}...")
for r, d, f in os.walk(str(root)):
    if any(p in r for p in [".git", ".venv", "__pycache__", "node_modules"]):
        continue
    for filename in f:
        p = Path(r) / filename
        if p.suffix in [".md", ".json", ".txt", ".py"]:
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as file:
                    content = file.read()
                for term in terms[:2]:
                    if term in content:
                        print(f"Found '{term}' in {p.relative_to(root)}")
                        # Print lines containing the term
                        lines = content.splitlines()
                        for i, line in enumerate(lines):
                            if term in line:
                                print(f"  Line {i+1}: {line.strip()[:150]}")
            except Exception as e:
                pass
