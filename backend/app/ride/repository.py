import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ride import Ride
from app.models.vehicle import Vehicle

ACTIVE_RIDE_STATUSES = ("REQUESTED", "ASSIGNED", "UNLOCK_PENDING", "ACTIVE", "END_PENDING")


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class RideRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_active_for_user(self, user_id: uuid.UUID) -> Ride | None:
        result = await self.session.execute(
            select(Ride).where(Ride.user_id == user_id, Ride.status.in_(ACTIVE_RIDE_STATUSES))
        )
        return result.scalar_one_or_none()

    async def find_by_id(self, ride_id: uuid.UUID) -> Ride | None:
        result = await self.session.execute(select(Ride).where(Ride.id == ride_id))
        return result.scalar_one_or_none()

    async def create_assigned(
        self, user_id: uuid.UUID, vehicle_id: uuid.UUID, dock_start_id: uuid.UUID
    ) -> Ride:
        """Ride enters the table already ASSIGNED.

        No queue/matching worker in scope — REQUESTED as its own persisted
        row would be a dangling state nobody advances. Vehicle availability
        checked synchronously before this call; row only ever persisted
        once assignment is guaranteed. RideEvent still records a synthetic
        REQUESTED entry for audit continuity.
        """
        ride = Ride(user_id=user_id, vehicle_id=vehicle_id, dock_start_id=dock_start_id, status="ASSIGNED")
        self.session.add(ride)
        await self.session.flush()
        return ride

    async def update_status(self, ride_id: uuid.UUID, status: str, **fields) -> Ride:
        ride = await self.find_by_id(ride_id)
        ride.status = status
        for key, value in fields.items():
            setattr(ride, key, value)
        await self.session.flush()
        return ride


class VehicleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_available_for_assignment(self, min_battery: int) -> Vehicle | None:
        """Row-locked so two concurrent ride requests can't grab the same
        vehicle. No-op lock on SQLite tests, fully effective on Postgres."""
        result = await self.session.execute(
            select(Vehicle)
            .where(
                Vehicle.status == "AVAILABLE",
                Vehicle.dock_id.is_not(None),
                Vehicle.battery_pct.is_not(None),
                Vehicle.battery_pct >= min_battery,
            )
            .order_by(Vehicle.last_seen_at.desc().nullslast())
            .limit(1)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def find_by_id(self, vehicle_id: uuid.UUID) -> Vehicle | None:
        result = await self.session.execute(select(Vehicle).where(Vehicle.id == vehicle_id))
        return result.scalar_one_or_none()

    async def update_status(self, vehicle_id: uuid.UUID, status: str) -> Vehicle:
        vehicle = await self.find_by_id(vehicle_id)
        vehicle.status = status
        await self.session.flush()
        return vehicle
