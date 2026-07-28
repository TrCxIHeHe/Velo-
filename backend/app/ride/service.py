"""
Ride lifecycle:
  1. User requests ride token for a dock   → PENDING ride created, JWT ride token issued
  2. Hardware at dock verifies ride token  → ACTIVE ride, vehicle assigned, slot freed
  3. User docks at end dock               → COMPLETED, fare calculated & charged, new slot occupied

Fare: 2 INR/minute, minimum 5 INR.
"""
import uuid
from datetime import datetime, timedelta, timezone
from math import ceil

from jose import JWTError, jwt

from app.audit.repository import AuditLogRepository
from app.config import settings
from app.core.exceptions import (
    DockMismatchError, DockNotFoundError, InsufficientBalanceError,
    RideAlreadyActiveError, RideInvalidStateError, RideNotFoundError,
    RideForbiddenError, RideTokenExpiredError, RideTokenInvalidError,
    RideTokenReusedError, VehicleUnavailableError,
)
from app.dock.repository import DockRepository, VehicleRepository
from app.notifications.service import NotificationService
from app.ride.repository import RideRepository
from app.ride.schemas import RideListResponse, RideResponse, RideTokenResponse
from app.wallet.service import WalletService

FARE_PER_MINUTE = 2.0
MINIMUM_FARE = 5.0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _aware_utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _calculate_fare(duration_seconds: int) -> float:
    minutes = ceil(duration_seconds / 60)
    fare = max(minutes * FARE_PER_MINUTE, MINIMUM_FARE)
    return round(fare, 2)


class RideService:
    def __init__(
        self,
        ride_repo: RideRepository,
        dock_repo: DockRepository,
        vehicle_repo: VehicleRepository,
        wallet_service: WalletService,
        audit_repo: AuditLogRepository,
        notification_service: NotificationService | None = None,
        redis_client=None,
    ) -> None:
        self.ride_repo = ride_repo
        self.dock_repo = dock_repo
        self.vehicle_repo = vehicle_repo
        self.wallet_service = wallet_service
        self.audit_repo = audit_repo
        self.notification_service = notification_service
        self.redis = redis_client

    async def _notify(self, user_id: uuid.UUID, type_: str, title: str, body: str) -> None:
        if self.notification_service is not None:
            await self.notification_service.notify(user_id, type_, title, body)

    async def request_ride_token(self, user_id: uuid.UUID, dock_id: uuid.UUID) -> RideTokenResponse:
        # Check no active ride
        existing = await self.ride_repo.find_active_for_user(user_id)
        if existing:
            raise RideAlreadyActiveError()

        # Dock must exist and be active
        dock = await self.dock_repo.find_by_id(dock_id)
        if not dock or not dock.is_active:
            raise DockNotFoundError()

        # Check vehicle availability
        vehicle = await self.vehicle_repo.find_available_in_dock(dock_id)
        if not vehicle:
            raise VehicleUnavailableError()

        # Check wallet has minimum balance
        has_balance = await self.wallet_service.check_sufficient_for_ride(user_id)
        if not has_balance:
            raise InsufficientBalanceError()

        # Issue short-lived JWT ride token
        jti = str(uuid.uuid4())
        now = _aware_utcnow()
        payload = {
            "sub": str(user_id),
            "dock_id": str(dock_id),
            "type": "ride",
            "jti": jti,
            "iat": now,
            "exp": now + timedelta(seconds=settings.RIDE_TOKEN_TTL_SECONDS),
        }
        ride_token = jwt.encode(payload, settings.RIDE_TOKEN_SECRET, algorithm=settings.RIDE_TOKEN_ALGORITHM)

        # Create PENDING ride
        ride = await self.ride_repo.create(user_id, dock_id, jti)
        await self.audit_repo.log(user_id, "RIDE_TOKEN_ISSUED", "ride", str(ride.id))

        return RideTokenResponse(
            ride_token=ride_token,
            ride_id=ride.id,
            expires_in_seconds=settings.RIDE_TOKEN_TTL_SECONDS,
        )

    async def confirm_ride(self, ride_token: str, dock_id: uuid.UUID) -> RideResponse:
        """Called by dock hardware after QR scan."""
        try:
            payload = jwt.decode(
                ride_token,
                settings.RIDE_TOKEN_SECRET,
                algorithms=[settings.RIDE_TOKEN_ALGORITHM],
            )
            if payload.get("type") != "ride":
                raise RideTokenInvalidError()
        except JWTError as exc:
            if "expired" in str(exc).lower():
                raise RideTokenExpiredError()
            raise RideTokenInvalidError() from exc

        # Validate dock matches token
        if str(dock_id) != payload.get("dock_id"):
            raise DockMismatchError()

        jti = payload["jti"]

        # Atomic one-time-use lock: SETNX is the correct fix for QR replay
        # (a plain read-then-write status check has a TOCTOU race — two
        # concurrent confirm calls with the same token could both pass the
        # status check before either commits its update). This must be
        # checked before the DB status check, not instead of it: Redis is
        # the primary defense, the DB status check below is a second
        # independent layer in case redis_client wasn't wired in.
        if self.redis is not None:
            lock_key = f"ride_token_used:{jti}"
            acquired = await self.redis.set(
                lock_key, "1", nx=True, ex=settings.RIDE_TOKEN_TTL_SECONDS + 5
            )
            if not acquired:
                raise RideTokenReusedError()

        ride = await self.ride_repo.find_by_jti(jti)
        if not ride:
            raise RideTokenInvalidError()
        if ride.status != "PENDING":
            raise RideTokenReusedError()

        # Assign vehicle
        vehicle = await self.vehicle_repo.find_available_in_dock(dock_id)
        if not vehicle:
            # Cancel the pending ride
            await self.ride_repo.update(ride.id, status="CANCELLED")
            raise VehicleUnavailableError()

        # Free vehicle's slot, mark vehicle as IN_RIDE
        if vehicle.slot_id:
            await self.dock_repo.free_slot(vehicle.slot_id)
        await self.vehicle_repo.set_status(vehicle.id, "IN_RIDE")
        await self.vehicle_repo.update_slot(vehicle.id, None)

        # Activate ride
        ride = await self.ride_repo.update(
            ride.id,
            status="ACTIVE",
            vehicle_id=vehicle.id,
            started_at=_utcnow(),
        )
        await self.audit_repo.log(ride.user_id, "RIDE_STARTED", "ride", str(ride.id))
        await self._notify(
            ride.user_id, "RIDE_START", "Ride started",
            "Your ride has started. Have a safe trip!",
        )
        return RideResponse.model_validate(ride)

    async def end_ride(self, user_id: uuid.UUID, ride_id: uuid.UUID, end_dock_id: uuid.UUID) -> RideResponse:
        ride = await self.ride_repo.find_by_id(ride_id)
        if not ride:
            raise RideNotFoundError()
        if ride.user_id != user_id:
            raise RideForbiddenError()
        if ride.status != "ACTIVE":
            raise RideInvalidStateError()

        end_dock = await self.dock_repo.find_by_id(end_dock_id)
        if not end_dock or not end_dock.is_active:
            raise DockNotFoundError()

        # Find a free slot at the end dock
        slot = await self.dock_repo.find_free_slot(end_dock_id)
        if not slot:
            from app.core.exceptions import DockFullError
            raise DockFullError()

        now = _utcnow()
        started_at = ride.started_at
        if started_at is None:
            started_at = now
        duration_seconds = max(int((now - started_at).total_seconds()), 0)
        fare = _calculate_fare(duration_seconds)

        # Park vehicle in slot
        await self.dock_repo.occupy_slot(slot.id)
        if ride.vehicle_id:
            await self.vehicle_repo.set_status(ride.vehicle_id, "AVAILABLE")
            await self.vehicle_repo.update_slot(ride.vehicle_id, slot.id)

        # Settle fare
        await self.wallet_service.debit_for_ride(user_id, fare, ride.id)

        ride = await self.ride_repo.update(
            ride.id,
            status="COMPLETED",
            end_dock_id=end_dock_id,
            ended_at=now,
            duration_seconds=duration_seconds,
            fare_amount=fare,
        )
        await self.audit_repo.log(user_id, "RIDE_ENDED", "ride", str(ride.id), meta=f"fare={fare}")
        await self._notify(
            user_id, "RIDE_END", "Ride completed",
            f"Your ride has ended. Fare charged: ₹{fare:.2f}.",
        )

        wallet = await self.wallet_service.get_balance(user_id)
        if wallet.balance < settings.WALLET_MIN_RIDE_BALANCE:
            await self._notify(
                user_id, "LOW_BALANCE", "Low wallet balance",
                f"Your wallet balance is ₹{wallet.balance:.2f}. Top up to keep riding.",
            )
        return RideResponse.model_validate(ride)

    async def get_ride(self, user_id: uuid.UUID, ride_id: uuid.UUID) -> RideResponse:
        ride = await self.ride_repo.find_by_id(ride_id)
        if not ride:
            raise RideNotFoundError()
        if ride.user_id != user_id:
            raise RideForbiddenError()
        return RideResponse.model_validate(ride)

    async def get_active_ride(self, user_id: uuid.UUID) -> RideResponse | None:
        ride = await self.ride_repo.find_active_for_user(user_id)
        if not ride:
            return None
        return RideResponse.model_validate(ride)

    async def list_rides(self, user_id: uuid.UUID, skip: int = 0, limit: int = 20) -> RideListResponse:
        rides, total = await self.ride_repo.list_for_user(user_id, skip, limit)
        return RideListResponse(
            items=[RideResponse.model_validate(r) for r in rides],
            total=total,
        )
