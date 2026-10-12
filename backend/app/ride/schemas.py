from app.core.timeutil import UTCDateTime
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
    started_at: UTCDateTime | None
    ended_at: UTCDateTime | None
    duration_seconds: int | None
    fare_amount: float | None
    fare_currency: str
    pricing_strategy: str | None = None
    pricing_reference_id: UUID | None = None
    created_at: UTCDateTime
    model_config = {"from_attributes": True}


class RideListResponse(BaseModel):
    items: list[RideResponse]
    total: int
