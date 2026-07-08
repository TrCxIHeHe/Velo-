import uuid

import fakeredis.aioredis
import pytest

from app.core.exceptions import (
    DockMismatchError,
    RideAlreadyActiveError,
    RideForbiddenError,
    RideInvalidStateError,
    RideNotFoundError,
    RideTokenInvalidError,
    RideTokenReusedError,
    VehicleUnavailableError,
)
from app.dock.repository import DockRepository
from app.models.dock import Dock
from app.models.vehicle import Vehicle
from app.ride.event_repository import RideEventRepository
from app.ride.repository import RideRepository, VehicleRepository
from app.ride.service import RideService
from app.ride.token_codec import RideTokenCodec


@pytest.fixture
async def fake_redis():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.flushall()
    await client.aclose()


@pytest.fixture
def ride_service(db_session, fake_redis):
    return RideService(
        RideRepository(db_session),
        VehicleRepository(db_session),
        DockRepository(db_session),
        RideEventRepository(db_session),
        RideTokenCodec(fake_redis),
    )


async def _seed_dock_and_vehicle(db_session, battery=85, status="AVAILABLE"):
    dock = Dock(name="Test Dock", latitude=1.0, longitude=1.0, total_slots=4, status="ACTIVE")
    db_session.add(dock)
    await db_session.flush()
    vehicle = Vehicle(qr_code=f"qr-{uuid.uuid4()}", status=status, battery_pct=battery, dock_id=dock.id)
    db_session.add(vehicle)
    await db_session.flush()
    await db_session.commit()
    return dock, vehicle


class TestRequestRide:
    async def test_assigns_available_vehicle(self, ride_service, db_session):
        user_id = uuid.uuid4()
        dock, vehicle = await _seed_dock_and_vehicle(db_session)

        ride = await ride_service.request_ride(user_id)

        assert ride.status == "ASSIGNED"
        assert ride.vehicle_id == vehicle.id
        assert ride.dock_start_id == dock.id

    async def test_no_vehicle_available_raises(self, ride_service):
        with pytest.raises(VehicleUnavailableError):
            await ride_service.request_ride(uuid.uuid4())

    async def test_low_battery_vehicle_not_assigned(self, ride_service, db_session):
        await _seed_dock_and_vehicle(db_session, battery=5)
        with pytest.raises(VehicleUnavailableError):
            await ride_service.request_ride(uuid.uuid4())

    async def test_maintenance_vehicle_not_assigned(self, ride_service, db_session):
        await _seed_dock_and_vehicle(db_session, status="MAINTENANCE")
        with pytest.raises(VehicleUnavailableError):
            await ride_service.request_ride(uuid.uuid4())

    async def test_second_request_while_active_raises(self, ride_service, db_session):
        user_id = uuid.uuid4()
        await _seed_dock_and_vehicle(db_session)
        await ride_service.request_ride(user_id)

        with pytest.raises(RideAlreadyActiveError):
            await ride_service.request_ride(user_id)


class TestIssueRideToken:
    async def test_issues_token_for_assigned_ride(self, ride_service, db_session):
        user_id = uuid.uuid4()
        await _seed_dock_and_vehicle(db_session)
        await ride_service.request_ride(user_id)

        token = await ride_service.issue_ride_token(user_id)

        assert token.expires_in == 30
        assert token.ride_token

    async def test_no_active_ride_raises(self, ride_service):
        with pytest.raises(RideInvalidStateError):
            await ride_service.issue_ride_token(uuid.uuid4())


class TestValidateToken:
    async def test_valid_token_moves_to_unlock_pending(self, ride_service, db_session):
        user_id = uuid.uuid4()
        dock, vehicle = await _seed_dock_and_vehicle(db_session)
        ride = await ride_service.request_ride(user_id)
        token = await ride_service.issue_ride_token(user_id)

        result = await ride_service.validate_token(dock.id, token.ride_token)

        assert result.status == "UNLOCK_PENDING"
        assert result.ride_id == ride.id

    async def test_reused_token_raises(self, ride_service, db_session):
        user_id = uuid.uuid4()
        dock, vehicle = await _seed_dock_and_vehicle(db_session)
        await ride_service.request_ride(user_id)
        token = await ride_service.issue_ride_token(user_id)

        await ride_service.validate_token(dock.id, token.ride_token)
        with pytest.raises(RideTokenReusedError):
            await ride_service.validate_token(dock.id, token.ride_token)

    async def test_garbage_token_raises_invalid(self, ride_service, db_session):
        dock, _ = await _seed_dock_and_vehicle(db_session)
        with pytest.raises(RideTokenInvalidError):
            await ride_service.validate_token(dock.id, "not_a_real_jwt")

    async def test_wrong_dock_raises_mismatch(self, ride_service, db_session):
        user_id = uuid.uuid4()
        dock, vehicle = await _seed_dock_and_vehicle(db_session)
        other_dock = Dock(name="Other", latitude=2.0, longitude=2.0, total_slots=2, status="ACTIVE")
        db_session.add(other_dock)
        await db_session.flush()
        await db_session.commit()

        await ride_service.request_ride(user_id)
        token = await ride_service.issue_ride_token(user_id)

        with pytest.raises(DockMismatchError):
            await ride_service.validate_token(other_dock.id, token.ride_token)


class TestAuthorizeUnlock:
    async def test_unlock_moves_ride_active_and_vehicle_in_use(self, ride_service, db_session):
        user_id = uuid.uuid4()
        dock, vehicle = await _seed_dock_and_vehicle(db_session)
        ride = await ride_service.request_ride(user_id)
        token = await ride_service.issue_ride_token(user_id)
        await ride_service.validate_token(dock.id, token.ride_token)

        result = await ride_service.authorize_unlock(dock.id, ride.id)

        assert result.status == "ACTIVE"
        assert result.vehicle_id == vehicle.id

        updated_vehicle = await VehicleRepository(db_session).find_by_id(vehicle.id)
        assert updated_vehicle.status == "IN_USE"

    async def test_unlock_without_validate_raises_invalid_state(self, ride_service, db_session):
        user_id = uuid.uuid4()
        dock, vehicle = await _seed_dock_and_vehicle(db_session)
        ride = await ride_service.request_ride(user_id)

        with pytest.raises(RideInvalidStateError):
            await ride_service.authorize_unlock(dock.id, ride.id)

    async def test_unlock_nonexistent_ride_raises_not_found(self, ride_service, db_session):
        dock, _ = await _seed_dock_and_vehicle(db_session)
        with pytest.raises(RideNotFoundError):
            await ride_service.authorize_unlock(dock.id, uuid.uuid4())


class TestGetRide:
    async def test_owner_can_view(self, ride_service, db_session):
        user_id = uuid.uuid4()
        await _seed_dock_and_vehicle(db_session)
        ride = await ride_service.request_ride(user_id)

        fetched = await ride_service.get_ride(ride.id, user_id)
        assert fetched.id == ride.id

    async def test_non_owner_forbidden(self, ride_service, db_session):
        user_id = uuid.uuid4()
        await _seed_dock_and_vehicle(db_session)
        ride = await ride_service.request_ride(user_id)

        with pytest.raises(RideForbiddenError):
            await ride_service.get_ride(ride.id, uuid.uuid4())

    async def test_nonexistent_ride_not_found(self, ride_service):
        with pytest.raises(RideNotFoundError):
            await ride_service.get_ride(uuid.uuid4(), uuid.uuid4())
