"""
Historical dataset loader and synthetic dataset generator for backtesting.
"""
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


class HistoricalDataLoader:
    """
    Loads and preprocesses historical odds and results datasets.
    """

    @staticmethod
    def load_csv(filepath: str | Path) -> pd.DataFrame:
        df = pd.read_csv(filepath)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp").reset_index(drop=True)
        return df

    @staticmethod
    def generate_synthetic_data(
        num_records: int = 500,
        start_date: Optional[datetime] = None,
        base_edge_mean: float = 0.03,
    ) -> pd.DataFrame:
        """
        Generates a realistic historical dataset with true probabilities,
        market odds with vig, and realized win/loss outcomes.
        """
        start = start_date or (datetime.now() - timedelta(days=90))
        records: List[Dict] = []

        events_pool = [
            ("Lakers vs Warriors", "basketball"),
            ("Celtics vs Bucks", "basketball"),
            ("Chiefs vs Ravens", "football"),
            ("Eagles vs Cowboys", "football"),
            ("BTC > $100K by month-end", "crypto"),
            ("ETH Flipping SOL", "crypto"),
            ("Fed cuts 25bps", "politics"),
            ("US Unemployment drops", "politics"),
        ]

        np.random.seed(42)
        for i in range(num_records):
            timestamp = start + timedelta(hours=i * 4)
            ev_name, cat = events_pool[i % len(events_pool)]

            # Underlying true win probability between 0.30 and 0.75
            true_prob = float(np.random.uniform(0.35, 0.70))

            # Market implied probability with some noise & vig
            noise = float(np.random.normal(-base_edge_mean, 0.05))
            market_implied = np.clip(true_prob + noise, 0.20, 0.85)

            # Add 4% bookmaker vig
            decimal_odds = round(1.0 / (market_implied * 1.04), 2)

            # Realized outcome based on true probability
            won = bool(np.random.random() < true_prob)

            records.append({
                "timestamp": timestamp.isoformat(),
                "event": f"{ev_name} #{i+1}",
                "category": cat,
                "selection": "Selection A",
                "odds": max(decimal_odds, 1.10),
                "true_prob": round(true_prob, 4),
                "implied_prob": round(1.0 / decimal_odds, 4),
                "result": won,
                "volume": int(np.random.uniform(10000, 500000)),
            })

        return pd.DataFrame(records)
