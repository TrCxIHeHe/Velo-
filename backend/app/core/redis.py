from functools import lru_cache
import redis.asyncio as redis
from app.config import settings


@lru_cache(maxsize=1)
def get_redis_client() -> redis.Redis:
    return redis.from_url(settings.REDIS_URL, decode_responses=True)
