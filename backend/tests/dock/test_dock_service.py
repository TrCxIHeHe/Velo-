import uuid
import pytest

from app.core.exceptions import DockNotFoundError
from app.dock.repository import DockRepository, VehicleRepository
from app.dock.schemas import DockCreate, DockUpdate
from app.dock.service import DockService


@pytest.mark.asyncio
async def test_create_dock_creates_slots(db_session):
    svc = DockService(DockRepository(db_session), VehicleRepository(db_session))
    dock = await svc.create_dock(DockCreate(
        name="Test Dock", location_lat=12.9, location_lng=77.6, total_slots=5
    ))
    assert dock.total_slots == 5
    assert dock.available_slots == 5


@pytest.mark.asyncio
async def test_get_dock_not_found(db_session):
    svc = DockService(DockRepository(db_session), VehicleRepository(db_session))
    with pytest.raises(DockNotFoundError):
        await svc.get_dock(uuid.uuid4())


@pytest.mark.asyncio
async def test_list_docks_returns_active(db_session):
    svc = DockService(DockRepository(db_session), VehicleRepository(db_session))
    await svc.create_dock(DockCreate(name="Active Dock", location_lat=12.9, location_lng=77.5, total_slots=3))
    docks = await svc.list_docks(active_only=True)
    assert len(docks) >= 1


@pytest.mark.asyncio
async def test_update_dock(db_session):
    svc = DockService(DockRepository(db_session), VehicleRepository(db_session))
    dock = await svc.create_dock(DockCreate(name="Old Name", location_lat=0.0, location_lng=0.0, total_slots=2))
    updated = await svc.update_dock(dock.id, DockUpdate(name="New Name"))
    assert updated.name == "New Name"
