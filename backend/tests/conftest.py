"""Shared pytest fixtures for the full merged test suite (Track A + Track B).

WHY SQLITE FOR TESTS, POSTGRES FOR PRODUCTION
----------------------------------------------
Every model is database-agnostic (GUID cross-dialect type, plain Float
lat/lng instead of PostGIS geometry) so tests run against an in-memory
SQLite database with zero setup. Production uses real PostgreSQL.

One deliberate divergence to know about: `with_for_update()` (row locking,
used in WalletRepository and DockRepository.find_free_slot) is a silent
no-op on SQLite. Fine for correctness here, but it cannot catch a
concurrency bug in that locking logic — that requires a real Postgres run.

AUTH IN TESTS
-------------
`auth_headers` / `admin_headers` below go through the real `POST
/auth/login` flow (Firebase mocked, see `firebase_mock`) and return a
genuine Bearer token, so wallet/dock/admin router tests exercise the same
auth path as everything else. `admin_headers` logs in once and then
promotes that user's role to ADMIN directly in the DB — `require_role`
re-reads the user from the DB on every request, so the already-issued
token remains valid after the promotion.
"""
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import fakeredis

from app import models  # noqa: F401 — registers every model on Base.metadata
from app.core.firebase import get_firebase_service
from app.core.redis import get_redis_client
from app.database import Base, get_db
from app.main import app
from app.models import User

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ── DB engine — fresh in-memory SQLite per test function ─────────────────────

@pytest_asyncio.fixture(scope="function")
async def engine():
    eng = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


# ── Firebase mock ────────────────────────────────────────────────────────────

MOCK_UID = "firebase_uid_test_001"
MOCK_PHONE = "+919876543210"


def make_firebase_mock(uid: str = MOCK_UID, phone: str = MOCK_PHONE):
    """`firebase_mock.verify_id_token` always returns MOCK_UID/MOCK_PHONE by
    default; override `.return_value`/`.side_effect` per-test to simulate a
    different user or a Firebase error. Two-user isolation tests mutate
    `.return_value` explicitly (see `other_auth_headers` below)."""
    mock = MagicMock()
    mock.verify_id_token.return_value = {"uid": uid, "phone_number": phone}
    return mock


@pytest.fixture
def firebase_mock():
    return make_firebase_mock()


# ── Redis mock ───────────────────────────────────────────────────────────────

@pytest.fixture
def redis_mock():
    """Fresh in-memory FakeAsyncRedis per test — real SETNX/EXPIRE semantics
    without a real Redis server, so ride-token replay-protection tests
    exercise the actual atomic-lock code path."""
    return fakeredis.FakeAsyncRedis(decode_responses=True)


# ── HTTP test client ──────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="function")
async def client(db_session, firebase_mock, redis_mock) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_firebase_service] = lambda: firebase_mock
    app.dependency_overrides[get_redis_client] = lambda: redis_mock

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Auth helpers ───────────────────────────────────────────────────────────────

@pytest.fixture
def user_id() -> uuid.UUID:
    """Plain random UUID for service-layer unit tests that bypass HTTP/auth
    entirely (WalletService, DockService called directly against a
    db_session) — no auth semantics involved, purely a data fixture."""
    return uuid.uuid4()


@pytest_asyncio.fixture
async def existing_user(db_session: AsyncSession) -> User:
    """A pre-existing active user in the test DB (for direct-repository tests)."""
    user = User(
        id=uuid.uuid4(),
        firebase_uid=MOCK_UID,
        phone_number=MOCK_PHONE,
        name="Test User",
        role="USER",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict:
    """Logs in via the real /auth/login flow, returns a ready Bearer header."""
    response = await client.post(
        "/api/v1/auth/login", json={"firebase_id_token": MOCK_UID}
    )
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def other_auth_headers(client: AsyncClient, firebase_mock) -> dict:
    """A second, distinct authenticated user — for isolation tests that
    need two different real users (e.g. wallet-per-user isolation).
    Switches the shared firebase_mock to a second identity; must be
    requested after `auth_headers` in the test signature so the first
    login already captured its token under the default identity."""
    firebase_mock.verify_id_token.return_value = {
        "uid": "firebase_uid_test_002",
        "phone_number": "+919876500002",
    }
    response = await client.post(
        "/api/v1/auth/login", json={"firebase_id_token": "firebase_uid_test_002"}
    )
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def admin_headers(client: AsyncClient, firebase_mock, db_session: AsyncSession) -> dict:
    """Logs in as a distinct identity, then promotes that user to ADMIN
    directly in the DB.

    Uses a UID different from MOCK_UID so this is a separate user from the
    one `auth_headers` logs in, letting tests request both fixtures at once
    to exercise regular-user-vs-admin isolation. require_role() re-reads
    the user from the database on every request, so the token issued
    before promotion is still valid afterwards.
    """
    admin_uid = "firebase_uid_test_admin_001"
    admin_phone = "+919876500099"
    firebase_mock.verify_id_token.return_value = {"uid": admin_uid, "phone_number": admin_phone}
    response = await client.post(
        "/api/v1/auth/login", json={"firebase_id_token": admin_uid}
    )
    token = response.json()["data"]["access_token"]

    user = await db_session.get(User, uuid.UUID(response.json()["data"]["user"]["id"]))
    user.role = "ADMIN"
    await db_session.commit()

    # Restore the mock to the default identity so a subsequently-requested
    # `auth_headers` in the same test logs in as MOCK_UID, not this admin.
    firebase_mock.verify_id_token.return_value = {"uid": MOCK_UID, "phone_number": MOCK_PHONE}

    return {"Authorization": f"Bearer {token}"}
