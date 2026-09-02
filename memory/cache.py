"""
Fast in-memory TTL caching layer.
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional


class CacheStore:
    def __init__(self, default_ttl_seconds: int = 300):
        self.default_ttl = default_ttl_seconds
        self._store: Dict[str, Dict[str, Any]] = {}

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None):
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        expire_at = datetime.now() + timedelta(seconds=ttl)
        self._store[key] = {
            "value": value,
            "expire_at": expire_at,
        }

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if not entry:
            return None
        if datetime.now() > entry["expire_at"]:
            del self._store[key]
            return None
        return entry["value"]

    def clear(self):
        self._store.clear()
