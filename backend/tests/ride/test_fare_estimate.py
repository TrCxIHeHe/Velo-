"""GET /rides/{id}/fare-estimate — read-only server quote."""
import uuid

from sqlalchemy import func, select

from app.models import AuditLog, Ride, WalletTransaction


def url(ride_id, dest):
    return f"/api/v1/rides/{ride_id}/fare-estimate?destination_dock_id={dest}"


async def _active(world, *, fare="20.00", balance=100.0):
    a = await world.dock("A", vehicles=1)
    b = await world.dock("B", slots=2)
    if fare:
        await world.fare(a, b, fare)
    await world.fund(balance)
    ride = await world.start_ride(a)
    return a, b, ride


async def test_requires_auth(client):
    r = await client.get(url(uuid.uuid4(), uuid.uuid4()))
    assert r.status_code == 401


async def test_returns_configured_pair_fare(client, world):
    a, b, ride = await _active(world, fare="20.50")
    r = await client.get(url(ride.id, b), headers=world.headers)
    assert r.status_code == 200, r.text
    q = r.json()["data"]
    assert q["ride_id"] == str(ride.id)
    assert q["origin_dock_id"] == str(a)           # derived from the stored ride
    assert q["destination_dock_id"] == str(b)
    assert q["fare_amount"] == 20.5 and q["currency"] == "INR"
    assert q["pricing_strategy"] == "fixed_dock_pair"
    assert q["pricing_reference_id"]
    assert q["wallet_balance"] == 100.0 and q["sufficient_balance"] is True


async def test_flags_insufficient_balance(client, world):
    _, b, ride = await _active(world, fare="150.00", balance=100.0)
    q = (await client.get(url(ride.id, b), headers=world.headers)).json()["data"]
    assert q["sufficient_balance"] is False


async def test_does_not_mutate_anything(client, world, db_session):
    _, b, ride = await _active(world)
    before_balance = await world.balance()
    before_occupied = await world.occupied(b)
    before_audit = (await db_session.execute(select(func.count()).select_from(AuditLog))).scalar_one()

    for _ in range(3):
        assert (await client.get(url(ride.id, b), headers=world.headers)).status_code == 200

    stored = (await db_session.execute(select(Ride).where(Ride.id == ride.id))).scalar_one()
    assert stored.status == "ACTIVE" and stored.fare_amount is None and stored.end_dock_id is None
    assert await world.occupied(b) == before_occupied
    assert await world.balance() == before_balance
    assert (await db_session.execute(select(func.count()).select_from(WalletTransaction).where(
        WalletTransaction.source == "RIDE_FARE"))).scalar_one() == 0
    assert (await db_session.execute(select(func.count()).select_from(AuditLog))).scalar_one() == before_audit


async def test_other_users_ride_is_forbidden(client, world, other_auth_headers):
    _, b, ride = await _active(world)
    r = await client.get(url(ride.id, b), headers=other_auth_headers)
    assert r.status_code == 403 and r.json()["error"]["code"] == "RIDE_FORBIDDEN"


async def test_unknown_ride_is_404(client, world):
    b = await world.dock("B")
    r = await client.get(url(uuid.uuid4(), b), headers=world.headers)
    assert r.status_code == 404


async def test_ride_must_be_active(client, world):
    a = await world.dock("A", vehicles=1)
    b = await world.dock("B")
    await world.fund(100)
    token = await world.service().request_ride_token(world.user_id, a)  # PENDING only
    await world.db.commit()
    r = await client.get(url(token.ride_id, b), headers=world.headers)
    assert r.status_code == 409 and r.json()["error"]["code"] == "RIDE_INVALID_STATE"


async def test_destination_validation(client, world):
    a, b, ride = await _active(world)
    inactive = await world.dock("Closed", active=False)
    full = await world.dock("Full", slots=1, vehicles=1)
    await world.fare(a, inactive, "10")
    await world.fare(a, full, "10")

    ghost = await client.get(url(ride.id, uuid.uuid4()), headers=world.headers)
    assert ghost.status_code == 404 and ghost.json()["error"]["code"] == "DOCK_NOT_FOUND"
    closed = await client.get(url(ride.id, inactive), headers=world.headers)
    assert closed.status_code == 404
    no_slot = await client.get(url(ride.id, full), headers=world.headers)
    assert no_slot.status_code == 400 and no_slot.json()["error"]["code"] == "DOCK_FULL"
    same = await client.get(url(ride.id, a), headers=world.headers)
    assert same.status_code == 400 and same.json()["error"]["code"] == "RIDE_SAME_DOCK_NOT_ALLOWED"


async def test_missing_or_inactive_fare_is_an_actionable_error(client, world):
    a, b, ride = await _active(world, fare=None)
    r = await client.get(url(ride.id, b), headers=world.headers)
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "FARE_NOT_CONFIGURED" and "admin" in err["message"].lower()

    await world.fare(a, b, "20", active=False)
    assert (await client.get(url(ride.id, b), headers=world.headers)).status_code == 409


async def test_reverse_pair_uses_its_own_fare(client, world):
    a, b, ride = await _active(world, fare="20.00")
    # fare B->A is irrelevant for a ride that started at A
    await world.fare(b, a, "99.00")
    q = (await client.get(url(ride.id, b), headers=world.headers)).json()["data"]
    assert q["fare_amount"] == 20.0
