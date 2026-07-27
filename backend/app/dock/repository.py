import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.dock import Dock, DockSlot, Vehicle


class DockRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, name: str, lat: float, lng: float, total_slots: int, address: str | None = None
    ) -> Dock:
        dock = Dock(name=name, location_lat=lat, location_lng=lng, total_slots=total_slots, address=address)
        self.session.add(dock)
        await self.session.flush()

        for i in range(1, total_slots + 1):
            self.session.add(DockSlot(dock_id=dock.id, slot_number=i))
        await self.session.flush()
        return dock

    async def find_by_id(self, dock_id: uuid.UUID) -> Dock | None:
        result = await self.session.execute(select(Dock).where(Dock.id == dock_id))
        return result.scalar_one_or_none()

    async def find_by_id_with_slots(self, dock_id: uuid.UUID) -> Dock | None:
        result = await self.session.execute(
            select(Dock)
            .where(Dock.id == dock_id)
            .options(selectinload(Dock.slots))
        )
        return result.scalar_one_or_none()

    async def list_active(self) -> list[Dock]:
        result = await self.session.execute(select(Dock).where(Dock.is_active.is_(True)).order_by(Dock.name))
        return list(result.scalars())

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Dock]:
        result = await self.session.execute(select(Dock).order_by(Dock.name).offset(skip).limit(limit))
        return list(result.scalars())

    async def update(self, dock_id: uuid.UUID, **kwargs) -> Dock | None:
        await self.session.execute(update(Dock).where(Dock.id == dock_id).values(**kwargs))
        await self.session.flush()
        return await self.find_by_id(dock_id)

    async def count_available_slots(self, dock_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count()).where(DockSlot.dock_id == dock_id, DockSlot.is_occupied.is_(False))
        )
        return result.scalar_one()

    async def find_free_slot(self, dock_id: uuid.UUID) -> DockSlot | None:
        result = await self.session.execute(
            select(DockSlot)
            .where(DockSlot.dock_id == dock_id, DockSlot.is_occupied.is_(False))
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        return result.scalar_one_or_none()

    async def occupy_slot(self, slot_id: uuid.UUID) -> None:
        await self.session.execute(update(DockSlot).where(DockSlot.id == slot_id).values(is_occupied=True))
        await self.session.flush()

    async def free_slot(self, slot_id: uuid.UUID) -> None:
        await self.session.execute(update(DockSlot).where(DockSlot.id == slot_id).values(is_occupied=False))
        await self.session.flush()

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


class VehicleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, qr_code: str, vehicle_type: str, battery_level: int, slot_id: uuid.UUID | None) -> Vehicle:
        vehicle = Vehicle(qr_code=qr_code, vehicle_type=vehicle_type, battery_level=battery_level, slot_id=slot_id)
        self.session.add(vehicle)
        await self.session.flush()
        return vehicle

    async def find_by_id(self, vehicle_id: uuid.UUID) -> Vehicle | None:
        result = await self.session.execute(select(Vehicle).where(Vehicle.id == vehicle_id))
        return result.scalar_one_or_none()

    async def find_available_in_dock(self, dock_id: uuid.UUID) -> Vehicle | None:
        result = await self.session.execute(
            select(Vehicle)
            .join(DockSlot, Vehicle.slot_id == DockSlot.id)
            .where(
                DockSlot.dock_id == dock_id,
                Vehicle.status == "AVAILABLE",
                Vehicle.battery_level >= 20,
            )
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        return result.scalar_one_or_none()

    async def set_status(self, vehicle_id: uuid.UUID, status: str) -> None:
        await self.session.execute(update(Vehicle).where(Vehicle.id == vehicle_id).values(status=status))
        await self.session.flush()

    async def update_slot(self, vehicle_id: uuid.UUID, slot_id: uuid.UUID | None) -> None:
        await self.session.execute(update(Vehicle).where(Vehicle.id == vehicle_id).values(slot_id=slot_id))
        await self.session.flush()

    async def update_vehicle(self, vehicle_id: uuid.UUID, **kwargs) -> Vehicle | None:
        await self.session.execute(update(Vehicle).where(Vehicle.id == vehicle_id).values(**kwargs))
        await self.session.flush()
        return await self.find_by_id(vehicle_id)

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Vehicle]:
        result = await self.session.execute(select(Vehicle).order_by(Vehicle.vehicle_type).offset(skip).limit(limit))
        return list(result.scalars())
