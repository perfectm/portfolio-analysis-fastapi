import sys
import pandas as pd
import os

def main():
    if len(sys.argv) < 2:
        print("Usage: python inspect_parquet.py <portfolio_id>")
        sys.exit(1)
    portfolio_id = sys.argv[1]
    parquet_path = os.path.join('uploads', 'portfolios', f'{portfolio_id}.parquet')
    if not os.path.exists(parquet_path):
        print(f"Parquet file not found: {parquet_path}")
        sys.exit(1)
    df = pd.read_parquet(parquet_path)
    print(f"[inspect_parquet] Columns: {list(df.columns)}")
    print(f"[inspect_parquet] Head:\n{df.head()}")

if __name__ == "__main__":
    main() 