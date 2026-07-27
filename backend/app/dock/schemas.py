from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class DockCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    location_lat: float
    location_lng: float
    address: str | None = None
    total_slots: int = Field(default=10, ge=1, le=100)


class DockUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    location_lat: float | None = None
    location_lng: float | None = None
    address: str | None = None
    is_active: bool | None = None


class VehicleCreate(BaseModel):
    qr_code: str = Field(..., min_length=1, max_length=128)
    vehicle_type: str = Field(default="SCOOTER")
    battery_level: int = Field(default=100, ge=0, le=100)
    slot_id: UUID | None = None


class VehicleStatusUpdate(BaseModel):
    battery_level: int | None = Field(default=None, ge=0, le=100)
    status: str | None = None  # AVAILABLE | IN_RIDE | MAINTENANCE


class SlotResponse(BaseModel):
    id: UUID
    slot_number: int
    is_occupied: bool
    model_config = {"from_attributes": True}


class VehicleResponse(BaseModel):
    id: UUID
    qr_code: str
    vehicle_type: str
    battery_level: int
    status: str
    slot_id: UUID | None
    model_config = {"from_attributes": True}


class DockResponse(BaseModel):
    id: UUID
    name: str
    location_lat: float
    location_lng: float
    address: str | None
    total_slots: int
    is_active: bool
    available_slots: int = 0
    created_at: datetime
    model_config = {"from_attributes": True}


class DockDetailResponse(DockResponse):
    slots: list[SlotResponse] = []
