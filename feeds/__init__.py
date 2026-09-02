"""Feeds module initialization."""
from feeds.websocket_manager import WebSocketFeedManager, MarketUpdate, ArbitrageDetector

__all__ = [
    "WebSocketFeedManager",
    "MarketUpdate",
    "ArbitrageDetector",
]
