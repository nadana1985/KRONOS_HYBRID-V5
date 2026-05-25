import os
import pandas as pd

def query_mid_range():
    compact_path = os.path.join("data", "signatures_compact.parquet")
    
    if not os.path.exists(compact_path):
        print("[ERROR] Compacted Parquet file not found!")
        return

    df = pd.read_parquet(compact_path)
    
    # Filter for MFE between 20% and 50%
    filtered_df = df[(df["mfe"] >= 0.20) & (df["mfe"] <= 0.50)].copy()
    
    total_found = len(filtered_df)
    
    print("=========================================================")
    print("             [REPORT] KRONOS V5 SIGNATURES (20% - 50% MFE)")
    print("=========================================================")
    print(f"Total Signatures Found: {total_found} events\n")

    if total_found == 0:
        print("[INFO] No historical events found within the 20% - 50% MFE range.")
        print("=========================================================")
        return

    # Sort chronologically
    filtered_df = filtered_df.sort_values(by="timestamp")

    print("| Timestamp | Combined Quality | Veto Score | Neural Conviction | Forward MFE | Forward MAE | Recovery Factor |")
    print("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
    
    for _, row in filtered_df.iterrows():
        print(f"| {row['timestamp']} | {row['slot_31']:.4f} | {row['slot_15']:.4f} | {row['neural_conviction']:.4f} | {row['mfe']:7.4%} | {row['mae']:7.4%} | {row['recovery_factor']:15.4f} |")
        
    print("=========================================================")

if __name__ == "__main__":
    query_mid_range()
