from pathlib import Path
import json

paths_to_check = [
    Path("g:/KRONOS/kronos_snapshot_full/kronos_mining/archetypes/"),
    Path("g:/KRONOS/kronos_snapshot_full/kronos_mining/"),
    Path("g:/KRONOS/"),
    Path("g:/KRONOS try 13may2026/ETHreverseEngineer/"),
]

for p in paths_to_check:
    print(f"Checking path: {p}")
    if p.exists():
        print(f"  Exists! Contents:")
        try:
            for child in p.iterdir():
                print(f"    {child.name} ({'Dir' if child.is_dir() else 'File'})")
        except Exception as e:
            print(f"    Error reading contents: {e}")
    else:
        print("  Does not exist.")

# If registry exists, let's load it and dump it
reg_path = Path("g:/KRONOS/kronos_snapshot_full/kronos_mining/archetypes/archetype_registry_v1.json")
if reg_path.exists():
    print(f"\nLoading registry from {reg_path}...")
    try:
        with open(reg_path, "r") as f:
            data = json.load(f)
        # Group phyla by archetype
        by_archetype = {}
        for phylum, arch in data.items():
            by_archetype.setdefault(arch, []).append(phylum)
        print("Archetypes and their mapped Phylum IDs:")
        for arch, phyla in by_archetype.items():
            print(f"  {arch}: {phyla}")
    except Exception as e:
        print(f"  Error: {e}")
