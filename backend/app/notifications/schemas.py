from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RegisterFcmTokenRequest(BaseModel):
    fcm_token: str = Field(..., min_length=1, max_length=255)


class NotificationResponse(BaseModel):
    id: UUID
    type: str
    title: str
    body: str
    sent_at: datetime | None
    read_at: datetime | None
    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
