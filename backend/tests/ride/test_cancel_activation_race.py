"""Pending-ride cancellation vs. activation: an ACTIVE ride is never cancelled,
and a cancelled ride is never activated."""
import pytest
from sqlalchemy import select, update

from app.core.exceptions import RideInvalidStateError, RideTokenInvalidError
from app.models import AuditLog, Ride


async def _pending(world):
    a = await world.dock("A", vehicles=1)
    await world.fund(100)
    svc = world.service()
    token = await svc.request_ride_token(world.user_id, a)
    await world.db.commit()
    return a, svc, token


async def _raw_status(world, ride_id, status):
    """Change the row WITHOUT updating the already-loaded ORM object — i.e. the
    state another request committed after this one read the ride."""
    await world.db.execute(
        update(Ride).where(Ride.id == ride_id).values(status=status)
        .execution_options(synchronize_session=False)
    )


async def test_cancel_after_activation_is_rejected_and_ride_stays_active(client, world):
    a, svc, token = await _pending(world)
    ride = await svc.confirm_ride(token.ride_token, a)
    await world.db.commit()

    r = await client.post(f"/api/v1/rides/{ride.id}/cancel", headers=world.headers)
    assert r.status_code == 409 and r.json()["error"]["code"] == "RIDE_INVALID_STATE"

    stored = (await world.db.execute(select(Ride).where(Ride.id == ride.id))).scalar_one()
    assert stored.status == "ACTIVE"
    assert (await world.vehicle(ride.vehicle_id)).status == "IN_RIDE"


async def test_cancel_loses_to_a_concurrent_activation(world):
    """cancel read PENDING; the scan committed ACTIVE before cancel's UPDATE."""
    a, svc, token = await _pending(world)
    await svc.ride_repo.find_by_id(token.ride_id)           # cancel's read: PENDING
    await _raw_status(world, token.ride_id, "ACTIVE")        # scan commits meanwhile

    with pytest.raises(RideInvalidStateError):
        await svc.cancel_pending_ride(world.user_id, token.ride_id)

    status = (await world.db.execute(
        select(Ride.status).where(Ride.id == token.ride_id))).scalar_one()
    assert status == "ACTIVE"                                # NOT overwritten with CANCELLED
    actions = [r.action for r in (await world.db.execute(select(AuditLog))).scalars()]
    assert "RIDE_CANCELLED" not in actions


async def test_confirm_loses_to_a_concurrent_cancel_and_touches_no_vehicle(world):
    a, svc, token = await _pending(world)
    await svc.ride_repo.find_by_jti(  # confirm's read: PENDING
        __import__("hashlib").sha256(token.ride_token.encode()).hexdigest())
    await _raw_status(world, token.ride_id, "CANCELLED")     # user cancelled meanwhile

    with pytest.raises(RideTokenInvalidError):
        await svc.confirm_ride(token.ride_token, a)

    status = (await world.db.execute(
        select(Ride.status).where(Ride.id == token.ride_id))).scalar_one()
    assert status == "CANCELLED"
    # the scooter was never released: still AVAILABLE and docked
    from app.models import Vehicle
    v = (await world.db.execute(select(Vehicle))).scalar_one()
    assert v.status == "AVAILABLE" and v.slot_id is not None and await world.occupied(a) == 1


async def test_stale_expiry_cannot_overwrite_an_activation(world):
    a, svc, token = await _pending(world)
    stale = await svc.ride_repo.find_by_id(token.ride_id)
    await _raw_status(world, token.ride_id, "ACTIVE")
    result = await svc._expire_ride(stale)
    assert result.status == "ACTIVE"


async def test_cancel_pending_is_idempotent(client, world):
    a, svc, token = await _pending(world)
    for _ in range(2):
        r = await client.post(f"/api/v1/rides/{token.ride_id}/cancel", headers=world.headers)
        assert r.status_code == 200 and r.json()["data"]["status"] == "CANCELLED"
    # and the cancelled token can no longer unlock the scooter
    with pytest.raises(RideTokenInvalidError):
        await svc.confirm_ride(token.ride_token, a)


async def test_new_token_supersedes_the_old_one(world):
    a, svc, first = await _pending(world)
    second = await svc.request_ride_token(world.user_id, a)
    await world.db.commit()
    with pytest.raises(RideTokenInvalidError):
        await svc.confirm_ride(first.ride_token, a)
    ride = await svc.confirm_ride(second.ride_token, a)
    assert ride.status == "ACTIVE"
