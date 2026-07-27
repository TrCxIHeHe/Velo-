import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.models.user import User


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, user_id: uuid.UUID, type_: str, title: str, body: str, sent: bool) -> Notification:
        notification = Notification(
            user_id=user_id,
            type=type_,
            title=title,
            body=body,
            sent_at=datetime.now(timezone.utc).replace(tzinfo=None) if sent else None,
        )
        self.session.add(notification)
        await self.session.flush()
        return notification

    async def list_for_user(
        self, user_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> tuple[list[Notification], int]:
        total = (
            await self.session.execute(
                select(func.count()).where(Notification.user_id == user_id)
            )
        ).scalar_one()
        result = await self.session.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.id.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars()), total


class UserDeviceRepository:
    """Minimal repository for the one column NotificationService needs from
    User — kept separate from AuthRepository's UserRepository so this module
    doesn't need to import across the auth/ boundary for a single column."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def set_fcm_token(self, user_id: uuid.UUID, fcm_token: str) -> None:
        await self.session.execute(update(User).where(User.id == user_id).values(fcm_token=fcm_token))
        await self.session.flush()

    async def get_fcm_token(self, user_id: uuid.UUID) -> str | None:
        result = await self.session.execute(select(User.fcm_token).where(User.id == user_id))
        return result.scalar_one_or_none()
