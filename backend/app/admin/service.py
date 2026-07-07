from decimal import Decimal

from app.admin.repository import AdminRepository
from app.admin.schemas import (
    DashboardSummaryResponse,
    FleetStatsResponse,
    RevenueStatsResponse,
    UserStatsResponse,
)


class AdminService:
    def __init__(self, repo: AdminRepository) -> None:
        self.repo = repo

    async def get_fleet_stats(self) -> FleetStatsResponse:
        total_docks = await self.repo.dock_repo.count_docks()
        total_slots = await self.repo.dock_repo.count_all_slots()
        occupied = await self.repo.dock_repo.count_occupied_slots()
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
        total_recharged = await self.repo.wallet_repo.sum_all("CREDIT")
        total_spent = await self.repo.wallet_repo.sum_all("DEBIT")
        total_refunded = await self.repo.wallet_repo.sum_all("REFUND")
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
        total_wallets = await self.repo.wallet_repo.count_wallets()
        return UserStatsResponse(total_wallets=total_wallets)

    async def get_dashboard_summary(self) -> DashboardSummaryResponse:
        return DashboardSummaryResponse(
            fleet=await self.get_fleet_stats(),
            revenue=await self.get_revenue_stats(),
            users=await self.get_user_stats(),
        )
