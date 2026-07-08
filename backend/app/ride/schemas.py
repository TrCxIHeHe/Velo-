from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RideResponse(BaseModel):
    id: UUID
    user_id: UUID
    vehicle_id: UUID | None
    dock_start_id: UUID | None
    dock_end_id: UUID | None
    status: str
    fare: float | None
    start_at: datetime | None
    end_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RideStatusResponse(BaseModel):
    id: UUID
    status: str


class RideTokenResponse(BaseModel):
    """Encoded client-side as the QR shown to the dock scanner."""
    ride_token: str
    expires_in: int
    expires_at: datetime


class ValidateTokenRequest(BaseModel):
    ride_token: str = Field(..., description="Token from POST /ride/token, scanned at the dock")


class ValidateTokenResponse(BaseModel):
    ride_id: UUID
    status: str


class UnlockRequest(BaseModel):
    ride_id: UUID = Field(..., description="Ride returned by /docks/{id}/validate")


class UnlockResponse(BaseModel):
    ride_id: UUID
    status: str
    vehicle_id: UUID
    started_at: datetime
