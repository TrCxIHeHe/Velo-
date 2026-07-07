from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.repository import AdminRepository
from app.admin.service import AdminService
from app.database import get_db
from app.dependencies import require_admin
from app.exceptions import AppException
from app.response import error_response, success_response

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],  # every route below needs X-Debug-Role: ADMIN
)


def get_admin_service(session: AsyncSession = Depends(get_db)) -> AdminService:
    return AdminService(AdminRepository(session))


@router.get("/dashboard")
async def get_dashboard(service: AdminService = Depends(get_admin_service)):
    try:
        summary = await service.get_dashboard_summary()
        return success_response(summary)
    except AppException as e:
        return error_response(e.code, e.message, e.http_status)


@router.get("/fleet")
async def get_fleet(service: AdminService = Depends(get_admin_service)):
    try:
        stats = await service.get_fleet_stats()
        return success_response(stats)
    except AppException as e:
        return error_response(e.code, e.message, e.http_status)


@router.get("/revenue")
async def get_revenue(service: AdminService = Depends(get_admin_service)):
    try:
        stats = await service.get_revenue_stats()
        return success_response(stats)
    except AppException as e:
        return error_response(e.code, e.message, e.http_status)


@router.get("/users")
async def get_users(service: AdminService = Depends(get_admin_service)):
    try:
        stats = await service.get_user_stats()
        return success_response(stats)
    except AppException as e:
        return error_response(e.code, e.message, e.http_status)
