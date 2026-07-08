import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dock_slot import DockSlot


class DockRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_slot_by_vehicle(self, dock_id: uuid.UUID, vehicle_id: uuid.UUID) -> DockSlot | None:
        result = await self.session.execute(
            select(DockSlot).where(DockSlot.dock_id == dock_id, DockSlot.vehicle_id == vehicle_id)
        )
        return result.scalar_one_or_none()

    async def release_slot(self, slot: DockSlot) -> DockSlot:
        slot.is_occupied = False
        slot.vehicle_id = None
        await self.session.flush()
        return slot
