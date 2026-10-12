"""Transaction control through the REAL request-session semantics.

``app.database.get_db`` commits when the handler returns normally, and the ride
router converts ``AppException`` into an ordinary error response. Without an
explicit rollback in ``RideService.end_ride`` a failure after the first write
would therefore be COMMITTED half-done. The shared-session ``client`` fixture
hides that (it never commits), so this module uses separate sessions on a
file-backed SQLite database and the production commit-on-exit dependency.
"""
import uuid
from collections.abc import AsyncGenerator
from decimal import Decimal

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.audit.repository import AuditLogRepository
from app.core.firebase import get_firebase_service
from app.core.redis import get_redis_client
from app.database import Base, get_db
from app.dock.repository import DockRepository, VehicleRepository
from app.dock.schemas import DockCreate, VehicleCreate
from app.dock.service import DockService
from app.main import app
from app.models import DockSlot, Ride, Vehicle, WalletTransaction
from app.pricing.repository import DockPairFareRepository
from app.ride.repository import RideRepository
from app.ride.service import RideService
from app.wallet.repository import WalletRepository
from app.wallet.service import WalletService


@pytest_asyncio.fixture
async def real_env(tmp_path, firebase_mock, redis_mock):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path/'tx.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def real_get_db() -> AsyncGenerator[AsyncSession, None]:  # same body as app.database.get_db
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = real_get_db
    app.dependency_overrides[get_firebase_service] = lambda: firebase_mock
    app.dependency_overrides[get_redis_client] = lambda: redis_mock
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, factory, redis_mock
    app.dependency_overrides.clear()
    await engine.dispose()


async def _scenario(real_env, *, fare: str | None, balance: float, dest_slots: int = 2):
    client, factory, redis = real_env
    login = await client.post("/api/v1/auth/login", json={"firebase_id_token": "uid"})
    token = login.json()["data"]["access_token"]
    user_id = uuid.UUID(login.json()["data"]["user"]["id"])
    headers = {"Authorization": f"Bearer {token}"}

    async with factory() as s:
        docks = DockService(DockRepository(s), VehicleRepository(s))
        a = (await docks.create_dock(DockCreate(name="A", location_lat=1, location_lng=1, total_slots=2))).id
        b = (await docks.create_dock(
            DockCreate(name="B", location_lat=2, location_lng=2, total_slots=dest_slots))).id
        slot = await DockRepository(s).find_free_slot(a)
        await docks.add_vehicle(VehicleCreate(qr_code="qr-1", battery_level=100, slot_id=slot.id))
        if fare:
            await DockPairFareRepository(s).create(a, b, Decimal(fare), "INR", True)
        await WalletService(WalletRepository(s)).top_up(user_id, balance)
        await s.commit()

        svc = RideService(
            RideRepository(s), DockRepository(s), VehicleRepository(s),
            WalletService(WalletRepository(s), AuditLogRepository(s)), AuditLogRepository(s),
            redis_client=redis,
        )
        tok = await svc.request_ride_token(user_id, a)
        ride = await svc.confirm_ride(tok.ride_token, a)
        await s.commit()
    return client, factory, headers, ride, a, b


async def _state(factory, ride_id, dest):
    async with factory() as s:
        ride = (await s.execute(select(Ride).where(Ride.id == ride_id))).scalar_one()
        occupied = (await s.execute(
            select(func.count()).select_from(DockSlot).where(DockSlot.dock_id == dest, DockSlot.is_occupied.is_(True))
        )).scalar_one()
        vehicle = (await s.execute(select(Vehicle).where(Vehicle.id == ride.vehicle_id))).scalar_one()
        debits = (await s.execute(
            select(func.count()).select_from(WalletTransaction).where(WalletTransaction.source == "RIDE_FARE")
        )).scalar_one()
        return ride, occupied, vehicle, debits


async def test_failed_end_is_not_committed_half_done(real_env):
    """150 fare vs 100 balance: the wallet debit fails AFTER the ride/slot/vehicle
    writes. The request returns an error and nothing may be persisted."""
    client, factory, headers, ride, a, b = await _scenario(real_env, fare="150.00", balance=100.0)

    r = await client.post(f"/api/v1/rides/{ride.id}/end", headers=headers, json={"dock_id": str(b)})
    assert r.status_code == 400 and r.json()["error"]["code"] == "WALLET_INSUFFICIENT_BALANCE"

    stored, occupied, vehicle, debits = await _state(factory, ride.id, b)
    assert stored.status == "ACTIVE" and stored.fare_amount is None and stored.end_dock_id is None
    assert occupied == 0
    assert vehicle.status == "IN_RIDE" and vehicle.slot_id is None
    assert debits == 0


async def test_successful_end_commits_everything_and_survives_replay(real_env):
    client, factory, headers, ride, a, b = await _scenario(real_env, fare="20.00", balance=100.0)
    end = lambda: client.post(f"/api/v1/rides/{ride.id}/end", headers=headers, json={"dock_id": str(b)})

    first = await end()
    assert first.status_code == 200 and first.json()["data"]["fare_amount"] == 20.0
    replay = await end()   # e.g. the app retried after a dropped response
    assert replay.status_code == 200 and replay.json()["data"]["id"] == first.json()["data"]["id"]

    stored, occupied, vehicle, debits = await _state(factory, ride.id, b)
    assert stored.status == "COMPLETED" and stored.fare_amount == 20.0
    assert occupied == 1 and vehicle.status == "AVAILABLE" and vehicle.slot_id is not None
    assert debits == 1


async def test_missing_fare_via_http_leaves_ride_active(real_env):
    client, factory, headers, ride, a, b = await _scenario(real_env, fare=None, balance=100.0)
    r = await client.post(f"/api/v1/rides/{ride.id}/end", headers=headers, json={"dock_id": str(b)})
    assert r.status_code == 409 and r.json()["error"]["code"] == "FARE_NOT_CONFIGURED"
    stored, occupied, vehicle, debits = await _state(factory, ride.id, b)
    assert stored.status == "ACTIVE" and occupied == 0 and debits == 0
