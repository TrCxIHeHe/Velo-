import uuid
from unittest.mock import MagicMock

import pytest

from app.notifications.repository import NotificationRepository, UserDeviceRepository
from app.notifications.service import NotificationService


def _fake_firebase(send_result: bool = True) -> MagicMock:
    mock = MagicMock()
    mock.send_push.return_value = send_result
    return mock


@pytest.mark.asyncio
async def test_notify_without_device_token_persists_unsent(db_session):
    firebase = _fake_firebase()
    svc = NotificationService(NotificationRepository(db_session), UserDeviceRepository(db_session), firebase)
    user_id = uuid.uuid4()

    await svc.notify(user_id, "RIDE_START", "Ride started", "Have a safe trip!")

    result = await svc.list_notifications(user_id)
    assert result.total == 1
    assert result.items[0].sent_at is None
    firebase.send_push.assert_not_called()


@pytest.mark.asyncio
async def test_notify_with_device_token_sends_push_and_marks_sent(db_session):
    firebase = _fake_firebase(send_result=True)
    device_repo = UserDeviceRepository(db_session)
    svc = NotificationService(NotificationRepository(db_session), device_repo, firebase)
    user_id = uuid.uuid4()

    from app.models.user import User
    db_session.add(User(id=user_id, firebase_uid="fcm-test-uid", phone_number="+910000088888"))
    await db_session.flush()
    await device_repo.set_fcm_token(user_id, "device-token-abc")

    await svc.notify(user_id, "LOW_BALANCE", "Low balance", "Top up now")

    result = await svc.list_notifications(user_id)
    assert result.total == 1
    assert result.items[0].sent_at is not None
    firebase.send_push.assert_called_once_with("device-token-abc", "Low balance", "Top up now")


@pytest.mark.asyncio
async def test_notify_survives_fcm_failure(db_session):
    """A dead token or Firebase outage must not raise — the caller is always
    mid-way through a ride/wallet operation that has already succeeded."""
    firebase = _fake_firebase(send_result=False)
    device_repo = UserDeviceRepository(db_session)
    svc = NotificationService(NotificationRepository(db_session), device_repo, firebase)
    user_id = uuid.uuid4()

    from app.models.user import User
    db_session.add(User(id=user_id, firebase_uid="fcm-test-uid-2", phone_number="+910000088887"))
    await db_session.flush()
    await device_repo.set_fcm_token(user_id, "dead-token")

    await svc.notify(user_id, "RIDE_END", "Ride ended", "Fare charged")

    result = await svc.list_notifications(user_id)
    assert result.total == 1
    assert result.items[0].sent_at is None
