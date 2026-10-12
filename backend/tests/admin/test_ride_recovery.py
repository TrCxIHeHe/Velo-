"""POST /admin/rides/{id}/recover — authorization, shared completion flow, invariants."""
import uuid

from sqlalchemy import select, update

from app.models import AuditLog, Ride, Vehicle


def url(ride_id):
    return f"/api/v1/admin/rides/{ride_id}/recover"


async def _active(world, *, fare="20.00", balance=100.0):
    a = await world.dock("A", vehicles=1)
    b = await world.dock("B")
    if fare:
        await world.fare(a, b, fare)
    await world.fund(balance)
    return a, b, await world.start_ride(a)


async def _ride(world, ride_id):
    return (await world.db.execute(
        select(Ride).where(Ride.id == ride_id).execution_options(populate_existing=True))).scalar_one()


async def test_authorization(client, world):
    a, b, ride = await _active(world)
    body = {"action": "complete", "dock_id": str(b), "reason": "stuck in dev"}
    assert (await client.post(url(ride.id), json=body)).status_code == 401
    forbidden = await client.post(url(ride.id), json=body, headers=world.headers)  # a normal user
    assert forbidden.status_code == 403
    assert (await _ride(world, ride.id)).status == "ACTIVE"


async def test_admin_completes_a_stuck_active_ride_through_the_normal_flow(client, world, admin_headers):
    a, b, ride = await _active(world, fare="20.00")
    r = await client.post(
        url(ride.id), headers=admin_headers,
        json={"action": "complete", "dock_id": str(b), "reason": "scooter never docked in dev"},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["status"] == "COMPLETED" and data["fare_amount"] == 20.0

    # same invariants as a normal end
    assert await world.balance() == 80.0 and len(await world.debits()) == 1
    assert await world.occupied(b) == 1 and await world.occupied(a) == 0
    v = await world.vehicle(ride.vehicle_id)
    assert v.status == "AVAILABLE" and v.slot_id is not None

    # audit trail names the admin, the reason and the action
    logs = (await world.db.execute(select(AuditLog))).scalars().all()
    rec = [l for l in logs if l.action == "RIDE_RECOVERED_COMPLETED"]
    assert len(rec) == 1 and "scooter never docked in dev" in rec[0].meta
    assert rec[0].user_id != world.user_id            # actor is the admin, not the rider

    # the rider can carry on testing without re-seeding
    assert (await world.service().request_ride_token(world.user_id, b)).ride_id


async def test_active_ride_cannot_be_just_cancelled(client, world, admin_headers):
    a, b, ride = await _active(world)
    r = await client.post(
        url(ride.id), headers=admin_headers, json={"action": "cancel_pending", "reason": "just clear it"}
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "RIDE_RECOVERY_FAILED"
    assert (await _ride(world, ride.id)).status == "ACTIVE"
    assert (await world.vehicle(ride.vehicle_id)).status == "IN_RIDE"


async def test_active_recovery_requires_an_explicit_destination(client, world, admin_headers):
    a, b, ride = await _active(world)
    r = await client.post(
        url(ride.id), headers=admin_headers, json={"action": "complete", "reason": "no destination"}
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "RIDE_RECOVERY_FAILED"


async def test_recovery_fails_cleanly_without_a_fare(client, world, admin_headers):
    a, b, ride = await _active(world, fare=None)
    r = await client.post(
        url(ride.id), headers=admin_headers,
        json={"action": "complete", "dock_id": str(b), "reason": "needs a tariff"},
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "FARE_NOT_CONFIGURED"
    assert (await _ride(world, ride.id)).status == "ACTIVE" and await world.occupied(b) == 0


async def test_insufficient_balance_rolls_everything_back(client, world, admin_headers):
    a, b, ride = await _active(world, fare="150.00", balance=100.0)
    r = await client.post(
        url(ride.id), headers=admin_headers,
        json={"action": "complete", "dock_id": str(b), "reason": "balance too low"},
    )
    assert r.status_code == 400 and r.json()["error"]["code"] == "WALLET_INSUFFICIENT_BALANCE"
    assert (await _ride(world, ride.id)).status == "ACTIVE"
    assert await world.occupied(b) == 0 and await world.balance() == 100.0
    logs = [l.action for l in (await world.db.execute(select(AuditLog))).scalars()]
    assert "RIDE_RECOVERED_COMPLETED" not in logs


async def test_inconsistent_vehicle_state_is_refused_with_diagnostics(client, world, admin_headers):
    a, b, ride = await _active(world)
    await world.db.execute(update(Vehicle).where(Vehicle.id == ride.vehicle_id).values(status="AVAILABLE"))
    await world.db.commit()
    r = await client.post(
        url(ride.id), headers=admin_headers,
        json={"action": "complete", "dock_id": str(b), "reason": "inconsistent test"},
    )
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "RIDE_RECOVERY_FAILED"
    assert "expected IN_RIDE" in err["message"] and "docs/pricing-and-ride-lifecycle.md" in err["message"]
    assert (await _ride(world, ride.id)).status == "ACTIVE" and await world.debits() == []


async def test_pending_ride_can_be_cancelled(client, world, admin_headers):
    a = await world.dock("A", vehicles=1)
    await world.fund(100)
    token = await world.service().request_ride_token(world.user_id, a)
    await world.db.commit()
    r = await client.post(
        url(token.ride_id), headers=admin_headers,
        json={"action": "cancel_pending", "reason": "stale qr in dev"},
    )
    assert r.status_code == 200 and r.json()["data"]["status"] == "CANCELLED"
    logs = [l.action for l in (await world.db.execute(select(AuditLog))).scalars()]
    assert "RIDE_RECOVERED_CANCELLED" in logs

    again = await client.post(
        url(token.ride_id), headers=admin_headers,
        json={"action": "cancel_pending", "reason": "stale qr in dev"},
    )
    assert again.status_code == 409          # nothing left to recover


async def test_completed_ride_is_not_recoverable_and_validation(client, world, admin_headers):
    a, b, ride = await _active(world)
    ok = {"action": "complete", "dock_id": str(b), "reason": "first recovery"}
    assert (await client.post(url(ride.id), json=ok, headers=admin_headers)).status_code == 200
    assert (await client.post(url(ride.id), json=ok, headers=admin_headers)).status_code == 409
    assert len(await world.debits()) == 1

    short = await client.post(url(ride.id), headers=admin_headers,
                              json={"action": "complete", "dock_id": str(b), "reason": "x"})
    assert short.status_code == 422
    ghost = await client.post(url(uuid.uuid4()), headers=admin_headers, json=ok)
    assert ghost.status_code == 404
