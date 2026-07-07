"""Shared pytest fixtures for the whole Track B test suite.

WHY SQLITE FOR TESTS, POSTGRES FOR PRODUCTION
----------------------------------------------
Every model in app/models/ was deliberately written to be database-agnostic
(plain Float lat/lng instead of PostGIS geometry, standard UUID/DateTime
columns) specifically so tests can run against an in-memory SQLite database
with zero setup — no Docker, no local Postgres install required to run
`pytest`. Production still uses real PostgreSQL (see app/config.py's
DATABASE_URL default and .env.example).

One deliberate divergence to know about: `with_for_update()` (row locking,
used in WalletRepository.find_by_user_id_locked and
DockRepository.find_available_slot) is a silent no-op on SQLite. That's
fine for correctness tests here — it doesn't change what the balance/slot
values end up being — but it means these tests cannot catch a concurrency
bug in that locking logic. If you need to prove the locking actually
prevents a race, that has to be tested against real Postgres (e.g. spin up
docker-compose's postgres service and fire two concurrent debits).

FIXTURE CHAIN
-------------
engine (per test session, in-memory sqlite)
  -> creates all tables from Base.metadata once
  -> db_session (per test function, wrapped in a transaction that's rolled
     back at the end of every test so tests never see each other's data)
  -> app fixture: builds a FastAPI TestClient with get_db overridden to
     hand out db_session instead of a real Postgres connection.
"""
import asyncio
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app import models  # noqa: F401 registers all tables on Base.metadata

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def engine():
    # A fresh in-memory DB per test function (not per session) keeps tests
    # fully isolated from each other with no manual cleanup needed — the
    # whole database just disappears when the engine is disposed.
    # StaticPool + check_same_thread=False: async sqlite normally opens a
    # new (empty) in-memory database per connection, which would make our
    # tables vanish between fixture setup and the actual test. StaticPool
    # forces every checkout to reuse the same single connection instead.
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
async def db_session(engine):
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    """An httpx AsyncClient wired directly into the FastAPI app, with the
    real Postgres-backed get_db dependency swapped for our SQLite test
    session. This lets router-level tests exercise the full stack
    (router -> service -> repository) exactly as a real request would,
    without needing a running server or a real database.
    """

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def auth_headers(user_id) -> dict:
    return {"X-Debug-User-Id": str(user_id)}


@pytest.fixture
def admin_headers(user_id) -> dict:
    return {"X-Debug-User-Id": str(user_id), "X-Debug-Role": "ADMIN"}
