"""Ride-token lifecycle: PENDING → ACTIVE | CANCELLED | EXPIRED.

Regression tests for the "stuck PENDING ride" bug: an expired, never-scanned
QR used to leave a PENDING ride behind that blocked every later token request
until `scripts/cancel_stuck_ride.py` was run by hand.

Expiry is exercised with a real (1 s) TTL so the JWT `exp` claim itself is what
gets rejected — nothing about token validation is mocked or weakened.
"""
import asyncio
import uuid

import pytest

from app.audit.repository import AuditLogRepository
from app.config import settings
from app.core.exceptions import (
    DockMismatchError,
    RideAlreadyActiveError,
    RideInvalidStateError,
    RideTokenExpiredError,
    RideTokenInvalidError,
    RideTokenReusedError,
    VehicleUnavailableError,
)
from app.dock.repository import DockRepository, VehicleRepository
from app.dock.schemas import DockCreate, VehicleCreate
from app.dock.service import DockService
from app.models.user import User
from app.ride.repository import RideRepository
from app.ride.service import RideService
from app.wallet.repository import WalletRepository
from app.wallet.service import WalletService


async def _make_dock(db_session, with_vehicle=True, name="Lifecycle Dock"):
    dock_repo = DockRepository(db_session)
    dock_svc = DockService(dock_repo, VehicleRepository(db_session))
    dock = await dock_svc.create_dock(
        DockCreate(name=name, location_lat=1.0, location_lng=1.0, total_slots=2)
    )
    if with_vehicle:
        slot = await dock_repo.find_free_slot(dock.id)
        await dock_svc.add_vehicle(
            VehicleCreate(qr_code=f"qr-{uuid.uuid4()}", battery_level=100, slot_id=slot.id)
        )
    return dock.id


async def _make_user(db_session):
    user_id = uuid.uuid4()
    db_session.add(
        User(id=user_id, firebase_uid=f"uid-{user_id}", phone_number=f"+91{user_id.int % 10**10:010d}")
    )
    await db_session.flush()
    await WalletService(WalletRepository(db_session), AuditLogRepository(db_session)).top_up(
        user_id, 500.0
    )
    return user_id


def _service(db_session, redis_client) -> RideService:
    return RideService(
        RideRepository(db_session),
        DockRepository(db_session),
        VehicleRepository(db_session),
        WalletService(WalletRepository(db_session), AuditLogRepository(db_session)),
        AuditLogRepository(db_session),
        redis_client=redis_client,
    )


@pytest.fixture
def short_ttl(monkeypatch):
    monkeypatch.setattr(settings, "RIDE_TOKEN_TTL_SECONDS", 1)


async def _wait_for_expiry():
    await asyncio.sleep(2.2)


# ── Acceptance A / B / C ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_expired_pending_does_not_block_new_token(db_session, redis_mock, short_ttl):
    dock_id = await _make_dock(db_session)
    user_id = await _make_user(db_session)
    svc = _service(db_session, redis_mock)

    qr1 = await svc.request_ride_token(user_id, dock_id)
    assert (await svc.get_active_ride(user_id)).status == "PENDING"

    await _wait_for_expiry()

    # A: QR #2 succeeds with no script / manual step.
    qr2 = await svc.request_ride_token(user_id, dock_id)
    assert qr2.ride_id != qr1.ride_id

    # The old ride was retired to EXPIRED, not left PENDING.
    old = await RideRepository(db_session).find_by_id(qr1.ride_id)
    assert old.status == "EXPIRED"

    # C: QR #1 stays rejected — JWT validation is untouched.
    with pytest.raises(RideTokenExpiredError):
        await svc.confirm_ride(qr1.ride_token, dock_id)

    # B: QR #2 at the right dock → ACTIVE.
    ride = await svc.confirm_ride(qr2.ride_token, dock_id)
    assert ride.status == "ACTIVE"


@pytest.mark.asyncio
async def test_same_valid_token_twice_is_rejected(db_session, redis_mock):
    dock_id = await _make_dock(db_session)
    user_id = await _make_user(db_session)
    svc = _service(db_session, redis_mock)

    qr = await svc.request_ride_token(user_id, dock_id)
    await svc.confirm_ride(qr.ride_token, dock_id)
    with pytest.raises(RideTokenReusedError):  # D
        await svc.confirm_ride(qr.ride_token, dock_id)


@pytest.mark.asyncio
async def test_wrong_dock_is_still_rejected(db_session, redis_mock):
    dock_id = await _make_dock(db_session)
    other_dock = await _make_dock(db_session, name="Other Dock")
    user_id = await _make_user(db_session)
    svc = _service(db_session, redis_mock)

    qr = await svc.request_ride_token(user_id, dock_id)
    with pytest.raises(DockMismatchError):
        await svc.confirm_ride(qr.ride_token, other_dock)


# ── Superseding a still-valid PENDING token ──────────────────────────────────

@pytest.mark.asyncio
async def test_new_request_supersedes_valid_pending_token(db_session, redis_mock):
    dock_id = await _make_dock(db_session)
    user_id = await _make_user(db_session)
    svc = _service(db_session, redis_mock)
    repo = RideRepository(db_session)

    qr1 = await svc.request_ride_token(user_id, dock_id)
    qr2 = await svc.request_ride_token(user_id, dock_id)

    assert (await repo.find_by_id(qr1.ride_id)).status == "CANCELLED"
    assert (await repo.find_by_id(qr2.ride_id)).status == "PENDING"
    assert len(await repo.list_open_for_user(user_id)) == 1  # one live PENDING ride

    # The superseded token is revoked even though its JWT has not expired.
    with pytest.raises(RideTokenInvalidError):
        await svc.confirm_ride(qr1.ride_token, dock_id)

    assert (await svc.confirm_ride(qr2.ride_token, dock_id)).status == "ACTIVE"


@pytest.mark.asyncio
async def test_failed_token_request_keeps_existing_valid_token(db_session, redis_mock):
    dock_id = await _make_dock(db_session)
    empty_dock = await _make_dock(db_session, with_vehicle=False, name="Empty Dock")
    user_id = await _make_user(db_session)
    svc = _service(db_session, redis_mock)

    qr1 = await svc.request_ride_token(user_id, dock_id)
    with pytest.raises(VehicleUnavailableError):
        await svc.request_ride_token(user_id, empty_dock)

    assert (await RideRepository(db_session).find_by_id(qr1.ride_id)).status == "PENDING"
    assert (await svc.confirm_ride(qr1.ride_token, dock_id)).status == "ACTIVE"


# ── ACTIVE still blocks; explicit cancel ─────────────────────────────────────

@pytest.mark.asyncio
async def test_active_ride_still_blocks_new_token(db_session, redis_mock):
    dock_id = await _make_dock(db_session)
    await _make_dock(db_session, name="Second")  # unrelated
    user_id = await _make_user(db_session)
    svc = _service(db_session, redis_mock)

    qr = await svc.request_ride_token(user_id, dock_id)
    await svc.confirm_ride(qr.ride_token, dock_id)
    with pytest.raises(RideAlreadyActiveError):
        await svc.request_ride_token(user_id, dock_id)


@pytest.mark.asyncio
async def test_explicit_cancel_pending_ride(db_session, redis_mock):
    dock_id = await _make_dock(db_session)
    user_id = await _make_user(db_session)
    svc = _service(db_session, redis_mock)

    qr = await svc.request_ride_token(user_id, dock_id)
    assert (await svc.cancel_pending_ride(user_id, qr.ride_id)).status == "CANCELLED"
    # idempotent
    assert (await svc.cancel_pending_ride(user_id, qr.ride_id)).status == "CANCELLED"
    # token is dead
    with pytest.raises(RideTokenInvalidError):
        await svc.confirm_ride(qr.ride_token, dock_id)
    # and the user can immediately get a new one
    await svc.request_ride_token(user_id, dock_id)


@pytest.mark.asyncio
async def test_cannot_cancel_active_ride_via_cancel_pending(db_session, redis_mock):
    dock_id = await _make_dock(db_session)
    user_id = await _make_user(db_session)
    svc = _service(db_session, redis_mock)

    qr = await svc.request_ride_token(user_id, dock_id)
    await svc.confirm_ride(qr.ride_token, dock_id)
    with pytest.raises(RideInvalidStateError):
        await svc.cancel_pending_ride(user_id, qr.ride_id)


# ── Lazy expiry on read paths (keeps the Flutter client in sync) ─────────────

@pytest.mark.asyncio
async def test_get_ride_reports_expired_once_ttl_elapsed(db_session, redis_mock, short_ttl):
    dock_id = await _make_dock(db_session)
    user_id = await _make_user(db_session)
    svc = _service(db_session, redis_mock)

    qr = await svc.request_ride_token(user_id, dock_id)
    assert (await svc.get_ride(user_id, qr.ride_id)).status == "PENDING"
    await _wait_for_expiry()
    assert (await svc.get_ride(user_id, qr.ride_id)).status == "EXPIRED"
    assert await svc.get_active_ride(user_id) is None


@pytest.mark.asyncio
async def test_valid_token_is_never_expired_early(db_session, redis_mock):
    """Default TTL: a fresh PENDING ride must not be swept by any read path."""
    dock_id = await _make_dock(db_session)
    user_id = await _make_user(db_session)
    svc = _service(db_session, redis_mock)

    qr = await svc.request_ride_token(user_id, dock_id)
    assert (await svc.get_active_ride(user_id)).status == "PENDING"
    assert (await svc.list_rides(user_id)).items[0].status == "PENDING"
    assert (await svc.confirm_ride(qr.ride_token, dock_id)).status == "ACTIVE"
