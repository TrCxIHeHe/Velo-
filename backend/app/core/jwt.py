import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import settings
from app.core.exceptions import InvalidTokenError, TokenExpiredError


class JWTService:
    """Encodes and decodes JWT access tokens.

    Refresh tokens are NOT JWTs — they are opaque random strings stored
    as SHA-256 hashes in the database. Only access tokens are JWTs.
    """

    def create_access_token(self, user_id: uuid.UUID, role: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "role": role,
            "type": "access",
            "jti": str(uuid.uuid4()),  # unique id — guarantees distinct tokens
            "iat": now,
            "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        }
        return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    def decode_access_token(self, token: str) -> dict:
        """Returns payload dict with 'sub' (user_id str) and 'role'.

        Raises TokenExpiredError or InvalidTokenError — never raw jose errors.
        """
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
            )
            if payload.get("type") != "access":
                raise InvalidTokenError()
            return payload
        except JWTError as exc:
            if "expired" in str(exc).lower():
                raise TokenExpiredError()
            raise InvalidTokenError() from exc
