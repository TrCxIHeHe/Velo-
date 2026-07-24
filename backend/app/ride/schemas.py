from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class RequestRideTokenRequest(BaseModel):
    dock_id: UUID


class ConfirmRideRequest(BaseModel):
    ride_token: str
    dock_id: UUID


class EndRideRequest(BaseModel):
    dock_id: UUID


class RideTokenResponse(BaseModel):
    ride_token: str
    ride_id: UUID
    expires_in_seconds: int


class RideResponse(BaseModel):
    id: UUID
    user_id: UUID
    vehicle_id: UUID | None
    start_dock_id: UUID
    end_dock_id: UUID | None
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    duration_seconds: int | None
    fare_amount: float | None
    fare_currency: str
    created_at: datetime
    model_config = {"from_attributes": True}


class RideListResponse(BaseModel):
    items: list[RideResponse]
    total: int
