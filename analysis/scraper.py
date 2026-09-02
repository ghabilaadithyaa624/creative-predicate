"""
Web scraping and prediction market ingestion modules.
"""
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from loguru import logger


@dataclass
class MarketData:
    event_name: str
    category: str
    start_time: str
    odds_home: float
    odds_away: float
    odds_draw: Optional[float] = None
    volume: Optional[float] = None
    source: str = "polymarket"
    extra_metadata: Dict[str, Any] = field(default_factory=dict)


class MarketScraper:
    """
    Perception module: extracts live or simulated prediction and sports markets.
    """

    def __init__(self, timeout: float = 1.5):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def scrape_polymarket(self) -> List[MarketData]:
        """
        Attempts to query Polymarket Gamma API or public endpoints,
        with automated synthetic fallback for robust operation.
        """
        markets: List[MarketData] = []
        try:
            # Try Polymarket Gamma API
            api_url = "https://gamma-api.polymarket.com/events?limit=10&active=true&closed=false"
            res = requests.get(api_url, headers=self.headers, timeout=self.timeout)
            if res.status_code == 200:
                data = res.json()
                for item in data:
                    title = item.get("title", "Unknown Event")
                    markets_list = item.get("markets", [])
                    if markets_list:
                        m = markets_list[0]
                        outcome_prices = m.get("outcomePrices", ["0.5", "0.5"])
                        try:
                            yes_price = float(outcome_prices[0]) if len(outcome_prices) > 0 else 0.5
                            no_price = float(outcome_prices[1]) if len(outcome_prices) > 1 else 0.5
                            odds_yes = round(1.0 / max(yes_price, 0.01), 2)
                            odds_no = round(1.0 / max(no_price, 0.01), 2)
                        except (ValueError, TypeError, ZeroDivisionError):
                            odds_yes, odds_no = 2.0, 2.0

                        vol = float(item.get("volume", 0) or 0)
                        cat = self._categorize_title(title)
                        markets.append(MarketData(
                            event_name=title,
                            category=cat,
                            start_time=item.get("endDate", datetime.now().isoformat()),
                            odds_home=odds_yes,
                            odds_away=odds_no,
                            volume=vol,
                            source="polymarket",
                            extra_metadata={"market_id": m.get("id"), "slug": item.get("slug")}
                        ))
        except Exception as e:
            logger.debug(f"Live Polymarket API query returned: {e}. Generating simulated feed.")

        # If external API is unreachable or returned empty, generate realistic markets
        if not markets:
            markets = self.generate_mock_markets(count=6)

        return markets

    def _categorize_title(self, title: str) -> str:
        title_lower = title.lower()
        if any(k in title_lower for k in ["nba", "basketball", "lakers", "celtics"]):
            return "basketball"
        if any(k in title_lower for k in ["nfl", "super bowl", "football", "quarterback"]):
            return "football"
        if any(k in title_lower for k in ["election", "president", "trump", "biden", "senate", "fed"]):
            return "politics"
        if any(k in title_lower for k in ["btc", "bitcoin", "eth", "ethereum", "crypto", "solana"]):
            return "crypto"
        return "general"

    def generate_mock_markets(self, count: int = 5) -> List[MarketData]:
        """
        Creates realistic synthetic prediction markets for simulation & tests.
        """
        templates = [
            ("Lakers vs Warriors - Winner", "basketball", 1.85, 2.05, 150000.0),
            ("BTC to break $100k before Q4", "crypto", 2.30, 1.65, 850000.0),
            ("Federal Reserve cuts rate at next FOMC", "politics", 1.45, 2.80, 1200000.0),
            ("Chiefs vs 49ers - Regular Season", "football", 1.95, 1.95, 320000.0),
            ("OpenAI releases GPT-5 in 2026", "tech", 2.10, 1.80, 450000.0),
            ("Ethereum market cap exceeds $600B", "crypto", 2.60, 1.55, 290000.0),
        ]

        selected = templates[:count] if count <= len(templates) else templates
        results = []
        for name, cat, yes_odds, no_odds, vol in selected:
            # Add small random fluctuation
            drift = random.uniform(-0.05, 0.05)
            y_odds = max(1.10, round(yes_odds + drift, 2))
            n_odds = max(1.10, round(no_odds - drift, 2))

            results.append(MarketData(
                event_name=name,
                category=cat,
                start_time=datetime.now().isoformat(),
                odds_home=y_odds,
                odds_away=n_odds,
                volume=vol * random.uniform(0.8, 1.2),
                source="polymarket_simulated",
            ))
        return results
