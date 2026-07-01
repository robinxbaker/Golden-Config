"""Redis client helpers used for caching device data."""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings

_redis_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """Return a lazily-initialised shared async Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.CACHE_REDIS_URL, encoding="utf-8", decode_responses=True
        )
    return _redis_client


async def cache_get_json(key: str) -> Any | None:
    """Fetch and JSON-decode a cached value, or ``None`` if missing."""
    raw = await get_redis().get(key)
    return json.loads(raw) if raw else None


async def cache_set_json(key: str, value: Any, ttl: int | None = None) -> None:
    """JSON-encode and cache a value with an optional TTL."""
    await get_redis().set(
        key, json.dumps(value, default=str), ex=ttl or settings.CACHE_TTL_SECONDS
    )


async def cache_delete(*keys: str) -> None:
    if keys:
        await get_redis().delete(*keys)
