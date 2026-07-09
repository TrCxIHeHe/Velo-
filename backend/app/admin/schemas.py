from decimal import Decimal

from pydantic import BaseModel


class FleetStatsResponse(BaseModel):
    """Snapshot of physical fleet state — how many docks/slots exist and
    how full they currently are. Powers the admin dashboard's map/overview
    page.
    """
    total_docks: int
    total_slots: int
    occupied_slots: int
    available_slots: int
    utilization_pct: float


class RevenueStatsResponse(BaseModel):
    """Wallet-derived revenue figures. Note this counts DEBIT transactions
    (money the platform actually collected for rides), not wallet top-ups
    (CREDIT) — a user topping up their wallet is not revenue until they
    spend it.
    """
    total_recharged: Decimal
    total_spent: Decimal
    total_refunded: Decimal
    net_platform_balance_held: Decimal  # money sitting in user wallets, a liability not revenue


class UserStatsResponse(BaseModel):
    total_wallets: int


class DashboardSummaryResponse(BaseModel):
    """Single call for the admin dashboard's landing page — avoids the
    frontend having to fire three separate requests on first paint.
    """
    fleet: FleetStatsResponse
    revenue: RevenueStatsResponse
    users: UserStatsResponse
