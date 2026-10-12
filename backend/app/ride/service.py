"""
Ride lifecycle:
  1. User requests ride token for a dock   → PENDING ride created, ride token issued
  2. Hardware at dock verifies ride token  → ACTIVE ride, vehicle assigned, slot freed
  3. User docks at end dock               → COMPLETED, fare priced & charged, slot occupied

Pre-hardware (PENDING) terminal states:
  PENDING → ACTIVE     valid scan
  PENDING → CANCELLED  explicit cancel, or superseded by a newer token request
  PENDING → EXPIRED    ride token TTL elapsed without a valid scan

A PENDING ride whose token has expired can never be confirmed, so it is moved to
EXPIRED lazily — whenever the owner requests a new token, reads the ride, or
lists rides — instead of blocking the user.

CONCURRENCY
-----------
Every state change is a compare-and-set (``RideRepository.transition``): the
UPDATE only applies if the ride is still in the expected status, so confirm /
cancel / expire / end cannot overwrite each other. Ending a ride additionally
locks the ride row (``SELECT ... FOR UPDATE``) and is all-or-nothing: any
failure rolls the whole request back (see ``end_ride``).

PRICING
-------
Fares come exclusively from ``PricingService`` (configured strategy; today a
fixed fare per directed dock pair). There is no fallback formula.

TIMESTAMPS
----------
DB columns hold naive UTC (``naive_utcnow``); the API serialises them with an
explicit ``Z`` (``app.core.timeutil``).
"""
import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta

from jose import JWTError, jwt

from app.audit.repository import AuditLogRepository
from app.config import settings
from app.core.exceptions import (
    DockFullError, DockMismatchError, DockNotFoundError, InsufficientBalanceError,
    RideAlreadyActiveError, RideForbiddenError, RideInvalidStateError, RideNotFoundError,
    RideRecoveryError, RideTokenExpiredError, RideTokenInvalidError, RideTokenReusedError,
    SameDockReturnNotAllowedError, VehicleUnavailableError,
)
from app.core.money import quantize_money
from app.core.timeutil import naive_utcnow
from app.dock.repository import DockRepository, VehicleRepository
from app.notifications.service import NotificationService
from app.pricing.repository import DockPairFareRepository
from app.pricing.schemas import FareQuoteResponse
from app.pricing.service import PricingService
from app.pricing.strategy import FareResult, PricingContext
from app.ride.repository import RideRepository
from app.ride.schemas import RideListResponse, RideResponse, RideTokenResponse
from app.wallet.service import WalletService

logger = logging.getLogger(__name__)

OPAQUE_RIDE_TOKEN_PREFIX = "rt2_"
OPAQUE_RIDE_TOKEN_BYTES = 16  # 128 bits of cryptographically secure entropy -> 22 URL-safe chars

# Naive-UTC "now" — the representation stored in the DB columns.
_utcnow = naive_utcnow


def _token_deadline(ride) -> datetime:
    """Naive-UTC instant at which the ride's token is guaranteed to be expired.

    ``ride.created_at`` is written after the token is minted, so
    ``created_at + TTL >= expiry``. A ride is therefore never marked EXPIRED
    while its token is still valid.
    """
    return ride.created_at + timedelta(seconds=settings.RIDE_TOKEN_TTL_SECONDS)


def _is_stale_pending(ride, now: datetime) -> bool:
    return ride.status == "PENDING" and now >= _token_deadline(ride)


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
        pricing_service: PricingService | None = None,
    ) -> None:
        self.ride_repo = ride_repo
        self.dock_repo = dock_repo
        self.vehicle_repo = vehicle_repo
        self.wallet_service = wallet_service
        self.audit_repo = audit_repo
        self.notification_service = notification_service
        self.redis = redis_client
        # Defaults to the configured strategy over the same DB session.
        self.pricing = pricing_service or PricingService(
            DockPairFareRepository(ride_repo.session), dock_repo
        )

    async def _notify(self, user_id: uuid.UUID, type_: str, title: str, body: str) -> None:
        if self.notification_service is not None:
            await self.notification_service.notify(user_id, type_, title, body)

    async def _expire_ride(self, ride):
        # Compare-and-set: never overwrite a ride a concurrent scan just activated.
        expired = await self.ride_repo.transition(ride.id, "PENDING", status="EXPIRED")
        ride = await self.ride_repo.refresh(ride.id)
        if expired:
            await self.audit_repo.log(ride.user_id, "RIDE_TOKEN_EXPIRED", "ride", str(ride.id))
        return ride

    async def _expire_stale_pending(self, user_id: uuid.UUID) -> None:
        """Move every PENDING ride of this user whose token has expired to EXPIRED."""
        now = _utcnow()
        for ride in await self.ride_repo.list_open_for_user(user_id):
            if _is_stale_pending(ride, now):
                await self._expire_ride(ride)

    async def request_ride_token(self, user_id: uuid.UUID, dock_id: uuid.UUID) -> RideTokenResponse:
        # 1. Expired PENDING rides can never complete — retire them so they
        #    cannot block a new token.
        await self._expire_stale_pending(user_id)

        # 2. Only a genuinely ACTIVE ride blocks a new token.
        open_rides = await self.ride_repo.list_open_for_user(user_id)
        if any(r.status == "ACTIVE" for r in open_rides):
            raise RideAlreadyActiveError()
        still_pending = [r for r in open_rides if r.status == "PENDING"]

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

        # 3. The user explicitly asked for another QR while a previous one is
        #    still valid: supersede it so there is never more than one live
        #    PENDING ride.  Done only after all validations pass so a failed
        #    request does not destroy a working token.  The old JWT can no
        #    longer be confirmed: its ride is no longer PENDING.
        for old in still_pending:
            if await self.ride_repo.transition(old.id, "PENDING", status="CANCELLED"):
                await self.audit_repo.log(
                    user_id, "RIDE_TOKEN_SUPERSEDED", "ride", str(old.id)
                )

        # A compact opaque credential keeps the QR sparse enough for a small camera.
        # Store only its SHA-256 digest in the existing 64-character JTI column.
        ride_token = OPAQUE_RIDE_TOKEN_PREFIX + secrets.token_urlsafe(OPAQUE_RIDE_TOKEN_BYTES)
        jti = hashlib.sha256(ride_token.encode("utf-8")).hexdigest()

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
        if ride_token.startswith(OPAQUE_RIDE_TOKEN_PREFIX):
            # New token format: lookup uses a digest, never the bearer secret itself.
            jti = hashlib.sha256(ride_token.encode("utf-8")).hexdigest()
            preliminary_ride = await self.ride_repo.find_by_jti(jti)
            if not preliminary_ride:
                raise RideTokenInvalidError()
            # Reject wrong-dock attempts before acquiring the one-time-use lock.
            if str(dock_id) != str(preliminary_ride.start_dock_id):
                raise DockMismatchError()
            if preliminary_ride.status == "EXPIRED" or _is_stale_pending(preliminary_ride, _utcnow()):
                raise RideTokenExpiredError()
        else:
            # Backward compatibility: accept unexpired JWTs issued before this deployment.
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

            # Legacy JWT embeds the dock identifier; keep its original validation.
            if str(dock_id) != payload.get("dock_id"):
                raise DockMismatchError()
            jti = payload.get("jti")
            if not isinstance(jti, str) or not jti:
                raise RideTokenInvalidError()

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
        if ride.status == "EXPIRED":
            raise RideTokenExpiredError()
        if ride.status == "CANCELLED":
            # Explicitly cancelled or superseded by a newer QR: revoked token.
            raise RideTokenInvalidError()
        if ride.status != "PENDING":
            raise RideTokenReusedError()

        # Assign vehicle
        vehicle = await self.vehicle_repo.find_available_in_dock(dock_id)
        if not vehicle:
            # Cancel the pending ride (compare-and-set: only if still PENDING)
            await self.ride_repo.transition(ride.id, "PENDING", status="CANCELLED")
            raise VehicleUnavailableError()

        # Activate FIRST, atomically, and only if the ride is still PENDING. If a
        # concurrent cancel/expiry won the race this fails *before* we touch the
        # vehicle or slot, so nothing needs undoing.
        activated = await self.ride_repo.transition(
            ride.id, "PENDING",
            status="ACTIVE", vehicle_id=vehicle.id, started_at=_utcnow(),
        )
        if not activated:
            current = await self.ride_repo.refresh(ride.id)
            if current is not None and current.status == "EXPIRED":
                raise RideTokenExpiredError()
            if current is not None and current.status in ("ACTIVE", "COMPLETED"):
                raise RideTokenReusedError()
            raise RideTokenInvalidError()  # cancelled/superseded in the meantime

        # Free vehicle's slot, mark vehicle as IN_RIDE
        if vehicle.slot_id:
            await self.dock_repo.free_slot(vehicle.slot_id)
        await self.vehicle_repo.set_status(vehicle.id, "IN_RIDE")
        await self.vehicle_repo.update_slot(vehicle.id, None)

        ride = await self.ride_repo.refresh(ride.id)
        await self.audit_repo.log(ride.user_id, "RIDE_STARTED", "ride", str(ride.id))
        await self._notify(
            ride.user_id, "RIDE_START", "Ride started",
            "Your ride has started. Have a safe trip!",
        )
        return RideResponse.model_validate(ride)

    # ── fare estimate ────────────────────────────────────────────────────

    async def quote_fare(
        self, user_id: uuid.UUID, ride_id: uuid.UUID, destination_dock_id: uuid.UUID
    ) -> FareQuoteResponse:
        """Estimate the fare for ending ``ride_id`` at ``destination_dock_id``.

        Read-only: no ride/slot/wallet mutation and no row locks. The origin is
        taken from the stored ride — never from the client. The final fare is
        recomputed (and the slot re-checked) when the ride is actually ended.
        """
        ride = await self.ride_repo.find_by_id(ride_id)
        if not ride:
            raise RideNotFoundError()
        if ride.user_id != user_id:
            raise RideForbiddenError()
        if ride.status != "ACTIVE":
            raise RideInvalidStateError()

        dock = await self.dock_repo.find_by_id(destination_dock_id)
        if not dock or not dock.is_active:
            raise DockNotFoundError()
        if dock.id == ride.start_dock_id:
            raise SameDockReturnNotAllowedError()
        if await self.dock_repo.count_available_slots(destination_dock_id) < 1:
            raise DockFullError()

        fare = await self.pricing.calculate(self._pricing_context(ride, destination_dock_id))

        wallet = await self.wallet_service.wallet_repo.find_by_user_id(user_id)
        balance = quantize_money(wallet.balance) if wallet is not None else None
        sufficient = (
            None if wallet is None
            else balance >= fare.amount and wallet.currency.upper() == fare.currency.upper()
        )
        return FareQuoteResponse(
            ride_id=ride.id,
            origin_dock_id=ride.start_dock_id,
            destination_dock_id=destination_dock_id,
            fare_amount=fare.amount,
            currency=fare.currency,
            pricing_strategy=fare.strategy,
            pricing_reference_id=fare.reference_id,
            wallet_balance=balance,
            sufficient_balance=sufficient,
        )

    @staticmethod
    def _pricing_context(ride, destination_dock_id, ended_at=None, duration_seconds=None) -> PricingContext:
        return PricingContext(
            ride_id=ride.id,
            user_id=ride.user_id,
            origin_dock_id=ride.start_dock_id,
            destination_dock_id=destination_dock_id,
            started_at=ride.started_at,
            ended_at=ended_at,
            duration_seconds=duration_seconds,
        )

    # ── ending a ride ────────────────────────────────────────────────────

    async def end_ride(self, user_id: uuid.UUID, ride_id: uuid.UUID, end_dock_id: uuid.UUID) -> RideResponse:
        """End an ACTIVE ride at ``end_dock_id``: price, settle, park, complete.

        All-or-nothing. ``get_db`` commits after the handler returns, and the
        router turns ``AppException`` into a normal response, so a failure in
        the middle of this method would otherwise be *committed* half-done
        (slot taken but ride still ACTIVE, or similar). Therefore any failure
        explicitly rolls back the whole session before re-raising, and only
        after a successful COMMIT are notifications (irreversible pushes) sent.

        Idempotent: repeating a request for an already completed ride at the
        same dock returns that ride and never charges or parks twice.
        """
        session = self.ride_repo.session
        try:
            ride = await self.ride_repo.find_by_id_for_update(ride_id)
            if not ride:
                raise RideNotFoundError()
            if ride.user_id != user_id:
                raise RideForbiddenError()
            if ride.status == "COMPLETED" and ride.end_dock_id == end_dock_id:
                return RideResponse.model_validate(ride)  # safe replay
            if ride.status != "ACTIVE":
                raise RideInvalidStateError()

            response, fare = await self._complete_active_ride(ride, end_dock_id, actor_id=user_id)
            await session.commit()  # durable before any external side effect
        except Exception:
            await session.rollback()
            raise

        await self._after_completion(user_id, fare)
        return response

    async def _complete_active_ride(
        self, ride, end_dock_id: uuid.UUID, *, actor_id: uuid.UUID, audit_note: str = ""
    ) -> tuple[RideResponse, FareResult]:
        """Validated completion shared by the user flow and admin recovery.

        Caller holds the ride row lock and is responsible for commit/rollback.
        Order: validate everything that can fail without writing → price →
        compare-and-set the ride → occupy slot → free vehicle → debit wallet.
        """
        end_dock = await self.dock_repo.find_by_id(end_dock_id)
        if not end_dock or not end_dock.is_active:
            raise DockNotFoundError()
        if end_dock.id == ride.start_dock_id:
            raise SameDockReturnNotAllowedError()

        now = _utcnow()
        started_at = ride.started_at or now
        duration_seconds = max(int((now - started_at).total_seconds()), 0)

        fare = await self.pricing.calculate(
            self._pricing_context(ride, end_dock_id, ended_at=now, duration_seconds=duration_seconds)
        )
        amount = float(fare.amount)  # legacy Float ledger columns; identical value everywhere

        # Re-check availability *now* (authoritative; the picker/quote may be stale).
        slot = await self.dock_repo.find_free_slot(end_dock_id)
        if not slot:
            raise DockFullError()

        completed = await self.ride_repo.transition(
            ride.id, "ACTIVE",
            status="COMPLETED", end_dock_id=end_dock_id, ended_at=now,
            duration_seconds=duration_seconds, fare_amount=amount,
            fare_currency=fare.currency, pricing_strategy=fare.strategy,
            pricing_reference_id=fare.reference_id,
        )
        if not completed:
            raise RideInvalidStateError()

        if not await self.dock_repo.try_occupy_slot(slot.id):
            raise DockFullError()
        if ride.vehicle_id:
            await self.vehicle_repo.set_status(ride.vehicle_id, "AVAILABLE")
            await self.vehicle_repo.update_slot(ride.vehicle_id, slot.id)

        # Wallet last: it can legitimately fail (insufficient balance / currency)
        # and then everything above is rolled back by the caller.
        await self.wallet_service.debit_for_ride(ride.user_id, amount, ride.id, currency=fare.currency)

        await self.audit_repo.log(
            actor_id, "RIDE_ENDED", "ride", str(ride.id),
            meta=f"fare={amount} {fare.currency} strategy={fare.strategy} "
                 f"ref={fare.reference_id} end_dock={end_dock_id}{audit_note}",
        )
        ride = await self.ride_repo.refresh(ride.id)
        return RideResponse.model_validate(ride), fare

    async def _after_completion(self, user_id: uuid.UUID, fare: FareResult) -> None:
        """Post-commit notifications. Failures must never undo a completed ride."""
        session = self.ride_repo.session
        try:
            await self._notify(
                user_id, "RIDE_END", "Ride completed",
                f"Your ride has ended. Fare charged: {fare.currency} {fare.amount:.2f}.",
            )
            wallet = await self.wallet_service.get_balance(user_id)
            if wallet.balance < settings.WALLET_MIN_RIDE_BALANCE:
                await self._notify(
                    user_id, "LOW_BALANCE", "Low wallet balance",
                    f"Your wallet balance is {wallet.currency} {wallet.balance:.2f}. Top up to keep riding.",
                )
        except Exception:  # noqa: BLE001 - best effort by design
            logger.exception("Post-completion notification failed for user %s", user_id)
            await session.rollback()

    # ── admin recovery ───────────────────────────────────────────────────

    async def recover_ride(
        self, actor_id: uuid.UUID, ride_id: uuid.UUID, action: str,
        dock_id: uuid.UUID | None, reason: str,
    ) -> RideResponse:
        """Admin recovery of a stuck ride, without bypassing any invariant.

        * PENDING + ``cancel_pending``  → CANCELLED.
        * ACTIVE  + ``complete``        → the *same* validated completion as a
          normal end (explicit destination, free slot, configured fare, wallet
          debit). If the vehicle/slot records are inconsistent it refuses with
          the exact findings instead of guessing.
        Every recovery is audit-logged with the actor and reason.
        """
        session = self.ride_repo.session
        fare = None
        try:
            ride = await self.ride_repo.find_by_id_for_update(ride_id)
            if not ride:
                raise RideNotFoundError()
            note = f" recovery_by={actor_id} reason={reason!r}"

            if ride.status == "PENDING":
                if action != "cancel_pending":
                    raise RideRecoveryError(
                        "Ride is PENDING; the only recovery action is 'cancel_pending'."
                    )
                if not await self.ride_repo.transition(ride.id, "PENDING", status="CANCELLED"):
                    raise RideInvalidStateError()
                await self.audit_repo.log(actor_id, "RIDE_RECOVERED_CANCELLED", "ride", str(ride.id), meta=note)
                response = RideResponse.model_validate(await self.ride_repo.refresh(ride.id))

            elif ride.status == "ACTIVE":
                if action != "complete" or dock_id is None:
                    raise RideRecoveryError(
                        "An ACTIVE ride is recovered only with action='complete' and an explicit "
                        "destination dock_id; it is never just marked cancelled."
                    )
                await self._assert_recoverable(ride)
                response, fare = await self._complete_active_ride(
                    ride, dock_id, actor_id=actor_id, audit_note=note
                )
                await self.audit_repo.log(actor_id, "RIDE_RECOVERED_COMPLETED", "ride", str(ride.id), meta=note)
            else:
                raise RideInvalidStateError(f"Ride is {ride.status}; nothing to recover.")
            await session.commit()
        except Exception:
            await session.rollback()
            raise

        if fare is not None:
            await self._after_completion(ride.user_id, fare)
        return response

    async def _assert_recoverable(self, ride) -> None:
        """Refuse recovery when vehicle/slot records disagree (see docs for manual steps)."""
        problems: list[str] = []
        if ride.vehicle_id is None:
            problems.append("ride has no vehicle_id")
        else:
            vehicle = await self.vehicle_repo.find_by_id(ride.vehicle_id)
            if vehicle is None:
                problems.append(f"vehicle {ride.vehicle_id} does not exist")
            else:
                if vehicle.status != "IN_RIDE":
                    problems.append(f"vehicle status is {vehicle.status}, expected IN_RIDE")
                if vehicle.slot_id is not None:
                    problems.append(f"vehicle still references slot {vehicle.slot_id}, expected none")
        if problems:
            raise RideRecoveryError(
                "Inconsistent state, nothing was changed: " + "; ".join(problems)
                + ". Follow 'Manual diagnostics' in docs/pricing-and-ride-lifecycle.md."
            )

    async def get_ride(self, user_id: uuid.UUID, ride_id: uuid.UUID) -> RideResponse:
        ride = await self.ride_repo.find_by_id(ride_id)
        if not ride:
            raise RideNotFoundError()
        if ride.user_id != user_id:
            raise RideForbiddenError()
        if _is_stale_pending(ride, _utcnow()):
            ride = await self._expire_ride(ride)
        return RideResponse.model_validate(ride)

    async def cancel_pending_ride(self, user_id: uuid.UUID, ride_id: uuid.UUID) -> RideResponse:
        """Explicitly cancel a PENDING ride (e.g. user left the QR screen).

        Idempotent for rides that already ended up CANCELLED/EXPIRED.
        ACTIVE/COMPLETED rides cannot be cancelled here.
        """
        ride = await self.ride_repo.find_by_id(ride_id)
        if not ride:
            raise RideNotFoundError()
        if ride.user_id != user_id:
            raise RideForbiddenError()
        if _is_stale_pending(ride, _utcnow()):
            ride = await self._expire_ride(ride)
        if ride.status == "PENDING":
            # Compare-and-set: a scan that activated the ride a moment ago must
            # win — an active ride is never silently flipped to CANCELLED.
            cancelled = await self.ride_repo.transition(ride.id, "PENDING", status="CANCELLED")
            ride = await self.ride_repo.refresh(ride.id)
            if cancelled:
                await self.audit_repo.log(user_id, "RIDE_CANCELLED", "ride", str(ride.id))
        if ride.status not in ("CANCELLED", "EXPIRED"):
            raise RideInvalidStateError()
        return RideResponse.model_validate(ride)

    async def get_active_ride(self, user_id: uuid.UUID) -> RideResponse | None:
        await self._expire_stale_pending(user_id)
        ride = await self.ride_repo.find_active_for_user(user_id)
        if not ride:
            return None
        return RideResponse.model_validate(ride)

    async def list_rides(self, user_id: uuid.UUID, skip: int = 0, limit: int = 20) -> RideListResponse:
        await self._expire_stale_pending(user_id)
        rides, total = await self.ride_repo.list_for_user(user_id, skip, limit)
        return RideListResponse(
            items=[RideResponse.model_validate(r) for r in rides],
            total=total,
        )
