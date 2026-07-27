"""
Shared test fixtures.

Uses an in-memory SQLite database (via aiosqlite) so tests run without
a real Postgres instance. The GUID type handles the dialect difference.
"""
import asyncio
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.jwt import JWTService
from app.database import Base, get_db
from app.main import app
from app.models.user import User

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(engine) -> AsyncGenerator[AsyncClient, None]:
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Auth fixtures for HTTP-level (router) tests ───────────────────────────────
# These commit users directly to the engine so the HTTP client's session can
# authenticate against them.  They must NOT use db_session (which rolls back).

@pytest_asyncio.fixture
async def _committed_user(engine) -> uuid.UUID:
    """Create and commit a USER-role test user, return its UUID."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    user_id = uuid.uuid4()
    async with factory() as session:
        user = User(
            id=user_id,
            firebase_uid=f"test-user-{user_id}",
            phone_number=f"+91{str(user_id.int % 10_000_000_000).zfill(10)}",
            role="USER",
            is_active=True,
        )
        session.add(user)
        await session.commit()
    return user_id


@pytest_asyncio.fixture
async def _committed_admin(engine) -> uuid.UUID:
    """Create and commit an ADMIN-role test user, return its UUID."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    user_id = uuid.uuid4()
    async with factory() as session:
        user = User(
            id=user_id,
            firebase_uid=f"test-admin-{user_id}",
            phone_number=f"+91{str((user_id.int + 1) % 10_000_000_000).zfill(10)}",
            role="ADMIN",
            is_active=True,
        )
        session.add(user)
        await session.commit()
    return user_id


@pytest.fixture
def auth_headers(_committed_user: uuid.UUID) -> dict:
    """Bearer token headers for a regular USER."""
    token = JWTService().create_access_token(_committed_user, "USER")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(_committed_admin: uuid.UUID) -> dict:
    """Bearer token headers for an ADMIN user."""
    token = JWTService().create_access_token(_committed_admin, "ADMIN")
    return {"Authorization": f"Bearer {token}"}
