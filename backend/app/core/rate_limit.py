"""Per-IP request rate limiting (slowapi/limits, in-memory — single-instance MVP).

Only active when ENVIRONMENT=production. Local dev and the test suite share
one client IP across hundreds of requests per run, so limiting there would
produce false 429s rather than catching anything real; the honest place to
exercise this is a staging/production deploy sitting behind a real client
population. Move to a Redis-backed storage backend before running more than
one backend instance, since slowapi's default in-memory store is per-process.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    enabled=settings.ENVIRONMENT == "production",
)
