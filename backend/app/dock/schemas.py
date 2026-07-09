from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DockResponse(BaseModel):
    id: UUID
    name: str
    latitude: float
    longitude: float
    total_slots: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DockSlotResponse(BaseModel):
    id: UUID
    dock_id: UUID
    slot_number: int
    vehicle_id: UUID | None
    is_occupied: bool
    is_charging: bool

    model_config = {"from_attributes": True}


class DockWithSlotsResponse(DockResponse):
    slots: list[DockSlotResponse]
    available_slots: int


class CreateDockRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    latitude: float
    longitude: float
    total_slots: int = Field(..., gt=0, le=200)


class AssignVehicleRequest(BaseModel):
    vehicle_id: UUID
