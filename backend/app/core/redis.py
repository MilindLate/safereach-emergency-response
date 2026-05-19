"""
SafeReach — Redis Client
Used for: Socket.io adapter, hospital lookup cache, session tokens.
"""

import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis: Optional[aioredis.Redis] = None


async def init_redis() -> None:
    global _redis
    _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    await _redis.ping()
    logger.info("Redis connection established.")


async def close_redis() -> None:
    if _redis:
        await _redis.aclose()
        logger.info("Redis connection closed.")


def get_redis() -> aioredis.Redis:
    if _redis is None:
        raise RuntimeError("Redis not initialised — call init_redis() first.")
    return _redis


# ─── Convenience helpers ──────────────────────────────────────────────────────

async def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> None:
    r = get_redis()
    await r.setex(key, ttl_seconds, json.dumps(value))


async def cache_get(key: str) -> Optional[Any]:
    r = get_redis()
    raw = await r.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def cache_delete(key: str) -> None:
    r = get_redis()
    await r.delete(key)


async def publish_event(channel: str, event: dict) -> None:
    """Publish a Socket.io-compatible event to a Redis channel."""
    r = get_redis()
    await r.publish(channel, json.dumps(event))
