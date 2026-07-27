import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ride import Ride


class RideRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, user_id: uuid.UUID, start_dock_id: uuid.UUID, jti: str) -> Ride:
        ride = Ride(user_id=user_id, start_dock_id=start_dock_id, ride_token_jti=jti, status="PENDING")
        self.session.add(ride)
        await self.session.flush()
        return ride

    async def find_by_id(self, ride_id: uuid.UUID) -> Ride | None:
        result = await self.session.execute(select(Ride).where(Ride.id == ride_id))
        return result.scalar_one_or_none()

    async def find_active_for_user(self, user_id: uuid.UUID) -> Ride | None:
        result = await self.session.execute(
            select(Ride).where(Ride.user_id == user_id, Ride.status.in_(["PENDING", "ACTIVE"]))
        )
        return result.scalar_one_or_none()

    async def find_by_jti(self, jti: str) -> Ride | None:
        result = await self.session.execute(select(Ride).where(Ride.ride_token_jti == jti))
        return result.scalar_one_or_none()

    async def update(self, ride_id: uuid.UUID, **kwargs) -> Ride | None:
        await self.session.execute(update(Ride).where(Ride.id == ride_id).values(**kwargs))
        await self.session.flush()
        return await self.find_by_id(ride_id)

    async def list_for_user(
        self, user_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> tuple[list[Ride], int]:
        count_result = await self.session.execute(
            select(func.count()).where(Ride.user_id == user_id)
        )
        total = count_result.scalar_one()
        result = await self.session.execute(
            select(Ride)
            .where(Ride.user_id == user_id)
            .order_by(Ride.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars()), total

    async def list_all(self, skip: int = 0, limit: int = 50) -> tuple[list[Ride], int]:
        count_result = await self.session.execute(select(func.count(Ride.id)))
        total = count_result.scalar_one()
        result = await self.session.execute(
            select(Ride).order_by(Ride.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars()), total
