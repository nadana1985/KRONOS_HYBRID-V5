import pandas as pd

def summarize_signatures():
    compact_path = "data/signatures_compact.parquet"
    df = pd.read_parquet(compact_path)
    
    total_signatures = len(df)
    signatures_10_plus = df[df['mfe'] >= 0.10]
    count_10_plus = len(signatures_10_plus)
    
    print(f"TOTAL_SIGNATURES: {total_signatures}")
    print(f"COUNT_10_PERCENT_AND_ABOVE: {count_10_plus}")
    
    print("\nTOP 10 HIGHEST YIELD SIGNATURES:")
    top_10 = df.sort_values(by='mfe', ascending=False).head(10)
    for idx, (_, row) in enumerate(top_10.iterrows(), 1):
        print(f"Rank {idx}: Timestamp: {row['timestamp']} | MFE: {row['mfe']*100:.4f}% | MAE: {row['mae']*100:.4f}% | Recovery: {row['recovery_factor']:.4f} | Quality: {row['slot_31']:.4f}")

if __name__ == "__main__":
    summarize_signatures()
