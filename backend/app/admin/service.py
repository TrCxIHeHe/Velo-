import uuid
from decimal import Decimal

from app.admin.repository import (
    AdminAuditRepository,
    AdminRepository,
    AdminRideRepository,
    AdminUserRepository,
)
from app.admin.schemas import (
    AuditLogListResponse,
    AuditLogResponse,
    DashboardSummaryResponse,
    FleetStatsResponse,
    RevenueStatsResponse,
    UserListResponse,
    UserStatsResponse,
)
from app.auth.schemas import UserResponse
from app.core.exceptions import UserNotFoundError
from app.ride.schemas import RideListResponse, RideResponse


class AdminService:
    def __init__(
        self,
        stats_repo: AdminRepository,
        user_repo: AdminUserRepository,
        audit_repo: AdminAuditRepository,
        ride_repo: AdminRideRepository,
    ) -> None:
        self.stats_repo = stats_repo
        self.user_repo = user_repo
        self.audit_repo = audit_repo
        self.ride_repo = ride_repo

    # ── Dashboard / fleet / revenue stats ───────────────────────────────────────

    async def get_fleet_stats(self) -> FleetStatsResponse:
        total_docks = await self.stats_repo.dock_repo.count_docks()
        total_slots = await self.stats_repo.dock_repo.count_all_slots()
        occupied = await self.stats_repo.dock_repo.count_occupied_slots()
        available = total_slots - occupied
        utilization = round((occupied / total_slots) * 100, 2) if total_slots else 0.0
        return FleetStatsResponse(
            total_docks=total_docks,
            total_slots=total_slots,
            occupied_slots=occupied,
            available_slots=available,
            utilization_pct=utilization,
        )

    async def get_revenue_stats(self) -> RevenueStatsResponse:
        total_recharged = await self.stats_repo.wallet_repo.sum_by_source("TOPUP")
        total_spent = await self.stats_repo.wallet_repo.sum_by_source("RIDE_FARE")
        total_refunded = await self.stats_repo.wallet_repo.sum_by_source("REFUND")
        # Money still sitting in every wallet combined — a liability on the
        # platform's books, not revenue. Kept here because it's the one
        # figure finance/admins ask for immediately after "how much did we
        # make" and it's already derivable from the same three sums.
        net_held: Decimal = total_recharged + total_refunded - total_spent
        return RevenueStatsResponse(
            total_recharged=total_recharged,
            total_spent=total_spent,
            total_refunded=total_refunded,
            net_platform_balance_held=net_held,
        )

    async def get_user_stats(self) -> UserStatsResponse:
        total_wallets = await self.stats_repo.wallet_repo.count_wallets()
        return UserStatsResponse(total_wallets=total_wallets)

    async def get_dashboard_summary(self) -> DashboardSummaryResponse:
        return DashboardSummaryResponse(
            fleet=await self.get_fleet_stats(),
            revenue=await self.get_revenue_stats(),
            users=await self.get_user_stats(),
        )

    # ── User management ──────────────────────────────────────────────────────────

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

    # ── Audit logs ───────────────────────────────────────────────────────────────

    async def list_audit_logs(
        self, skip: int, limit: int, user_id: uuid.UUID | None = None, action: str | None = None
    ) -> AuditLogListResponse:
        logs, total = await self.audit_repo.list_logs(skip, limit, user_id, action)
        return AuditLogListResponse(
            items=[AuditLogResponse.model_validate(log) for log in logs],
            total=total,
        )

    # ── Ride management ──────────────────────────────────────────────────────────

    async def list_all_rides(self, skip: int, limit: int, status: str | None = None) -> RideListResponse:
        rides, total = await self.ride_repo.list_all(skip, limit, status)
        return RideListResponse(
            items=[RideResponse.model_validate(r) for r in rides],
            total=total,
        )
