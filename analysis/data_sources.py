"""
Unified data sources interface for sportsbooks and prediction platforms.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from analysis.scraper import MarketData, MarketScraper


class BaseDataSource(ABC):
    @abstractmethod
    def fetch_markets(self) -> List[MarketData]:
        pass


class PolymarketSource(BaseDataSource):
    def __init__(self):
        self.scraper = MarketScraper()

    def fetch_markets(self) -> List[MarketData]:
        return self.scraper.scrape_polymarket()


class SimulatedSportsSource(BaseDataSource):
    def __init__(self):
        self.scraper = MarketScraper()

    def fetch_markets(self) -> List[MarketData]:
        return self.scraper.generate_mock_markets(count=5)


class AggregatedMarketFeed:
    """
    Collects and unifies data across all registered data sources.
    """

    def __init__(self, sources: Optional[List[BaseDataSource]] = None):
        self.sources: List[BaseDataSource] = sources or [PolymarketSource(), SimulatedSportsSource()]

    def poll_all_markets(self) -> List[MarketData]:
        all_markets = []
        for source in self.sources:
            try:
                markets = source.fetch_markets()
                all_markets.extend(markets)
            except Exception:
                pass
        return all_markets
