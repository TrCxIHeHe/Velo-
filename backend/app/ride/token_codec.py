import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from redis.asyncio import Redis

from app.config import settings
from app.core.exceptions import (
    RideTokenExpiredError,
    RideTokenGenerationError,
    RideTokenInvalidError,
    RideTokenReusedError,
)

RIDE_JTI_PREFIX = "ride:jti:"


class RideTokenCodec:
    """Issue/consume the 30s HMAC-signed one-time ride token.

    Payload minimal by design: sub, jti, iat, exp only. ride_id binding
    lives in the Redis value (jti -> ride_id), not the JWT.
    """

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def issue(self, user_id: uuid.UUID, ride_id: uuid.UUID) -> tuple[str, datetime]:
        now = datetime.now(timezone.utc)
        exp = now + timedelta(seconds=settings.RIDE_TOKEN_TTL_SECONDS)
        jti = str(uuid.uuid4())

        payload = {"sub": str(user_id), "jti": jti, "iat": now, "exp": exp}
        token = jwt.encode(payload, settings.RIDE_TOKEN_SECRET, algorithm=settings.RIDE_TOKEN_ALGORITHM)

        try:
            ok = await self.redis.set(
                f"{RIDE_JTI_PREFIX}{jti}", str(ride_id), ex=settings.RIDE_TOKEN_TTL_SECONDS, nx=True
            )
        except Exception as exc:
            raise RideTokenGenerationError() from exc

        if not ok:
            raise RideTokenGenerationError()

        return token, exp

    async def consume(self, raw_token: str) -> tuple[uuid.UUID, uuid.UUID]:
        """Decode + one-time-consume. Returns (user_id, ride_id).

        GETDEL is atomic — a second consume of the same token, concurrent
        or not, finds nothing and raises reuse.
        """
        try:
            payload = jwt.decode(
                raw_token, settings.RIDE_TOKEN_SECRET, algorithms=[settings.RIDE_TOKEN_ALGORITHM]
            )
        except JWTError as exc:
            if "expired" in str(exc).lower():
                raise RideTokenExpiredError() from exc
            raise RideTokenInvalidError() from exc

        jti = payload.get("jti")
        sub = payload.get("sub")
        if not jti or not sub:
            raise RideTokenInvalidError()

        ride_id_raw = await self.redis.getdel(f"{RIDE_JTI_PREFIX}{jti}")
        if ride_id_raw is None:
            raise RideTokenReusedError()

        return uuid.UUID(sub), uuid.UUID(ride_id_raw)
