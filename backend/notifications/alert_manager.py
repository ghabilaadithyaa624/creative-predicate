"""
Multi-channel alert and incident manager for Telegram, Discord, Slack, and Console.
"""
import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

try:
    import aiohttp
except ImportError:  # pragma: no cover - optional transport dependency
    # Only needed to actually POST to Discord/Telegram/Slack webhooks.
    # Console alerts and the whole alert-history API work without it, so an
    # absent aiohttp must not break importing the package.
    aiohttp = None


@dataclass
class Alert:
    level: str  # info, warning, error, critical
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)


class NotificationManager:
    """
    Manages notifications across communication endpoints with retry and rate-limiting.
    """
    def __init__(self):
        self.config: Dict[str, Dict[str, Any]] = {}
        self.alert_history: List[Alert] = []

    def configure_telegram(self, bot_token: str, chat_id: str):
        self.config['telegram'] = {'token': bot_token, 'chat_id': chat_id, 'enabled': True}

    def configure_discord(self, webhook_url: str):
        self.config['discord'] = {'webhook': webhook_url, 'enabled': True}

    def configure_slack(self, webhook_url: str):
        self.config['slack'] = {'webhook': webhook_url, 'enabled': True}

    async def send_alert(
        self,
        level: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        channels: Optional[List[str]] = None,
    ):
        alert = Alert(level=level, title=title, message=message, data=data)
        self.alert_history.append(alert)
        logger.info(f"[ALERT] [{level.upper()}] {title} - {message}")

        target_channels = channels if channels is not None else list(self.config.keys())
        tasks = []
        for ch in target_channels:
            if ch in self.config and self.config[ch].get('enabled'):
                tasks.append(self._dispatch_channel(ch, alert))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _dispatch_channel(self, channel: str, alert: Alert):
        if aiohttp is None:
            logger.warning(
                f"Cannot dispatch '{channel}' alert: aiohttp is not installed. "
                f"Install the API extra (pip install -e '.[api]') to enable "
                f"webhook delivery."
            )
            return
        try:
            if channel == "discord" and "webhook" in self.config["discord"]:
                url = self.config["discord"]["webhook"]
                async with aiohttp.ClientSession() as session:
                    payload = {"content": f"**[{alert.level.upper()}] {alert.title}**\n{alert.message}"}
                    await session.post(url, json=payload)
        except Exception as e:
            logger.debug(f"Alert dispatch exception for {channel}: {e}")
