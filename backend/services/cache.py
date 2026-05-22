"""
backend/services/cache.py
Simple caching layer: in-memory (default) or Redis if REDIS_URL is set.

Usage:
    from backend.services.cache import get_cache
    cache = get_cache()

    await cache.set("key", value, ttl=3600)
    result = await cache.get("key")
    await cache.delete("key")
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger("economic_agent.cache")


def make_cache_key(prefix: str, **kwargs) -> str:
    """Deterministic cache key from a prefix + kwargs dict."""
    payload = json.dumps(kwargs, sort_keys=True, default=str)
    digest = hashlib.sha256(payload.encode()).hexdigest()[:12]
    return f"{prefix}:{digest}"


# ── Abstract interface ────────────────────────────────────────────────────────

class BaseCache(ABC):
    @abstractmethod
    async def get(self, key: str) -> Any | None: ...

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int | None = None) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    async def clear(self) -> None: ...


# ── In-memory implementation ──────────────────────────────────────────────────

class InMemoryCache(BaseCache):
    """Thread-safe in-memory cache with TTL support. Good for dev / single-worker."""

    def __init__(self, default_ttl: int = 3600):
        self._store: dict[str, tuple[Any, float]] = {}  # key → (value, expires_at)
        self._lock = asyncio.Lock()
        self.default_ttl = default_ttl

    async def get(self, key: str) -> Any | None:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.time() > expires_at:
                del self._store[key]
                return None
            return value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        ttl = ttl if ttl is not None else self.default_ttl
        async with self._lock:
            self._store[key] = (value, time.time() + ttl)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()

    def stats(self) -> dict:
        now = time.time()
        live = sum(1 for _, (_, exp) in self._store.items() if exp > now)
        return {"total_keys": len(self._store), "live_keys": live}


# ── Redis implementation ──────────────────────────────────────────────────────

class RedisCache(BaseCache):
    """Redis-backed cache. Requires `pip install redis[asyncio]`."""

    def __init__(self, redis_url: str, default_ttl: int = 3600):
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self._client = None

    async def _get_client(self):
        if self._client is None:
            try:
                import redis.asyncio as aioredis
                self._client = aioredis.from_url(self.redis_url, decode_responses=True)
            except ImportError:
                raise RuntimeError("Install redis: pip install redis[asyncio]")
        return self._client

    async def get(self, key: str) -> Any | None:
        client = await self._get_client()
        raw = await client.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        client = await self._get_client()
        ttl = ttl if ttl is not None else self.default_ttl
        await client.setex(key, ttl, json.dumps(value, default=str))

    async def delete(self, key: str) -> None:
        client = await self._get_client()
        await client.delete(key)

    async def clear(self) -> None:
        client = await self._get_client()
        await client.flushdb()


# ── Factory ───────────────────────────────────────────────────────────────────

_cache_instance: BaseCache | None = None


def get_cache() -> BaseCache:
    """Return the singleton cache (lazy init)."""
    global _cache_instance
    if _cache_instance is not None:
        return _cache_instance

    from backend.config import get_settings
    settings = get_settings()

    if settings.redis_url:
        logger.info("Using Redis cache: %s", settings.redis_url)
        _cache_instance = RedisCache(settings.redis_url, settings.cache_ttl_seconds)
    else:
        logger.info("Using in-memory cache (TTL=%ds)", settings.cache_ttl_seconds)
        _cache_instance = InMemoryCache(settings.cache_ttl_seconds)

    return _cache_instance


# ── Decorator helper ──────────────────────────────────────────────────────────

def cached(prefix: str, ttl: int | None = None):
    """
    Async decorator to cache function results.
    
    @cached("predict", ttl=600)
    async def run_prediction(company: str, ...):
        ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            cache = get_cache()
            key = make_cache_key(prefix, args=args, kwargs=kwargs)
            cached_result = await cache.get(key)
            if cached_result is not None:
                logger.debug("Cache HIT: %s", key)
                return cached_result
            logger.debug("Cache MISS: %s", key)
            result = await func(*args, **kwargs)
            await cache.set(key, result, ttl=ttl)
            return result
        return wrapper
    return decorator