from pathlib import Path
import re

wiki_path = Path("g:/KRONOS try 13may2026/ETHreverseEngineer/wiki/reversal_signatures_wiki_v45.md")
if not wiki_path.exists():
    wiki_path = Path("g:/KRONOS try 13may2026/ETHreverseEngineer/reversal_signatures_wiki_v45.md")

print(f"Reading wiki file from: {wiki_path}")

try:
    with open(wiki_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    print(f"File loaded successfully. Length: {len(content)} chars.")
    
    # Search for our terms case-insensitively
    for term in ["Alpha Trend Builder", "Compression Snap"]:
        matches = [m.start() for m in re.finditer(re.escape(term), content, re.IGNORECASE)]
        print(f"\nFound {len(matches)} matches for '{term}':")
        for i, idx in enumerate(matches[:5]):
            start = max(0, idx - 100)
            end = min(len(content), idx + 400)
            print(f"Match {i+1} at index {idx}:")
            print(f"...{content[start:end]}...\n")
            
except Exception as e:
    print(f"Error: {e}")
