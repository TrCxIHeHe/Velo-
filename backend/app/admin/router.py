import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.repository import (
    AdminAuditRepository,
    AdminRepository,
    AdminRideRepository,
    AdminUserRepository,
)
from app.admin.schemas import SetUserActiveRequest, SetUserRoleRequest
from app.admin.service import AdminService
from app.audit.repository import AuditLogRepository
from app.auth.dependencies import CurrentUser, require_role
from app.core.exceptions import AppException
from app.core.response import error_response, success_response
from app.database import get_db

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_role("ADMIN"))])


def get_admin_service(session: Annotated[AsyncSession, Depends(get_db)]) -> AdminService:
    return AdminService(
        AdminRepository(session),
        AdminUserRepository(session),
        AdminAuditRepository(session),
        AdminRideRepository(session),
        AuditLogRepository(session),
    )


AdminServiceDep = Annotated[AdminService, Depends(get_admin_service)]


# ── Dashboard / fleet / revenue stats ───────────────────────────────────────────
# Namespaced under /stats to avoid colliding with GET /users below (user list).

@router.get("/stats/dashboard")
async def get_dashboard(service: AdminServiceDep):
    try:
        summary = await service.get_dashboard_summary()
        return success_response(summary.model_dump())
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)


@router.get("/stats/fleet")
async def get_fleet(service: AdminServiceDep):
    try:
        stats = await service.get_fleet_stats()
        return success_response(stats.model_dump())
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)


@router.get("/stats/revenue")
async def get_revenue(service: AdminServiceDep):
    try:
        stats = await service.get_revenue_stats()
        return success_response(stats.model_dump())
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)


@router.get("/stats/users")
async def get_user_stats(service: AdminServiceDep):
    try:
        stats = await service.get_user_stats()
        return success_response(stats.model_dump())
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)


# ── User management ──────────────────────────────────────────────────────────────

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
async def set_user_role(
    user_id: uuid.UUID, body: SetUserRoleRequest, admin_user: CurrentUser, service: AdminServiceDep
):
    try:
        user = await service.set_role(user_id, body.role, actor_id=admin_user.id)
        return success_response(user.model_dump())
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)


@router.patch("/users/{user_id}/active")
async def set_user_active(
    user_id: uuid.UUID, body: SetUserActiveRequest, admin_user: CurrentUser, service: AdminServiceDep
):
    try:
        user = await service.set_active(user_id, body.is_active, actor_id=admin_user.id)
        return success_response(user.model_dump())
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)


# ── Audit logs ────────────────────────────────────────────────────────────────────

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


# ── Ride management ────────────────────────────────────────────────────────────────

@router.get("/rides")
async def list_all_rides(
    service: AdminServiceDep,
    skip: int = 0,
    limit: int = 50,
    status: str | None = None,
):
    result = await service.list_all_rides(skip, limit, status)
    return success_response(result.model_dump())
