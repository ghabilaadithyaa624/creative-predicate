"""Feeds module initialization."""
from feeds.websocket_manager import ArbitrageDetector, MarketUpdate, WebSocketFeedManager

__all__ = [
    "WebSocketFeedManager",
    "MarketUpdate",
    "ArbitrageDetector",
]
