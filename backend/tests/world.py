"""Shared builders for ride / pricing / recovery tests.

Setup data is COMMITTED: ``RideService.end_ride`` rolls the session back on any
failure, so only committed rows survive a failed end — exactly like production.
"""
import uuid
from decimal import Decimal

from sqlalchemy import select

from app.audit.repository import AuditLogRepository
from app.dock.repository import DockRepository, VehicleRepository
from app.dock.schemas import DockCreate, VehicleCreate
from app.dock.service import DockService
from app.models import DockSlot, Vehicle, Wallet, WalletTransaction
from app.pricing.repository import DockPairFareRepository
from app.ride.repository import RideRepository
from app.ride.service import RideService
from app.wallet.repository import WalletRepository
from app.wallet.service import WalletService


class World:
    def __init__(self, db, redis, user_id: uuid.UUID, headers: dict):
        self.db, self.redis, self.user_id, self.headers = db, redis, user_id, headers

    def service(self) -> RideService:
        return RideService(
            RideRepository(self.db), DockRepository(self.db), VehicleRepository(self.db),
            WalletService(WalletRepository(self.db), AuditLogRepository(self.db)),
            AuditLogRepository(self.db), redis_client=self.redis,
        )

    async def dock(self, name: str, slots: int = 2, vehicles: int = 0, active: bool = True) -> uuid.UUID:
        svc = DockService(DockRepository(self.db), VehicleRepository(self.db))
        dock = await svc.create_dock(
            DockCreate(name=name, location_lat=12.97, location_lng=77.59, total_slots=slots)
        )
        for _ in range(vehicles):
            slot = await DockRepository(self.db).find_free_slot(dock.id)
            await svc.add_vehicle(
                VehicleCreate(qr_code=f"qr-{uuid.uuid4()}", battery_level=100, slot_id=slot.id)
            )
        if not active:
            await DockRepository(self.db).update(dock.id, is_active=False)
        await self.db.commit()
        return dock.id

    async def fund(self, amount: float, currency: str | None = None) -> None:
        await WalletService(WalletRepository(self.db)).top_up(self.user_id, amount)
        if currency:
            wallet = await WalletRepository(self.db).find_by_user_id(self.user_id)
            wallet.currency = currency
        await self.db.commit()

    async def fare(self, origin, destination, amount: str, *, active=True, currency="INR"):
        row = await DockPairFareRepository(self.db).create(
            origin, destination, Decimal(amount), currency, active
        )
        await self.db.commit()
        return row

    async def start_ride(self, dock_id):
        """Real token -> confirm flow; returns the ACTIVE RideResponse."""
        svc = self.service()
        token = await svc.request_ride_token(self.user_id, dock_id)
        ride = await svc.confirm_ride(token.ride_token, dock_id)
        await self.db.commit()
        return ride

    # ── inspection helpers ───────────────────────────────────────────────
    async def slots(self, dock_id):
        rows = await self.db.execute(select(DockSlot).where(DockSlot.dock_id == dock_id))
        return list(rows.scalars())

    async def occupied(self, dock_id) -> int:
        return sum(1 for s in await self.slots(dock_id) if s.is_occupied)

    async def vehicle(self, vehicle_id) -> Vehicle:
        row = await self.db.execute(
            select(Vehicle).where(Vehicle.id == vehicle_id).execution_options(populate_existing=True)
        )
        return row.scalar_one()

    async def balance(self) -> float:
        row = await self.db.execute(
            select(Wallet).where(Wallet.user_id == self.user_id).execution_options(populate_existing=True)
        )
        return row.scalar_one().balance

    async def debits(self) -> list[WalletTransaction]:
        rows = await self.db.execute(
            select(WalletTransaction).where(WalletTransaction.source == "RIDE_FARE")
        )
        return list(rows.scalars())
