"""
Web scraping and prediction market ingestion modules.
"""
import json
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

    @staticmethod
    def _parse_outcome_prices(raw: Any) -> Optional[List[float]]:
        """
        Normalise Gamma's ``outcomePrices`` into a list of floats.

        The live API returns this field as a *JSON-encoded string*, e.g.
        ``'["0.945", "0.055"]'``, not as a list. Indexing that string yields
        the character ``'['``, so a naive ``float(prices[0])`` raises and any
        caller that swallows the error silently substitutes a fabricated
        50/50 price. Both the string and list forms are accepted here.

        Returns None when the field cannot be parsed, so the caller can skip
        the market rather than invent a price for it.
        """
        if raw is None:
            return None

        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (ValueError, TypeError):
                return None

        if not isinstance(raw, (list, tuple)) or len(raw) < 2:
            return None

        try:
            prices = [float(p) for p in raw[:2]]
        except (ValueError, TypeError):
            return None

        # A genuine binary market must have strictly positive prices that
        # roughly complete. Anything else is a resolved/degenerate market.
        if any(p <= 0.0 or p >= 1.0 for p in prices):
            return None
        if not 0.90 <= sum(prices) <= 1.10:
            return None

        return prices

    def scrape_polymarket(self, allow_synthetic_fallback: bool = True) -> List[MarketData]:
        """
        Query the Polymarket Gamma API for live binary markets.

        Parameters
        ----------
        allow_synthetic_fallback:
            When True (default) an unreachable API or an empty result yields a
            simulated feed so demos and offline tests still run. Set to False
            to get an empty list instead -- required if you need to be certain
            you are looking at real prices, since synthetic markets are
            otherwise indistinguishable at a glance.
        """
        markets: List[MarketData] = []
        try:
            api_url = "https://gamma-api.polymarket.com/events?limit=10&active=true&closed=false"
            res = requests.get(api_url, headers=self.headers, timeout=self.timeout)
            if res.status_code == 200:
                data = res.json()
                if not isinstance(data, list):
                    data = data.get("data", []) if isinstance(data, dict) else []

                for item in data:
                    title = item.get("title") or item.get("question") or "Unknown Event"
                    markets_list = item.get("markets") or []
                    if not markets_list:
                        continue

                    m = markets_list[0]
                    prices = self._parse_outcome_prices(m.get("outcomePrices"))
                    if prices is None:
                        # Never invent a price. A market we cannot read is a
                        # market we must not trade.
                        logger.warning(
                            f"Skipping Polymarket market '{title}': unreadable "
                            f"outcomePrices={m.get('outcomePrices')!r}"
                        )
                        continue

                    yes_price, no_price = prices
                    odds_yes = round(1.0 / yes_price, 4)
                    odds_no = round(1.0 / no_price, 4)

                    try:
                        vol = float(item.get("volume") or m.get("volume") or 0.0)
                    except (ValueError, TypeError):
                        vol = 0.0

                    markets.append(MarketData(
                        event_name=title,
                        category=self._categorize_title(title),
                        start_time=item.get("endDate") or datetime.now().isoformat(),
                        odds_home=odds_yes,
                        odds_away=odds_no,
                        volume=vol,
                        source="polymarket",
                        extra_metadata={
                            "market_id": m.get("id"),
                            "slug": item.get("slug"),
                            "yes_price": yes_price,
                            "no_price": no_price,
                        },
                    ))
            else:
                logger.warning(
                    f"Polymarket Gamma API returned HTTP {res.status_code}."
                )
        except Exception as e:
            logger.warning(f"Live Polymarket API query failed: {e}")

        if not markets:
            if not allow_synthetic_fallback:
                logger.warning("No live markets available and fallback disabled.")
                return []
            logger.info("No live markets available; generating simulated feed.")
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
