"""
Real-time WebSocket feeds and multi-exchange data feeds manager.
Includes cross-exchange real-time arbitrage detection.
"""
import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
import json
from typing import Callable, Dict, List, Optional, Any
from loguru import logger

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False


@dataclass
class MarketUpdate:
    exchange: str
    market_id: str
    event_name: str
    odds_home: float
    odds_away: float
    volume: float
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class WebSocketFeedManager:
    """
    Manages live and simulated data streams from multiple prediction exchanges.
    """
    def __init__(self):
        self.subscribers: Dict[str, List[Callable[[MarketUpdate], Any]]] = defaultdict(list)
        self.running = False
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.prices: Dict[str, Dict[str, MarketUpdate]] = defaultdict(dict)

    def subscribe(self, exchange: str, callback: Callable[[MarketUpdate], Any]):
        self.subscribers[exchange].append(callback)

    async def ingest_update(self, update: MarketUpdate):
        self.prices[update.event_name][update.exchange] = update
        await self.message_queue.put(update)
        for cb in self.subscribers.get(update.exchange, []):
            try:
                res = cb(update)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.error(f"Feed subscriber error: {e}")

    async def simulate_live_tick(self, count: int = 3):
        """Simulates incoming high-frequency market orderbook ticks."""
        import random
        events = [
            ("Lakers vs Warriors - Winner", 1.85, 2.05),
            ("BTC to break $100k before Q4", 2.30, 1.65),
            ("Federal Reserve cuts rate at next FOMC", 1.45, 2.80),
        ]
        exchanges = ["polymarket", "betfair", "dex_prediction"]
        
        for name, yes_base, no_base in events[:count]:
            for ex in exchanges:
                drift = random.uniform(-0.06, 0.06)
                upd = MarketUpdate(
                    exchange=ex,
                    market_id=f"{ex}_{name}",
                    event_name=name,
                    odds_home=max(1.10, round(yes_base + drift, 2)),
                    odds_away=max(1.10, round(no_base - drift, 2)),
                    volume=float(random.randint(50000, 1000000)),
                )
                await self.ingest_update(upd)


class ArbitrageDetector:
    """
    Detects cross-exchange pricing discrepancies and risk-free arbitrage conditions.
    """
    def __init__(self, feed_manager: WebSocketFeedManager):
        self.feeds = feed_manager
        self.opportunities: List[Dict[str, Any]] = []

    def scan_all_for_arbitrage(self) -> List[Dict[str, Any]]:
        arbs = []
        for event_name, exchange_dict in self.feeds.prices.items():
            if len(exchange_dict) < 2:
                continue

            # Best home odds and best away odds across any exchange
            best_home = max(exchange_dict.values(), key=lambda x: x.odds_home)
            best_away = max(exchange_dict.values(), key=lambda x: x.odds_away)

            inv_sum = (1.0 / best_home.odds_home) + (1.0 / best_away.odds_away)
            if inv_sum < 1.0:
                profit_pct = round(((1.0 - inv_sum) / inv_sum) * 100.0, 2)
                arb = {
                    "event": event_name,
                    "buy_home_exchange": best_home.exchange,
                    "buy_home_odds": best_home.odds_home,
                    "buy_away_exchange": best_away.exchange,
                    "buy_away_odds": best_away.odds_away,
                    "profit_margin_pct": profit_pct,
                    "timestamp": datetime.now().isoformat(),
                }
                arbs.append(arb)
                self.opportunities.append(arb)

        return arbs
