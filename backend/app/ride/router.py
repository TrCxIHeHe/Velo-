from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.repository import AuditLogRepository
from app.auth.dependencies import CurrentUser
from app.core.exceptions import AppException
from app.core.redis import get_redis_client
from app.core.response import error_response, success_response
from app.database import get_db
from app.dock.repository import DockRepository
from app.ride.event_repository import RideEventRepository
from app.ride.repository import RideRepository, VehicleRepository
from app.ride.service import RideService
from app.ride.token_codec import RideTokenCodec

router = APIRouter(prefix="/ride", tags=["ride"])


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


@router.post("/request", status_code=201)
async def request_ride(current_user: CurrentUser, service: RideService = Depends(get_ride_service)):
    try:
        ride = await service.request_ride(current_user.id)
        return success_response(ride, status_code=201)
    except AppException as e:
        return error_response(e.code, e.message, e.http_status)


@router.get("/{ride_id}")
async def get_ride(
    ride_id: UUID, current_user: CurrentUser, service: RideService = Depends(get_ride_service)
):
    try:
        ride = await service.get_ride(ride_id, current_user.id)
        return success_response(ride)
    except AppException as e:
        return error_response(e.code, e.message, e.http_status)


@router.get("/status/{ride_id}")
async def get_ride_status(
    ride_id: UUID, current_user: CurrentUser, service: RideService = Depends(get_ride_service)
):
    try:
        status = await service.get_status(ride_id, current_user.id)
        return success_response(status)
    except AppException as e:
        return error_response(e.code, e.message, e.http_status)


# ── Ride Token — additive under /ride, not in the frozen endpoint list ────────

@router.post("/token", status_code=201)
async def issue_ride_token(
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_db),
    service: RideService = Depends(get_ride_service),
):
    try:
        token = await service.issue_ride_token(current_user.id)
        await AuditLogRepository(session).log(
            actor_id=current_user.id,
            action="RIDE_TOKEN_ISSUED",
            entity_type="ride",
            entity_id=str(current_user.id),
        )
        return success_response(token, status_code=201)
    except AppException as e:
        return error_response(e.code, e.message, e.http_status)
