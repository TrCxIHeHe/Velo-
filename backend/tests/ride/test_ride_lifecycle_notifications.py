"""End-to-end RideService lifecycle test — this path (request token -> confirm
-> end) was previously only smoke-tested at the HTTP layer for auth guards;
nothing exercised the actual state transitions, fare settlement, or the
notification/audit side effects wired into confirm_ride/end_ride."""
import uuid
from unittest.mock import MagicMock

import pytest

from app.audit.repository import AuditLogRepository
from app.dock.repository import DockRepository, VehicleRepository
from app.dock.schemas import DockCreate, VehicleCreate
from app.dock.service import DockService
from app.notifications.repository import NotificationRepository, UserDeviceRepository
from app.notifications.service import NotificationService
from app.ride.repository import RideRepository
from app.ride.service import RideService
from app.wallet.repository import WalletRepository
from app.wallet.service import WalletService


async def _setup_dock_with_vehicle(db_session):
    dock_repo = DockRepository(db_session)
    vehicle_repo = VehicleRepository(db_session)
    dock_svc = DockService(dock_repo, vehicle_repo)

    dock = await dock_svc.create_dock(
        DockCreate(name="Lifecycle Test Dock", location_lat=1.0, location_lng=1.0, total_slots=2)
    )
    slot = await dock_repo.find_free_slot(dock.id)
    await dock_svc.add_vehicle(
        VehicleCreate(qr_code=f"qr-{uuid.uuid4()}", battery_level=100, slot_id=slot.id)
    )
    return dock.id


def _build_ride_service(db_session, firebase_mock) -> RideService:
    return RideService(
        RideRepository(db_session),
        DockRepository(db_session),
        VehicleRepository(db_session),
        WalletService(WalletRepository(db_session), AuditLogRepository(db_session)),
        AuditLogRepository(db_session),
        NotificationService(
            NotificationRepository(db_session), UserDeviceRepository(db_session), firebase_mock
        ),
    )


@pytest.mark.asyncio
async def test_full_ride_lifecycle_settles_fare_and_notifies(db_session):
    from app.models.user import User

    dock_id = await _setup_dock_with_vehicle(db_session)
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, firebase_uid=f"uid-{user_id}", phone_number="+910000077777"))
    await db_session.flush()

    wallet_service = WalletService(WalletRepository(db_session), AuditLogRepository(db_session))
    await wallet_service.top_up(user_id, 500.0)

    firebase_mock = MagicMock()
    firebase_mock.send_push.return_value = False  # no device token registered anyway
    ride_service = _build_ride_service(db_session, firebase_mock)

    token_result = await ride_service.request_ride_token(user_id, dock_id)
    assert token_result.ride_id is not None

    ride = await ride_service.confirm_ride(token_result.ride_token, dock_id)
    assert ride.status == "ACTIVE"
    assert ride.vehicle_id is not None

    ended = await ride_service.end_ride(user_id, ride.id, dock_id)
    assert ended.status == "COMPLETED"
    assert ended.fare_amount is not None and ended.fare_amount > 0

    wallet = await wallet_service.get_balance(user_id)
    assert wallet.balance == pytest.approx(500.0 - ended.fare_amount)

    notification_service = NotificationService(
        NotificationRepository(db_session), UserDeviceRepository(db_session), firebase_mock
    )
    result = await notification_service.list_notifications(user_id)
    types = {n.type for n in result.items}
    assert "RIDE_START" in types
    assert "RIDE_END" in types
