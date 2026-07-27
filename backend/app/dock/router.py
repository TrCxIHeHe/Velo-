import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.core.exceptions import AppException
from app.core.response import error_response, success_response
from app.database import get_db
from app.dock.repository import DockRepository, VehicleRepository
from app.dock.schemas import DockCreate, DockUpdate, VehicleCreate, VehicleStatusUpdate
from app.dock.service import DockService

router = APIRouter(prefix="/docks", tags=["docks"])


def get_dock_service(session: Annotated[AsyncSession, Depends(get_db)]) -> DockService:
    return DockService(DockRepository(session), VehicleRepository(session))


DockServiceDep = Annotated[DockService, Depends(get_dock_service)]


# ── Public endpoints (no auth) ────────────────────────────────────────────────

@router.get("")
async def list_docks(service: DockServiceDep, active_only: bool = True):
    """List active docks. Public — needed by the Flutter map before login."""
    docks = await service.list_docks(active_only)
    return success_response([d.model_dump() for d in docks])


@router.get("/{dock_id}")
async def get_dock(dock_id: uuid.UUID, service: DockServiceDep):
    """Dock detail with slot availability. Public."""
    try:
        dock = await service.get_dock(dock_id)
        return success_response(dock.model_dump())
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)


# ── Admin-only endpoints ──────────────────────────────────────────────────────

@router.post("", dependencies=[Depends(require_role("ADMIN"))])
async def create_dock(body: DockCreate, service: DockServiceDep):
    dock = await service.create_dock(body)
    return success_response(dock.model_dump(), status_code=201)


@router.patch("/{dock_id}", dependencies=[Depends(require_role("ADMIN"))])
async def update_dock(dock_id: uuid.UUID, body: DockUpdate, service: DockServiceDep):
    try:
        dock = await service.update_dock(dock_id, body)
        return success_response(dock.model_dump())
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)


@router.get("/vehicles/all", dependencies=[Depends(require_role("ADMIN"))])
async def list_vehicles(service: DockServiceDep, skip: int = 0, limit: int = 100):
    vehicles = await service.list_vehicles(skip, limit)
    return success_response([v.model_dump() for v in vehicles])


@router.post("/vehicles", dependencies=[Depends(require_role("ADMIN"))])
async def add_vehicle(body: VehicleCreate, service: DockServiceDep):
    try:
        vehicle = await service.add_vehicle(body)
        return success_response(vehicle.model_dump(), status_code=201)
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)


@router.patch("/vehicles/{vehicle_id}", dependencies=[Depends(require_role("ADMIN"))])
async def update_vehicle(vehicle_id: uuid.UUID, body: VehicleStatusUpdate, service: DockServiceDep):
    try:
        vehicle = await service.update_vehicle(vehicle_id, body)
        return success_response(vehicle.model_dump())
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)
