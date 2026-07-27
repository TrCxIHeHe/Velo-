"""Unit tests for AuthService using mocked Firebase and real SQLite DB."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.audit.repository import AuditLogRepository
from app.auth.repository import RefreshTokenRepository, UserRepository
from app.auth.service import AuthService
from app.core.exceptions import (
    RefreshTokenExpiredError,
    RefreshTokenReuseError,
    UserDeactivatedError,
)
from app.core.jwt import JWTService
from app.core.security import hash_token


def _mock_firebase(uid="firebase-uid-123", phone="+919876543210"):
    svc = MagicMock()
    svc.verify_id_token.return_value = {"uid": uid, "phone_number": phone}
    return svc


@pytest.mark.asyncio
async def test_login_creates_new_user(db_session):
    user_repo = UserRepository(db_session)
    token_repo = RefreshTokenRepository(db_session)
    audit_repo = AuditLogRepository(db_session)
    jwt = JWTService()
    firebase = _mock_firebase()

    service = AuthService(user_repo, token_repo, firebase, jwt, audit_repo)
    result = await service.login("dummy-firebase-token")

    assert result.access_token
    assert result.refresh_token
    assert result.user.phone_number == "+919876543210"


@pytest.mark.asyncio
async def test_login_existing_user_returns_tokens(db_session):
    user_repo = UserRepository(db_session)
    token_repo = RefreshTokenRepository(db_session)
    audit_repo = AuditLogRepository(db_session)
    jwt = JWTService()
    firebase = _mock_firebase(uid="existing-uid", phone="+911234567890")

    service = AuthService(user_repo, token_repo, firebase, jwt, audit_repo)
    r1 = await service.login("token1")
    r2 = await service.login("token2")

    assert r1.user.id == r2.user.id


@pytest.mark.asyncio
async def test_refresh_rotates_token(db_session):
    user_repo = UserRepository(db_session)
    token_repo = RefreshTokenRepository(db_session)
    audit_repo = AuditLogRepository(db_session)
    jwt = JWTService()
    firebase = _mock_firebase(uid="refresh-uid", phone="+910000000001")

    service = AuthService(user_repo, token_repo, firebase, jwt, audit_repo)
    login_result = await service.login("t1")
    refresh_result = await service.refresh(login_result.refresh_token)

    assert refresh_result.access_token
    assert refresh_result.refresh_token != login_result.refresh_token


@pytest.mark.asyncio
async def test_refresh_reuse_revokes_family(db_session):
    user_repo = UserRepository(db_session)
    token_repo = RefreshTokenRepository(db_session)
    audit_repo = AuditLogRepository(db_session)
    jwt = JWTService()
    firebase = _mock_firebase(uid="reuse-uid", phone="+910000000002")

    service = AuthService(user_repo, token_repo, firebase, jwt, audit_repo)
    login_result = await service.login("t2")
    await service.refresh(login_result.refresh_token)  # consume it

    with pytest.raises(RefreshTokenReuseError):
        await service.refresh(login_result.refresh_token)  # reuse → error


@pytest.mark.asyncio
async def test_logout_revokes_token(db_session):
    user_repo = UserRepository(db_session)
    token_repo = RefreshTokenRepository(db_session)
    audit_repo = AuditLogRepository(db_session)
    jwt = JWTService()
    firebase = _mock_firebase(uid="logout-uid", phone="+910000000003")

    service = AuthService(user_repo, token_repo, firebase, jwt, audit_repo)
    login_result = await service.login("t3")
    await service.logout(login_result.refresh_token)

    # Should now fail as reused/revoked
    with pytest.raises(Exception):
        await service.refresh(login_result.refresh_token)
