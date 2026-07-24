import uuid

from app.admin.repository import AdminAuditRepository, AdminRideRepository, AdminUserRepository
from app.admin.schemas import AuditLogListResponse, AuditLogResponse, UserListResponse
from app.auth.schemas import UserResponse
from app.core.exceptions import UserNotFoundError
from app.ride.schemas import RideListResponse, RideResponse


class AdminService:
    def __init__(
        self,
        user_repo: AdminUserRepository,
        audit_repo: AdminAuditRepository,
        ride_repo: AdminRideRepository,
    ) -> None:
        self.user_repo = user_repo
        self.audit_repo = audit_repo
        self.ride_repo = ride_repo

    async def list_users(self, skip: int = 0, limit: int = 50) -> UserListResponse:
        users, total = await self.user_repo.list_users(skip, limit)
        return UserListResponse(
            items=[UserResponse.model_validate(u).model_dump() for u in users],
            total=total,
        )

    async def get_user(self, user_id: uuid.UUID) -> UserResponse:
        user = await self.user_repo.find_by_id(user_id)
        if not user:
            raise UserNotFoundError()
        return UserResponse.model_validate(user)

    async def set_role(self, user_id: uuid.UUID, role: str) -> UserResponse:
        user = await self.user_repo.set_role(user_id, role)
        if not user:
            raise UserNotFoundError()
        return UserResponse.model_validate(user)

    async def set_active(self, user_id: uuid.UUID, is_active: bool) -> UserResponse:
        user = await self.user_repo.set_active(user_id, is_active)
        if not user:
            raise UserNotFoundError()
        return UserResponse.model_validate(user)

    async def list_audit_logs(
        self, skip: int, limit: int, user_id: uuid.UUID | None = None, action: str | None = None
    ) -> AuditLogListResponse:
        logs, total = await self.audit_repo.list_logs(skip, limit, user_id, action)
        return AuditLogListResponse(
            items=[AuditLogResponse.model_validate(log) for log in logs],
            total=total,
        )

    async def list_all_rides(self, skip: int, limit: int, status: str | None = None) -> RideListResponse:
        rides, total = await self.ride_repo.list_all(skip, limit, status)
        return RideListResponse(
            items=[RideResponse.model_validate(r) for r in rides],
            total=total,
        )
