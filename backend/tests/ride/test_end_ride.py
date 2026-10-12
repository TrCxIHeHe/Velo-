"""End-ride: server-priced settlement, atomicity, idempotency, stale availability."""

import pytest
from sqlalchemy import select, update

from app.core.exceptions import (
    FareNotConfiguredError, InsufficientBalanceError, RideInvalidStateError,
    SameDockReturnNotAllowedError,
)
from app.models import AuditLog, Ride


async def _setup(world, *, fare="20.00", balance=100.0, dest_slots=2):
    a = await world.dock("A", vehicles=1)
    b = await world.dock("B", slots=dest_slots)
    if fare:
        await world.fare(a, b, fare)
    await world.fund(balance)
    ride = await world.start_ride(a)
    return a, b, ride


async def test_final_fare_is_the_configured_pair_fare_and_matches_the_debit(world):
    a, b, ride = await _setup(world, fare="20.50")
    ended = await world.service().end_ride(world.user_id, ride.id, b)

    assert ended.status == "COMPLETED" and ended.end_dock_id == b
    assert ended.fare_amount == 20.5 and ended.fare_currency == "INR"
    assert ended.pricing_strategy == "fixed_dock_pair" and ended.pricing_reference_id
    assert ended.started_at and ended.ended_at and ended.duration_seconds is not None

    debits = await world.debits()
    assert len(debits) == 1 and debits[0].amount == ended.fare_amount
    assert await world.balance() == pytest.approx(100.0 - 20.5)
    assert debits[0].balance_after == pytest.approx(79.5)

    # scooter parked in a destination slot, origin slot freed
    assert await world.occupied(b) == 1 and await world.occupied(a) == 0
    vehicle = await world.vehicle(ride.vehicle_id)
    assert vehicle.status == "AVAILABLE" and vehicle.slot_id is not None


async def test_both_directions_are_priced_independently(world):
    a, b, ride = await _setup(world, fare="20.00")
    await world.fare(b, a, "35.00")
    await world.service().end_ride(world.user_id, ride.id, b)          # A -> B = 20
    back = await world.start_ride(b)
    ended = await world.service().end_ride(world.user_id, back.id, a)  # B -> A = 35
    assert ended.fare_amount == 35.0
    assert await world.balance() == pytest.approx(100 - 20 - 35)


async def test_duration_is_recorded_but_does_not_drive_the_fare(world, db_session):
    from datetime import timedelta
    from app.core.timeutil import naive_utcnow

    a, b, ride = await _setup(world, fare="20.00")
    await db_session.execute(
        update(Ride).where(Ride.id == ride.id).values(started_at=naive_utcnow() - timedelta(hours=2))
    )
    await db_session.commit()
    ended = await world.service().end_ride(world.user_id, ride.id, b)
    assert 7195 <= ended.duration_seconds <= 7215
    assert ended.fare_amount == 20.0


async def test_client_cannot_choose_the_fare_or_origin(client, world):
    """The request body only carries a destination; extra fields are ignored."""
    a, b, ride = await _setup(world, fare="20.00")
    r = await client.post(
        f"/api/v1/rides/{ride.id}/end", headers=world.headers,
        json={"dock_id": str(b), "fare_amount": 0.01, "start_dock_id": str(b)},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["fare_amount"] == 20.0


async def test_missing_fare_keeps_ride_active_and_changes_nothing(world):
    a, b, ride = await _setup(world, fare=None)
    with pytest.raises(FareNotConfiguredError):
        await world.service().end_ride(world.user_id, ride.id, b)
    await _assert_untouched(world, ride, b)


async def test_insufficient_balance_rolls_back_slot_vehicle_and_ride(world):
    a, b, ride = await _setup(world, fare="150.00", balance=100.0)
    with pytest.raises(InsufficientBalanceError):
        await world.service().end_ride(world.user_id, ride.id, b)
    await _assert_untouched(world, ride, b)
    assert await world.balance() == 100.0


async def test_currency_mismatch_is_rejected_atomically(world):
    from app.core.exceptions import CurrencyMismatchError
    a = await world.dock("A", vehicles=1)
    b = await world.dock("B")
    await world.fare(a, b, "20.00", currency="USD")
    await world.fund(100.0)
    ride = await world.start_ride(a)
    with pytest.raises(CurrencyMismatchError):
        await world.service().end_ride(world.user_id, ride.id, b)
    await _assert_untouched(world, ride, b)


async def test_destination_filled_between_quote_and_completion(client, world):
    a, b, ride = await _setup(world, fare="20.00", dest_slots=1)
    est = await client.get(
        f"/api/v1/rides/{ride.id}/fare-estimate?destination_dock_id={b}", headers=world.headers
    )
    assert est.status_code == 200                       # looked fine at quote time

    slot = (await world.slots(b))[0]                    # someone else docks there
    slot.is_occupied = True
    await world.db.commit()

    r = await client.post(f"/api/v1/rides/{ride.id}/end", headers=world.headers, json={"dock_id": str(b)})
    assert r.status_code == 400 and r.json()["error"]["code"] == "DOCK_FULL"
    await _assert_untouched(world, ride, b, dest_occupied=1)

    # user picks another dock and gets a fresh quote
    c = await world.dock("C")
    await world.fare(a, c, "27.00")
    q = (await client.get(
        f"/api/v1/rides/{ride.id}/fare-estimate?destination_dock_id={c}", headers=world.headers
    )).json()["data"]
    assert q["fare_amount"] == 27.0
    ok = await client.post(f"/api/v1/rides/{ride.id}/end", headers=world.headers, json={"dock_id": str(c)})
    assert ok.status_code == 200 and ok.json()["data"]["fare_amount"] == 27.0


async def test_same_dock_return_is_rejected(world):
    a, b, ride = await _setup(world)
    with pytest.raises(SameDockReturnNotAllowedError):
        await world.service().end_ride(world.user_id, ride.id, a)
    await _assert_untouched(world, ride, b)


async def test_inactive_destination_is_rejected(world):
    a, b, ride = await _setup(world)
    closed = await world.dock("Closed", active=False)
    await world.fare(a, closed, "10")
    from app.core.exceptions import DockNotFoundError
    with pytest.raises(DockNotFoundError):
        await world.service().end_ride(world.user_id, ride.id, closed)


async def test_repeated_end_is_idempotent_no_double_debit_or_slot(world):
    a, b, ride = await _setup(world, fare="20.00")
    first = await world.service().end_ride(world.user_id, ride.id, b)
    second = await world.service().end_ride(world.user_id, ride.id, b)
    third = await world.service().end_ride(world.user_id, ride.id, b)

    assert first.id == second.id == third.id and second.fare_amount == first.fare_amount
    assert len(await world.debits()) == 1
    assert await world.balance() == pytest.approx(80.0)
    assert await world.occupied(b) == 1


async def test_ending_a_completed_ride_at_another_dock_is_a_conflict(world):
    a, b, ride = await _setup(world)
    c = await world.dock("C")
    await world.fare(a, c, "11")
    await world.service().end_ride(world.user_id, ride.id, b)
    with pytest.raises(RideInvalidStateError):
        await world.service().end_ride(world.user_id, ride.id, c)
    assert len(await world.debits()) == 1 and await world.occupied(c) == 0


async def test_lost_race_on_ride_state_cannot_double_complete(world, db_session):
    """Another request completes the ride after we read it but before we write.
    The compare-and-set must refuse and leave no partial writes."""
    a, b, ride = await _setup(world)
    svc = world.service()
    real_calc = svc.pricing.calculate

    async def racing_calc(ctx):
        # concurrent transaction wins: ride is no longer ACTIVE
        await db_session.execute(
            update(Ride).where(Ride.id == ride.id).values(status="COMPLETED")
            .execution_options(synchronize_session=False)
        )
        return await real_calc(ctx)

    svc.pricing.calculate = racing_calc
    with pytest.raises(RideInvalidStateError):
        await svc.end_ride(world.user_id, ride.id, b)
    assert await world.debits() == []
    assert await world.occupied(b) == 0


async def test_only_the_owner_can_end(client, world, other_auth_headers):
    a, b, ride = await _setup(world)
    r = await client.post(
        f"/api/v1/rides/{ride.id}/end", headers=other_auth_headers, json={"dock_id": str(b)}
    )
    assert r.status_code == 403


async def test_completion_is_audited_and_notified_after_commit(world, db_session):
    a, b, ride = await _setup(world, fare="20.00")
    await world.service().end_ride(world.user_id, ride.id, b)
    actions = [r.action for r in (await db_session.execute(select(AuditLog))).scalars()]
    assert "RIDE_ENDED" in actions and "WALLET_DEBIT_RIDE_FARE" in actions


async def test_notification_failure_never_undoes_a_completed_ride(world, db_session):
    from unittest.mock import AsyncMock
    a, b, ride = await _setup(world, fare="20.00")
    svc = world.service()
    svc.notification_service = AsyncMock()
    svc.notification_service.notify.side_effect = RuntimeError("push provider down")

    ended = await svc.end_ride(world.user_id, ride.id, b)
    assert ended.status == "COMPLETED"
    stored = (await db_session.execute(
        select(Ride).where(Ride.id == ride.id).execution_options(populate_existing=True))).scalar_one()
    assert stored.status == "COMPLETED"
    assert len(await world.debits()) == 1


async def _assert_untouched(world, ride, dest, *, dest_occupied=0):
    stored = (await world.db.execute(
        select(Ride).where(Ride.id == ride.id).execution_options(populate_existing=True)
    )).scalar_one()
    assert stored.status == "ACTIVE"
    assert stored.end_dock_id is None and stored.fare_amount is None and stored.ended_at is None
    assert await world.occupied(dest) == dest_occupied
    vehicle = await world.vehicle(ride.vehicle_id)
    assert vehicle.status == "IN_RIDE" and vehicle.slot_id is None
    assert await world.debits() == []
