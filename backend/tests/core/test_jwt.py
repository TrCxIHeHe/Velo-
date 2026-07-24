import uuid
import pytest
from app.core.jwt import JWTService
from app.core.exceptions import InvalidTokenError, TokenExpiredError


def test_create_and_decode_access_token():
    svc = JWTService()
    user_id = uuid.uuid4()
    token = svc.create_access_token(user_id, "USER")
    payload = svc.decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "USER"
    assert payload["type"] == "access"


def test_invalid_token_raises():
    svc = JWTService()
    with pytest.raises(InvalidTokenError):
        svc.decode_access_token("not.a.valid.token")


def test_wrong_type_raises():
    """A JWT signed with the right secret but wrong type must be rejected."""
    from jose import jwt
    from app.config import settings
    import uuid
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(uuid.uuid4()),
        "role": "USER",
        "type": "refresh",   # wrong type
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(minutes=15),
    }
    bad_token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    svc = JWTService()
    with pytest.raises(InvalidTokenError):
        svc.decode_access_token(bad_token)
