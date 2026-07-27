from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.firebase import FirebaseService, get_firebase_service
from app.core.response import success_response
from app.database import get_db
from app.notifications.repository import NotificationRepository, UserDeviceRepository
from app.notifications.schemas import RegisterFcmTokenRequest
from app.notifications.service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


def get_notification_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    firebase: Annotated[FirebaseService, Depends(get_firebase_service)],
) -> NotificationService:
    return NotificationService(NotificationRepository(session), UserDeviceRepository(session), firebase)


NotificationServiceDep = Annotated[NotificationService, Depends(get_notification_service)]


@router.post("/device-token")
async def register_device_token(
    body: RegisterFcmTokenRequest, current_user: CurrentUser, service: NotificationServiceDep
):
    """Register/update the caller's FCM device token. Called by the app once
    on login and again whenever Firebase rotates the token."""
    await service.register_device(current_user.id, body.fcm_token)
    return success_response({"message": "Device token registered."})


@router.get("")
async def list_notifications(
    current_user: CurrentUser, service: NotificationServiceDep, skip: int = 0, limit: int = 20
):
    result = await service.list_notifications(current_user.id, skip, limit)
    return success_response(result.model_dump())
