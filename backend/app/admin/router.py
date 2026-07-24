import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.repository import AdminAuditRepository, AdminRideRepository, AdminUserRepository
from app.admin.schemas import SetUserActiveRequest, SetUserRoleRequest
from app.admin.service import AdminService
from app.auth.dependencies import require_role
from app.core.exceptions import AppException
from app.core.response import error_response, success_response
from app.database import get_db

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_role("ADMIN"))])


def get_admin_service(session: Annotated[AsyncSession, Depends(get_db)]) -> AdminService:
    return AdminService(
        AdminUserRepository(session),
        AdminAuditRepository(session),
        AdminRideRepository(session),
    )


AdminServiceDep = Annotated[AdminService, Depends(get_admin_service)]


@router.get("/users")
async def list_users(service: AdminServiceDep, skip: int = 0, limit: int = 50):
    result = await service.list_users(skip, limit)
    return success_response(result.model_dump())


@router.get("/users/{user_id}")
async def get_user(user_id: uuid.UUID, service: AdminServiceDep):
    try:
        user = await service.get_user(user_id)
        return success_response(user.model_dump())
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)


@router.patch("/users/{user_id}/role")
async def set_user_role(user_id: uuid.UUID, body: SetUserRoleRequest, service: AdminServiceDep):
    try:
        user = await service.set_role(user_id, body.role)
        return success_response(user.model_dump())
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)


@router.patch("/users/{user_id}/active")
async def set_user_active(user_id: uuid.UUID, body: SetUserActiveRequest, service: AdminServiceDep):
    try:
        user = await service.set_active(user_id, body.is_active)
        return success_response(user.model_dump())
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)


@router.get("/audit-logs")
async def list_audit_logs(
    service: AdminServiceDep,
    skip: int = 0,
    limit: int = 50,
    user_id: uuid.UUID | None = None,
    action: str | None = None,
):
    result = await service.list_audit_logs(skip, limit, user_id, action)
    return success_response(result.model_dump())


@router.get("/rides")
async def list_all_rides(
    service: AdminServiceDep,
    skip: int = 0,
    limit: int = 50,
    status: str | None = None,
):
    result = await service.list_all_rides(skip, limit, status)
    return success_response(result.model_dump())
