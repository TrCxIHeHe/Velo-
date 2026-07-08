import uuid

from app.config import settings
from app.core.exceptions import (
    DockMismatchError,
    RideAlreadyActiveError,
    RideForbiddenError,
    RideInvalidStateError,
    RideNotFoundError,
    VehicleUnavailableError,
)
from app.dock.repository import DockRepository
from app.ride.event_repository import RideEventRepository
from app.ride.repository import RideRepository, VehicleRepository, utcnow
from app.ride.schemas import (
    RideResponse,
    RideTokenResponse,
    UnlockResponse,
    ValidateTokenResponse,
)
from app.ride.token_codec import RideTokenCodec


class RideService:
    def __init__(
        self,
        ride_repo: RideRepository,
        vehicle_repo: VehicleRepository,
        dock_repo: DockRepository,
        event_repo: RideEventRepository,
        token_codec: RideTokenCodec,
    ) -> None:
        self.ride_repo = ride_repo
        self.vehicle_repo = vehicle_repo
        self.dock_repo = dock_repo
        self.event_repo = event_repo
        self.token_codec = token_codec

    # ── Vehicle Assignment ───────────────────────────────────────────────────

    async def request_ride(self, user_id: uuid.UUID) -> RideResponse:
        existing = await self.ride_repo.find_active_for_user(user_id)
        if existing is not None:
            raise RideAlreadyActiveError()

        vehicle = await self.vehicle_repo.find_available_for_assignment(
            settings.VEHICLE_BATTERY_MIN_THRESHOLD
        )
        if vehicle is None:
            raise VehicleUnavailableError()

        await self.vehicle_repo.update_status(vehicle.id, "RESERVED")
        ride = await self.ride_repo.create_assigned(user_id, vehicle.id, vehicle.dock_id)

        await self.event_repo.log(ride.id, "REQUESTED", {"user_id": str(user_id)})
        await self.event_repo.log(
            ride.id, "ASSIGNED", {"vehicle_id": str(vehicle.id), "dock_id": str(vehicle.dock_id)}
        )
        return RideResponse.model_validate(ride)

    # ── Reads ─────────────────────────────────────────────────────────────────

    async def get_ride(self, ride_id: uuid.UUID, requester_id: uuid.UUID) -> RideResponse:
        ride = await self.ride_repo.find_by_id(ride_id)
        if ride is None:
            raise RideNotFoundError()
        if ride.user_id != requester_id:
            raise RideForbiddenError()
        return RideResponse.model_validate(ride)

    async def get_status(self, ride_id: uuid.UUID, requester_id: uuid.UUID) -> dict:
        ride = await self.ride_repo.find_by_id(ride_id)
        if ride is None:
            raise RideNotFoundError()
        if ride.user_id != requester_id:
            raise RideForbiddenError()
        return {"id": ride.id, "status": ride.status}

    # ── Ride Token Issuance ───────────────────────────────────────────────────

    async def issue_ride_token(self, user_id: uuid.UUID) -> RideTokenResponse:
        ride = await self.ride_repo.find_active_for_user(user_id)
        if ride is None or ride.status != "ASSIGNED":
            raise RideInvalidStateError("No ride awaiting unlock. Request a ride first.")

        token, exp = await self.token_codec.issue(user_id, ride.id)
        return RideTokenResponse(
            ride_token=token, expires_in=settings.RIDE_TOKEN_TTL_SECONDS, expires_at=exp
        )

    # ── QR Validation + Ride Token Consumption ──────────────────────────────

    async def validate_token(self, dock_id: uuid.UUID, raw_token: str) -> ValidateTokenResponse:
        user_id, ride_id = await self.token_codec.consume(raw_token)

        ride = await self.ride_repo.find_by_id(ride_id)
        if ride is None:
            raise RideNotFoundError()
        if ride.user_id != user_id:
            raise RideForbiddenError()
        if ride.status != "ASSIGNED":
            raise RideInvalidStateError()
        if ride.dock_start_id != dock_id:
            raise DockMismatchError()

        await self.ride_repo.update_status(ride.id, "UNLOCK_PENDING")
        await self.event_repo.log(ride.id, "QR_SCANNED", {"dock_id": str(dock_id)})
        await self.event_repo.log(ride.id, "DOCK_VALIDATED", {"dock_id": str(dock_id)})
        return ValidateTokenResponse(ride_id=ride.id, status="UNLOCK_PENDING")

    # ── Unlock Authorization ─────────────────────────────────────────────────

    async def authorize_unlock(self, dock_id: uuid.UUID, ride_id: uuid.UUID) -> UnlockResponse:
        ride = await self.ride_repo.find_by_id(ride_id)
        if ride is None:
            raise RideNotFoundError()
        if ride.status != "UNLOCK_PENDING":
            raise RideInvalidStateError()
        if ride.dock_start_id != dock_id:
            raise DockMismatchError()

        started_at = utcnow()
        await self.ride_repo.update_status(ride.id, "ACTIVE", start_at=started_at)
        await self.vehicle_repo.update_status(ride.vehicle_id, "IN_USE")

        slot = await self.dock_repo.find_slot_by_vehicle(dock_id, ride.vehicle_id)
        if slot is not None:
            await self.dock_repo.release_slot(slot)

        await self.event_repo.log(
            ride.id, "DOCK_UNLOCKED", {"dock_id": str(dock_id), "vehicle_id": str(ride.vehicle_id)}
        )
        await self.event_repo.log(ride.id, "RIDE_STARTED", {"started_at": started_at.isoformat()})
        return UnlockResponse(
            ride_id=ride.id, status="ACTIVE", vehicle_id=ride.vehicle_id, started_at=started_at
        )
