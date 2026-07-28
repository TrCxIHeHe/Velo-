"""Per-IP request rate limiting (slowapi/limits).

Only active when ENVIRONMENT=production. Local dev and the test suite share
one client IP across hundreds of requests per run, so limiting there would
produce false 429s rather than catching anything real; the honest place to
exercise this is a staging/production deploy sitting behind a real client
population.

Storage: Redis-backed in production, so limits are shared correctly across
multiple backend instances/processes rather than the in-memory default
(which only counts requests seen by that one process).
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    enabled=settings.ENVIRONMENT == "production",
    storage_uri=settings.REDIS_URL if settings.ENVIRONMENT == "production" else None,
)
