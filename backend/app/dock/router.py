from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.dock.repository import DockRepository
from app.dock.schemas import AssignVehicleRequest, CreateDockRequest
from app.dock.service import DockService
from app.exceptions import AppException
from app.response import error_response, success_response

router = APIRouter(prefix="/docks", tags=["dock"])


def get_dock_service(session: AsyncSession = Depends(get_db)) -> DockService:
    return DockService(DockRepository(session))


# Reading dock/slot availability is public (riders need it on the map before
# logging in to anything), so it does NOT require get_current_user_id.

@router.get("")
async def list_docks(
    limit: int = 50,
    offset: int = 0,
    service: DockService = Depends(get_dock_service),
):
    try:
        docks = await service.list_docks(limit, offset)
        return success_response(docks)
    except AppException as e:
        return error_response(e.code, e.message, e.http_status)


@router.get("/{dock_id}")
async def get_dock(
    dock_id: UUID,
    service: DockService = Depends(get_dock_service),
):
    try:
        dock = await service.get_dock(dock_id)
        return success_response(dock)
    except AppException as e:
        return error_response(e.code, e.message, e.http_status)


# Mutating endpoints — creating docks and assigning/releasing vehicles — DO
# require an authenticated caller (admin, in a real deployment). We reuse the
# same dev auth stub as wallet for now; tighten to an admin-only check once
# Track A's role-based auth exists.

@router.post("", status_code=201)
async def create_dock(
    body: CreateDockRequest,
    _user_id: UUID = Depends(get_current_user_id),
    service: DockService = Depends(get_dock_service),
):
    try:
        dock = await service.create_dock(body.name, body.latitude, body.longitude, body.total_slots)
        return success_response(dock, status_code=201)
    except AppException as e:
        return error_response(e.code, e.message, e.http_status)


@router.post("/{dock_id}/assign")
async def assign_vehicle(
    dock_id: UUID,
    body: AssignVehicleRequest,
    _user_id: UUID = Depends(get_current_user_id),
    service: DockService = Depends(get_dock_service),
):
    try:
        slot = await service.assign_vehicle(dock_id, body.vehicle_id)
        return success_response(slot, status_code=201)
    except AppException as e:
        return error_response(e.code, e.message, e.http_status)


@router.post("/{dock_id}/slots/{slot_id}/release")
async def release_vehicle(
    dock_id: UUID,
    slot_id: UUID,
    _user_id: UUID = Depends(get_current_user_id),
    service: DockService = Depends(get_dock_service),
):
    try:
        slot = await service.release_vehicle(dock_id, slot_id)
        return success_response(slot)
    except AppException as e:
        return error_response(e.code, e.message, e.http_status)
