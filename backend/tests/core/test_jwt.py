import time
import uuid

import pytest
from jose import jwt

from app.core.exceptions import InvalidTokenError, TokenExpiredError
from app.core.jwt import JWTService


@pytest.fixture
def jwt_service():
    return JWTService()


@pytest.fixture
def user_id():
    return uuid.uuid4()


class TestCreateAccessToken:
    def test_returns_decodable_token(self, jwt_service, user_id):
        token = jwt_service.create_access_token(user_id, "USER")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_payload_contains_sub_and_role(self, jwt_service, user_id):
        from app.config import settings
        token = jwt_service.create_access_token(user_id, "ADMIN")
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        assert payload["sub"] == str(user_id)
        assert payload["role"] == "ADMIN"
        assert payload["type"] == "access"

    def test_token_has_expiry(self, jwt_service, user_id):
        from app.config import settings
        token = jwt_service.create_access_token(user_id, "USER")
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        assert "exp" in payload
        assert payload["exp"] > time.time()


class TestDecodeAccessToken:
    def test_valid_token_returns_payload(self, jwt_service, user_id):
        token = jwt_service.create_access_token(user_id, "USER")
        payload = jwt_service.decode_access_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["role"] == "USER"

    def test_tampered_token_raises_invalid(self, jwt_service, user_id):
        token = jwt_service.create_access_token(user_id, "USER")
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(InvalidTokenError):
            jwt_service.decode_access_token(tampered)

    def test_garbage_string_raises_invalid(self, jwt_service):
        with pytest.raises(InvalidTokenError):
            jwt_service.decode_access_token("not.a.token")

    def test_wrong_type_raises_invalid(self, jwt_service, user_id):
        """A token with type != 'access' must be rejected."""
        from app.config import settings
        from datetime import datetime, timedelta, timezone
        payload = {
            "sub": str(user_id),
            "role": "USER",
            "type": "refresh",  # wrong
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        }
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        with pytest.raises(InvalidTokenError):
            jwt_service.decode_access_token(token)
