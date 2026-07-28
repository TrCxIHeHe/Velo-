"""Ride-token one-time-use is enforced atomically via Redis SETNX
(app/ride/service.py::confirm_ride), not just the DB status check —
the DB check alone has a TOCTOU race under concurrent confirms."""
import asyncio
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.audit.repository import AuditLogRepository
from app.dock.repository import DockRepository, VehicleRepository
from app.dock.schemas import DockCreate, VehicleCreate
from app.dock.service import DockService
from app.ride.repository import RideRepository
from app.ride.service import RideService
from app.wallet.repository import WalletRepository
from app.wallet.service import WalletService


async def _setup_dock_with_vehicle(db_session):
    dock_repo = DockRepository(db_session)
    vehicle_repo = VehicleRepository(db_session)
    dock_svc = DockService(dock_repo, vehicle_repo)

    dock = await dock_svc.create_dock(
        DockCreate(name="Replay Test Dock", location_lat=1.0, location_lng=1.0, total_slots=2)
    )
    slot = await dock_repo.find_free_slot(dock.id)
    await dock_svc.add_vehicle(
        VehicleCreate(qr_code=f"qr-{uuid.uuid4()}", battery_level=100, slot_id=slot.id)
    )
    return dock.id


def _build_ride_service(db_session, redis_client) -> RideService:
    return RideService(
        RideRepository(db_session),
        DockRepository(db_session),
        VehicleRepository(db_session),
        WalletService(WalletRepository(db_session), AuditLogRepository(db_session)),
        AuditLogRepository(db_session),
        redis_client=redis_client,
    )


@pytest.mark.asyncio
async def test_second_confirm_of_same_token_is_rejected(db_session, redis_mock):
    from app.core.exceptions import RideTokenReusedError

    dock_id = await _setup_dock_with_vehicle(db_session)
    user_id = uuid.uuid4()
    from app.models.user import User
    db_session.add(User(id=user_id, firebase_uid=f"uid-{user_id}", phone_number="+910000099999"))
    await db_session.flush()
    await WalletService(WalletRepository(db_session), AuditLogRepository(db_session)).top_up(user_id, 500.0)

    ride_service = _build_ride_service(db_session, redis_mock)
    token_result = await ride_service.request_ride_token(user_id, dock_id)

    await ride_service.confirm_ride(token_result.ride_token, dock_id)

    with pytest.raises(RideTokenReusedError):
        await ride_service.confirm_ride(token_result.ride_token, dock_id)


@pytest.mark.asyncio
async def test_concurrent_confirms_of_same_token_only_one_succeeds(engine, redis_mock):
    """The scenario the DB-only check can't safely handle: two requests
    racing to confirm the same (stolen/duplicated) QR at the same instant.
    Exactly one must succeed. Uses two independent sessions (over the same
    in-memory DB) since a single AsyncSession isn't safe for concurrent use
    — the property under test here is the Redis lock's atomicity, not
    session concurrency."""
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as setup_session:
        dock_id = await _setup_dock_with_vehicle(setup_session)
        user_id = uuid.uuid4()
        from app.models.user import User
        setup_session.add(User(id=user_id, firebase_uid=f"uid-{user_id}", phone_number="+910000088888"))
        await setup_session.commit()
        await WalletService(WalletRepository(setup_session), AuditLogRepository(setup_session)).top_up(
            user_id, 500.0
        )
        await setup_session.commit()

        token_result = await _build_ride_service(setup_session, redis_mock).request_ride_token(
            user_id, dock_id
        )
        await setup_session.commit()

    async def _confirm():
        async with session_factory() as session:
            service = _build_ride_service(session, redis_mock)
            result = await service.confirm_ride(token_result.ride_token, dock_id)
            await session.commit()
            return result

    results = await asyncio.gather(_confirm(), _confirm(), return_exceptions=True)

    successes = [r for r in results if not isinstance(r, Exception)]
    failures = [r for r in results if isinstance(r, Exception)]
    assert len(successes) == 1
    assert len(failures) == 1
