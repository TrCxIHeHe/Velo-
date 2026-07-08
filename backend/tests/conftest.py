import uuid
from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.dependencies import get_auth_service
from app.core.firebase import get_firebase_service
from app.core.redis import get_redis_client
from app.database import Base, get_db
from app.main import app
from app import models  # noqa: F401 — registers every model on Base.metadata
from app.models import User

# ── In-memory SQLite engine for tests ────────────────────────────────────────

from sqlalchemy.pool import StaticPool

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=StaticPool)
TestSessionFactory = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Firebase mock ─────────────────────────────────────────────────────────────

MOCK_UID = "firebase_uid_test_001"
MOCK_PHONE = "+919876543210"


def make_firebase_mock(uid: str = MOCK_UID, phone: str = MOCK_PHONE):
    mock = MagicMock()
    mock.verify_id_token.return_value = {"uid": uid, "phone_number": phone}
    return mock


@pytest.fixture
def firebase_mock():
    return make_firebase_mock()


# ── Fake Redis ────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def fake_redis() -> AsyncGenerator:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.flushall()
    await client.aclose()


# ── HTTP test client ──────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client(firebase_mock, fake_redis) -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_firebase_service] = lambda: firebase_mock
    app.dependency_overrides[get_redis_client] = lambda: fake_redis

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Helpers ───────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionFactory() as session:
        yield session


@pytest_asyncio.fixture
async def existing_user(db_session: AsyncSession) -> User:
    """A pre-existing active user in the test DB."""
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
