import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dock import Dock
from app.models.dock_slot import DockSlot


class DockRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, name: str, latitude: float, longitude: float, total_slots: int) -> Dock:
        dock = Dock(name=name, latitude=latitude, longitude=longitude, total_slots=total_slots)
        self.session.add(dock)
        await self.session.flush()

        for slot_number in range(1, total_slots + 1):
            self.session.add(DockSlot(dock_id=dock.id, slot_number=slot_number))
        await self.session.flush()
        return dock

    async def find_by_id(self, dock_id: uuid.UUID) -> Dock | None:
        result = await self.session.execute(select(Dock).where(Dock.id == dock_id))
        return result.scalar_one_or_none()

    async def list_active(self, limit: int = 50, offset: int = 0) -> list[Dock]:
        result = await self.session.execute(
            select(Dock).where(Dock.status == "ACTIVE").order_by(Dock.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def get_slots(self, dock_id: uuid.UUID) -> list[DockSlot]:
        result = await self.session.execute(
            select(DockSlot).where(DockSlot.dock_id == dock_id).order_by(DockSlot.slot_number)
        )
        return list(result.scalars().all())

    async def find_slot_by_id(self, slot_id: uuid.UUID) -> DockSlot | None:
        result = await self.session.execute(select(DockSlot).where(DockSlot.id == slot_id))
        return result.scalar_one_or_none()

    async def find_slot_by_vehicle(self, dock_id: uuid.UUID, vehicle_id: uuid.UUID) -> DockSlot | None:
        result = await self.session.execute(
            select(DockSlot).where(DockSlot.dock_id == dock_id, DockSlot.vehicle_id == vehicle_id)
        )
        return result.scalar_one_or_none()

    async def find_available_slot(self, dock_id: uuid.UUID) -> DockSlot | None:
        result = await self.session.execute(
            select(DockSlot)
            .where(DockSlot.dock_id == dock_id, DockSlot.is_occupied.is_(False))
            .order_by(DockSlot.slot_number)
            .limit(1)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def count_available_slots(self, dock_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(DockSlot).where(DockSlot.dock_id == dock_id, DockSlot.is_occupied.is_(False))
        )
        return result.scalar_one()

    async def occupy_slot(self, slot: DockSlot, vehicle_id: uuid.UUID) -> DockSlot:
        slot.is_occupied = True
        slot.vehicle_id = vehicle_id
        slot.is_charging = False
        await self.session.flush()
        return slot

    async def release_slot(self, slot: DockSlot) -> DockSlot:
        slot.is_occupied = False
        slot.vehicle_id = None
        slot.is_charging = False
        await self.session.flush()
        return slot

    async def count_docks(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(Dock))
        return result.scalar_one()

    async def count_all_slots(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(DockSlot))
        return result.scalar_one()

    async def count_occupied_slots(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(DockSlot).where(DockSlot.is_occupied.is_(True))
        )
        return result.scalar_one()
