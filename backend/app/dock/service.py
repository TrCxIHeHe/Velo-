import uuid

from app.dock.repository import DockRepository
from app.dock.schemas import DockResponse, DockSlotResponse, DockWithSlotsResponse
from app.core.exceptions import DockFullError, DockNotFoundError, SlotNotFoundError, SlotOccupiedError


class DockService:
    def __init__(self, repo: DockRepository) -> None:
        self.repo = repo

    async def create_dock(self, name: str, latitude: float, longitude: float, total_slots: int) -> DockResponse:
        dock = await self.repo.create(name, latitude, longitude, total_slots)
        return DockResponse.model_validate(dock)

    async def list_docks(self, limit: int = 50, offset: int = 0) -> list[DockResponse]:
        docks = await self.repo.list_active(limit, offset)
        return [DockResponse.model_validate(d) for d in docks]

    async def get_dock(self, dock_id: uuid.UUID) -> DockWithSlotsResponse:
        dock = await self.repo.find_by_id(dock_id)
        if dock is None:
            raise DockNotFoundError()
        slots = await self.repo.get_slots(dock_id)
        available = sum(1 for s in slots if not s.is_occupied)
        return DockWithSlotsResponse(
            **DockResponse.model_validate(dock).model_dump(),
            slots=[DockSlotResponse.model_validate(s) for s in slots],
            available_slots=available,
        )

    async def assign_vehicle(self, dock_id: uuid.UUID, vehicle_id: uuid.UUID) -> DockSlotResponse:
        dock = await self.repo.find_by_id(dock_id)
        if dock is None:
            raise DockNotFoundError()
        slot = await self.repo.find_available_slot(dock_id)
        if slot is None:
            raise DockFullError()
        slot = await self.repo.occupy_slot(slot, vehicle_id)
        return DockSlotResponse.model_validate(slot)

    async def release_vehicle(self, dock_id: uuid.UUID, slot_id: uuid.UUID) -> DockSlotResponse:
        slot = await self.repo.find_slot_by_id(slot_id)
        if slot is None or slot.dock_id != dock_id:
            raise SlotNotFoundError()
        if not slot.is_occupied:
            raise SlotOccupiedError("This slot is already empty — nothing to release.")
        slot = await self.repo.release_slot(slot)
        return DockSlotResponse.model_validate(slot)
