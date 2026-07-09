from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user_id
from app.core.redis import get_redis_client
from app.dock.repository import DockRepository
from app.dock.schemas import AssignVehicleRequest, CreateDockRequest
from app.dock.service import DockService
from app.core.exceptions import AppException
from app.core.response import error_response, success_response
from app.ride.event_repository import RideEventRepository
from app.ride.repository import RideRepository, VehicleRepository
from app.ride.schemas import UnlockRequest, ValidateTokenRequest
from app.ride.service import RideService
from app.ride.token_codec import RideTokenCodec

router = APIRouter(prefix="/docks", tags=["dock"])


def get_dock_service(session: AsyncSession = Depends(get_db)) -> DockService:
    return DockService(DockRepository(session))


def get_ride_service(
    session: AsyncSession = Depends(get_db), redis=Depends(get_redis_client)
) -> RideService:
    return RideService(
        RideRepository(session),
        VehicleRepository(session),
        DockRepository(session),
        RideEventRepository(session),
        RideTokenCodec(redis),
    )


@router.get("")
async def list_docks(limit: int = 50, offset: int = 0, service: DockService = Depends(get_dock_service)):
    try:
        docks = await service.list_docks(limit, offset)
        return success_response(docks)
    except AppException as e:
        return error_response(e.code, e.message, e.http_status)


@router.get("/{dock_id}")
async def get_dock(dock_id: UUID, service: DockService = Depends(get_dock_service)):
    try:
        dock = await service.get_dock(dock_id)
        return success_response(dock)
    except AppException as e:
        return error_response(e.code, e.message, e.http_status)


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


# ── QR Validation + Ride Token Consumption (Track A) ──────────────────────────

@router.post("/{dock_id}/validate")
async def validate_ride_token(
    dock_id: UUID, body: ValidateTokenRequest, service: RideService = Depends(get_ride_service)
):
    """No auth dependency — the dock scanner isn't a logged-in user.
    Identity comes from inside the ride token's `sub` claim."""
    try:
        result = await service.validate_token(dock_id, body.ride_token)
        return success_response(result)
    except AppException as e:
        return error_response(e.code, e.message, e.http_status)


# ── Unlock Authorization (Track A) ────────────────────────────────────────────

@router.post("/{dock_id}/unlock")
async def authorize_unlock(
    dock_id: UUID, body: UnlockRequest, service: RideService = Depends(get_ride_service)
):
    """Backend authorization decision only — no ESP32/MQTT call (out of
    scope). Dock firmware will act on this once hardware integration lands."""
    try:
        result = await service.authorize_unlock(dock_id, body.ride_id)
        return success_response(result)
    except AppException as e:
        return error_response(e.code, e.message, e.http_status)
