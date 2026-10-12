"""Admin CRUD for the fixed dock-pair tariff table (``/admin/dock-fares``)."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.repository import AuditLogRepository
from app.auth.dependencies import CurrentUser, require_role
from app.core.exceptions import AppException
from app.core.response import error_response, success_response
from app.database import get_db
from app.dock.repository import DockRepository
from app.pricing.repository import DockPairFareRepository
from app.pricing.schemas import DockPairFareCreate, DockPairFareUpdate
from app.pricing.service import PricingService

router = APIRouter(
    prefix="/admin/dock-fares", tags=["admin-pricing"], dependencies=[Depends(require_role("ADMIN"))]
)


def get_pricing_service(session: Annotated[AsyncSession, Depends(get_db)]) -> PricingService:
    return PricingService(
        DockPairFareRepository(session), DockRepository(session), AuditLogRepository(session)
    )


PricingServiceDep = Annotated[PricingService, Depends(get_pricing_service)]


@router.post("")
async def create_fare(body: DockPairFareCreate, admin: CurrentUser, service: PricingServiceDep):
    try:
        fare = await service.create_fare(body, admin.id)
        return success_response(fare.model_dump(mode="json"), status_code=201)
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)


@router.get("")
async def list_fares(
    service: PricingServiceDep,
    origin_dock_id: uuid.UUID | None = None,
    destination_dock_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    skip: int = 0,
    limit: int = 100,
):
    fares = await service.list_fares(
        origin=origin_dock_id, destination=destination_dock_id, is_active=is_active,
        skip=skip, limit=min(limit, 500),
    )
    return success_response([f.model_dump(mode="json") for f in fares])


@router.get("/{fare_id}")
async def get_fare(fare_id: uuid.UUID, service: PricingServiceDep):
    try:
        return success_response((await service.get_fare(fare_id)).model_dump(mode="json"))
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)


@router.patch("/{fare_id}")
async def update_fare(
    fare_id: uuid.UUID, body: DockPairFareUpdate, admin: CurrentUser, service: PricingServiceDep
):
    try:
        fare = await service.update_fare(fare_id, body, admin.id)
        return success_response(fare.model_dump(mode="json"))
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)
