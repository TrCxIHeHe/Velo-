from app.core.timeutil import UTCDateTime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ── Dashboard / fleet / revenue stats ───────────────────────────────────────────

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


# ── User / audit-log management ─────────────────────────────────────────────────

class UserListResponse(BaseModel):
    items: list[dict]
    total: int


class SetUserRoleRequest(BaseModel):
    role: str  # USER | ADMIN


class SetUserActiveRequest(BaseModel):
    is_active: bool


class AuditLogResponse(BaseModel):
    id: UUID
    user_id: UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    meta: str | None
    created_at: UTCDateTime
    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int


class RecoverRideRequest(BaseModel):
    """Admin recovery of a stuck ride (see RideService.recover_ride)."""

    action: Literal["complete", "cancel_pending"]
    # Required for an ACTIVE ride: the dock to park the scooter in. It goes
    # through exactly the same validation/pricing/settlement as a normal end.
    dock_id: UUID | None = None
    reason: str = Field(..., min_length=5, max_length=300)
