import uuid

from app.core.firebase import FirebaseService
from app.notifications.repository import NotificationRepository, UserDeviceRepository
from app.notifications.schemas import NotificationListResponse, NotificationResponse


class NotificationService:
    def __init__(
        self,
        notification_repo: NotificationRepository,
        device_repo: UserDeviceRepository,
        firebase: FirebaseService,
    ) -> None:
        self.notification_repo = notification_repo
        self.device_repo = device_repo
        self.firebase = firebase

    async def register_device(self, user_id: uuid.UUID, fcm_token: str) -> None:
        await self.device_repo.set_fcm_token(user_id, fcm_token)

    async def notify(self, user_id: uuid.UUID, type_: str, title: str, body: str) -> None:
        """Send a push (best-effort) and persist a row either way.

        A missing device token or a Firebase outage must never surface as an
        error to the caller — this is always called as a side effect of a
        ride/wallet operation that has already succeeded.
        """
        fcm_token = await self.device_repo.get_fcm_token(user_id)
        sent = False
        if fcm_token:
            sent = self.firebase.send_push(fcm_token, title, body)
        await self.notification_repo.create(user_id, type_, title, body, sent)

    async def list_notifications(
        self, user_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> NotificationListResponse:
        items, total = await self.notification_repo.list_for_user(user_id, skip, limit)
        return NotificationListResponse(
            items=[NotificationResponse.model_validate(n) for n in items],
            total=total,
        )
