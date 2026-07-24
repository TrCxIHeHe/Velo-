import uuid

from app.core.exceptions import DockNotFoundError, DockFullError, SlotNotFoundError
from app.dock.repository import DockRepository, VehicleRepository
from app.dock.schemas import (
    DockCreate, DockDetailResponse, DockResponse, DockUpdate,
    SlotResponse, VehicleCreate, VehicleResponse, VehicleStatusUpdate,
)


def _dock_to_response(dock, available_slots: int = 0) -> DockResponse:
    return DockResponse(
        id=dock.id,
        name=dock.name,
        location_lat=dock.location_lat,
        location_lng=dock.location_lng,
        address=dock.address,
        total_slots=dock.total_slots,
        is_active=dock.is_active,
        available_slots=available_slots,
        created_at=dock.created_at,
    )


class DockService:
    def __init__(self, dock_repo: DockRepository, vehicle_repo: VehicleRepository) -> None:
        self.dock_repo = dock_repo
        self.vehicle_repo = vehicle_repo

    async def create_dock(self, data: DockCreate) -> DockResponse:
        dock = await self.dock_repo.create(data.name, data.location_lat, data.location_lng, data.total_slots, data.address)
        return _dock_to_response(dock, available_slots=dock.total_slots)

    async def get_dock(self, dock_id: uuid.UUID) -> DockDetailResponse:
        dock = await self.dock_repo.find_by_id_with_slots(dock_id)
        if not dock:
            raise DockNotFoundError()
        available = await self.dock_repo.count_available_slots(dock_id)
        return DockDetailResponse(
            id=dock.id,
            name=dock.name,
            location_lat=dock.location_lat,
            location_lng=dock.location_lng,
            address=dock.address,
            total_slots=dock.total_slots,
            is_active=dock.is_active,
            available_slots=available,
            created_at=dock.created_at,
            slots=[SlotResponse.model_validate(s) for s in dock.slots],
        )

    async def list_docks(self, active_only: bool = True) -> list[DockResponse]:
        if active_only:
            docks = await self.dock_repo.list_active()
        else:
            docks = await self.dock_repo.list_all()
        result = []
        for dock in docks:
            available = await self.dock_repo.count_available_slots(dock.id)
            result.append(_dock_to_response(dock, available))
        return result

    async def update_dock(self, dock_id: uuid.UUID, data: DockUpdate) -> DockResponse:
        dock = await self.dock_repo.find_by_id(dock_id)
        if not dock:
            raise DockNotFoundError()
        updates = data.model_dump(exclude_none=True)
        if updates:
            dock = await self.dock_repo.update(dock_id, **updates)
        available = await self.dock_repo.count_available_slots(dock_id)
        return _dock_to_response(dock, available)

    async def add_vehicle(self, data: VehicleCreate) -> VehicleResponse:
        if data.slot_id:
            # mark the slot as occupied
            await self.dock_repo.occupy_slot(data.slot_id)
        vehicle = await self.vehicle_repo.create(data.qr_code, data.vehicle_type, data.battery_level, data.slot_id)
        return VehicleResponse.model_validate(vehicle)

    async def update_vehicle(self, vehicle_id: uuid.UUID, data: VehicleStatusUpdate) -> VehicleResponse:
        updates = data.model_dump(exclude_none=True)
        vehicle = await self.vehicle_repo.update_vehicle(vehicle_id, **updates)
        if not vehicle:
            from app.core.exceptions import DockNotFoundError
            raise DockNotFoundError()
        return VehicleResponse.model_validate(vehicle)

    async def list_vehicles(self, skip: int = 0, limit: int = 100) -> list[VehicleResponse]:
        vehicles = await self.vehicle_repo.list_all(skip, limit)
        return [VehicleResponse.model_validate(v) for v in vehicles]
