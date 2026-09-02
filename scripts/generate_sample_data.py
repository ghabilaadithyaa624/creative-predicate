"""
Script to generate sample historical dataset for testing and backtesting.
"""
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backtest.historical_data import HistoricalDataLoader


def main():
    data_dir = ROOT_DIR / "data" / "historical"
    data_dir.mkdir(parents=True, exist_ok=True)
    out_path = data_dir / "sample.csv"

    print(f"Generating synthetic historical odds dataset at {out_path}...")
    df = HistoricalDataLoader.generate_synthetic_data(num_records=500, base_edge_mean=0.03)
    df.to_csv(out_path, index=False)
    print(f" Successfully saved {len(df)} historical market records.")


if __name__ == "__main__":
    main()
