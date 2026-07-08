from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.redis import get_redis_client
from app.core.response import error_response, success_response
from app.database import get_db
from app.dock.repository import DockRepository
from app.ride.event_repository import RideEventRepository
from app.ride.repository import RideRepository, VehicleRepository
from app.ride.schemas import UnlockRequest, ValidateTokenRequest
from app.ride.service import RideService
from app.ride.token_codec import RideTokenCodec

router = APIRouter(prefix="/docks", tags=["dock"])


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


# ── QR Validation + Ride Token Consumption ────────────────────────────────────

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


# ── Unlock Authorization ──────────────────────────────────────────────────────

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
