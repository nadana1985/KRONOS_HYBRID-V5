import duckdb
from pathlib import Path

db_path = Path("g:/KRONOS HYBRID/data/signatures.duckdb")
print(f"Connecting to production database at: {db_path}")

con = duckdb.connect(str(db_path))

# Check real number of signatures in database
total_signatures = con.execute("SELECT COUNT(*) FROM signatures").fetchone()[0]
print(f"Total signatures in signatures table: {total_signatures}")

# Check unique values in slot_28 (Phylum ID)
try:
    unique_phyla = con.execute("SELECT slot_28, COUNT(*) as count FROM signatures GROUP BY slot_28 ORDER BY count DESC").fetchall()
    print(f"\nUnique values in slot_28 across the entire database (Total unique: {len(unique_phyla)}):")
    for row in unique_phyla[:30]: # Print top 30
        phylum_id = row[0]
        count = row[1]
        pct = (count / total_signatures) * 100
        label = "Noise (-1.0)" if phylum_id == -1.0 else f"Phylum {phylum_id}"
        print(f"  {label:<15}: {count:<8} ({pct:.2f}%)")
except Exception as e:
    print(f"Error querying slot_28: {e}")
