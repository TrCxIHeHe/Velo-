from functools import lru_cache

import redis.asyncio as redis

from app.config import settings


@lru_cache(maxsize=1)
def _client() -> redis.Redis:
    """Singleton async Redis client. Pool-backed, safe across requests."""
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


async def get_redis_client() -> redis.Redis:
    """FastAPI dependency — overridden with fakeredis in tests
    (see tests/conftest.py), same pattern as get_db/get_firebase_service."""
    return _client()
