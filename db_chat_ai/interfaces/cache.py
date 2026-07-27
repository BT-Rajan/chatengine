"""
interfaces/cache.py — optional response caching.

NoCache (the default) is a complete no-op — nothing is allocated, nothing
imported. RedisCache only imports the `redis` package inside its own
constructor, so it never becomes a hard dependency: if the cache feature
is off, or set to "memory", `redis` is never imported at all.
"""

from abc import ABC, abstractmethod
from collections import OrderedDict
from typing import Any


class Cache(ABC):
    @abstractmethod
    def get(self, key: str) -> Any:
        ...

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        ...


class NoCache(Cache):
    """Default. Every get() misses, every set() is discarded."""

    def get(self, key: str) -> Any:
        return None

    def set(self, key: str, value: Any) -> None:
        return None


class MemoryCache(Cache):
    """Simple in-process LRU cache. No external dependency."""

    def __init__(self, max_size: int = 256):
        self.max_size = max_size
        self._store: OrderedDict[str, Any] = OrderedDict()

    def get(self, key: str) -> Any:
        if key not in self._store:
            return None
        self._store.move_to_end(key)
        return self._store[key]

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value
        self._store.move_to_end(key)
        if len(self._store) > self.max_size:
            self._store.popitem(last=False)


class RedisCache(Cache):
    """Backed by Redis. `redis` is only imported here, at construction
    time — so it's only ever required when CACHE["type"] == "redis" AND
    FEATURES["cache"] is True. Any other configuration never touches it."""

    def __init__(self, url: str = "redis://localhost:6379/0", ttl_seconds: int = 3600):
        try:
            import redis
        except ImportError as e:
            raise RuntimeError(
                "The 'redis' package is required for RedisCache. "
                "Install it with `pip install redis`, or set "
                "CACHE['type'] = 'memory' to use MemoryCache instead."
            ) from e
        self._client = redis.Redis.from_url(url)
        self._ttl = ttl_seconds

    def get(self, key: str) -> Any:
        value = self._client.get(key)
        return value.decode() if value is not None else None

    def set(self, key: str, value: Any) -> None:
        self._client.set(key, value, ex=self._ttl)
