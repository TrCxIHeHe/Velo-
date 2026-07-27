import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.repository import AuditLogRepository
from app.auth.dependencies import CurrentUser
from app.core.exceptions import AppException
from app.core.firebase import FirebaseService, get_firebase_service
from app.core.rate_limit import limiter
from app.core.response import error_response, success_response
from app.database import get_db
from app.dock.repository import DockRepository, VehicleRepository
from app.notifications.repository import NotificationRepository, UserDeviceRepository
from app.notifications.service import NotificationService
from app.ride.repository import RideRepository
from app.ride.schemas import ConfirmRideRequest, EndRideRequest, RequestRideTokenRequest
from app.ride.service import RideService
from app.wallet.repository import WalletRepository
from app.wallet.service import WalletService

router = APIRouter(prefix="/rides", tags=["rides"])


def get_ride_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    firebase: Annotated[FirebaseService, Depends(get_firebase_service)],
) -> RideService:
    return RideService(
        RideRepository(session),
        DockRepository(session),
        VehicleRepository(session),
        WalletService(WalletRepository(session), AuditLogRepository(session)),
        AuditLogRepository(session),
        NotificationService(NotificationRepository(session), UserDeviceRepository(session), firebase),
    )


RideServiceDep = Annotated[RideService, Depends(get_ride_service)]


@router.post("/token")
@limiter.limit("3/minute")
async def request_ride_token(
    request: Request, body: RequestRideTokenRequest, current_user: CurrentUser, service: RideServiceDep
):
    try:
        result = await service.request_ride_token(current_user.id, body.dock_id)
        return success_response(result.model_dump(), status_code=201)
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)


@router.post("/confirm")
async def confirm_ride(body: ConfirmRideRequest, service: RideServiceDep):
    """Called by dock hardware. No user auth required — the ride token IS the auth."""
    try:
        ride = await service.confirm_ride(body.ride_token, body.dock_id)
        return success_response(ride.model_dump())
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)


@router.post("/{ride_id}/end")
async def end_ride(ride_id: uuid.UUID, body: EndRideRequest, current_user: CurrentUser, service: RideServiceDep):
    try:
        ride = await service.end_ride(current_user.id, ride_id, body.dock_id)
        return success_response(ride.model_dump())
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)


@router.get("/active")
async def get_active_ride(current_user: CurrentUser, service: RideServiceDep):
    ride = await service.get_active_ride(current_user.id)
    if ride is None:
        return success_response(None)
    return success_response(ride.model_dump())


@router.get("")
async def list_rides(
    current_user: CurrentUser, service: RideServiceDep, skip: int = 0, limit: int = 20
):
    result = await service.list_rides(current_user.id, skip, limit)
    return success_response(result.model_dump())


@router.get("/{ride_id}")
async def get_ride(ride_id: uuid.UUID, current_user: CurrentUser, service: RideServiceDep):
    try:
        ride = await service.get_ride(current_user.id, ride_id)
        return success_response(ride.model_dump())
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)
