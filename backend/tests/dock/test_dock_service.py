"""Unit tests for DockService — dock/slot CRUD, availability counting,
and the assign/release primitives that a future ride-unlock flow will
call into (see setup.md section 8, item 2)."""
import uuid

import pytest

from app.dock.repository import DockRepository
from app.dock.service import DockService
from app.exceptions import DockFullError, DockNotFoundError, SlotNotFoundError, SlotOccupiedError


@pytest.fixture
def dock_service(db_session):
    return DockService(DockRepository(db_session))


async def test_create_dock_creates_matching_number_of_slots(dock_service):
    dock = await dock_service.create_dock("MG Road Dock", 12.9716, 77.5946, total_slots=4)
    detail = await dock_service.get_dock(dock.id)
    assert len(detail.slots) == 4
    assert detail.available_slots == 4
    assert all(not s.is_occupied for s in detail.slots)


async def test_get_dock_not_found_raises(dock_service):
    with pytest.raises(DockNotFoundError):
        await dock_service.get_dock(uuid.uuid4())


async def test_list_docks_only_returns_active(dock_service):
    await dock_service.create_dock("Dock A", 1.0, 1.0, total_slots=2)
    docks = await dock_service.list_docks()
    assert len(docks) == 1
    assert all(d.status == "ACTIVE" for d in docks)


async def test_assign_vehicle_occupies_a_slot(dock_service):
    dock = await dock_service.create_dock("Dock A", 1.0, 1.0, total_slots=2)
    vehicle_id = uuid.uuid4()
    slot = await dock_service.assign_vehicle(dock.id, vehicle_id)
    assert slot.is_occupied is True
    assert slot.vehicle_id == vehicle_id

    detail = await dock_service.get_dock(dock.id)
    assert detail.available_slots == 1


async def test_assign_vehicle_to_full_dock_raises(dock_service):
    dock = await dock_service.create_dock("Tiny Dock", 1.0, 1.0, total_slots=1)
    await dock_service.assign_vehicle(dock.id, uuid.uuid4())
    with pytest.raises(DockFullError):
        await dock_service.assign_vehicle(dock.id, uuid.uuid4())


async def test_assign_vehicle_to_nonexistent_dock_raises(dock_service):
    with pytest.raises(DockNotFoundError):
        await dock_service.assign_vehicle(uuid.uuid4(), uuid.uuid4())


async def test_release_vehicle_frees_the_slot(dock_service):
    dock = await dock_service.create_dock("Dock A", 1.0, 1.0, total_slots=1)
    vehicle_id = uuid.uuid4()
    slot = await dock_service.assign_vehicle(dock.id, vehicle_id)

    released = await dock_service.release_vehicle(dock.id, slot.id)
    assert released.is_occupied is False
    assert released.vehicle_id is None

    # And the slot becomes assignable again.
    new_slot = await dock_service.assign_vehicle(dock.id, uuid.uuid4())
    assert new_slot.id == slot.id


async def test_release_already_empty_slot_raises(dock_service):
    dock = await dock_service.create_dock("Dock A", 1.0, 1.0, total_slots=1)
    slots = (await dock_service.get_dock(dock.id)).slots
    with pytest.raises(SlotOccupiedError):
        await dock_service.release_vehicle(dock.id, slots[0].id)


async def test_release_slot_belonging_to_different_dock_raises(dock_service):
    dock_a = await dock_service.create_dock("Dock A", 1.0, 1.0, total_slots=1)
    dock_b = await dock_service.create_dock("Dock B", 2.0, 2.0, total_slots=1)
    slot_a = (await dock_service.get_dock(dock_a.id)).slots[0]
    with pytest.raises(SlotNotFoundError):
        # Asking to release slot_a but scoping the call to dock_b — this
        # must fail closed, not silently release the wrong dock's slot.
        await dock_service.release_vehicle(dock_b.id, slot_a.id)
