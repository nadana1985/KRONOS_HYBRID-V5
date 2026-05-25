import os
import pandas as pd

def query_monster():
    compact_path = os.path.join("data", "signatures_compact.parquet")
    df = pd.read_parquet(compact_path)
    
    # Locate the specific May 7, 2025 P99 monster impulse row
    df["timestamp_str"] = df["timestamp"].astype(str)
    row = df[df["timestamp_str"].str.contains("2025-05-07 20:40")].iloc[0]
    
    print("=========================================================")
    print("             [REPORT] MONSTER IMPULSE DETAIL (MAY 7, 2025)")
    print("=========================================================")
    print(f"Timestamp:       {row['timestamp']}")
    print(f"Quality Score:   {row['slot_31']:.4f}")
    print(f"Veto Score:      {row['slot_15']:.4f}")
    print(f"Neural Conviction:{row['neural_conviction']:.4f}")
    print(f"Forward MFE:     {row['mfe']:.4%}")
    print(f"Forward MAE:     {row['mae']:.4%}")
    print(f"Recovery Factor: {row['recovery_factor']:.4f}")
    print("=========================================================")

if __name__ == "__main__":
    query_monster()
