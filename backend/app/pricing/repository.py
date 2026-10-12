import uuid
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dock_pair_fare import DockPairFare


class DockPairFareRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, origin: uuid.UUID, destination: uuid.UUID, amount: Decimal, currency: str, is_active: bool
    ) -> DockPairFare:
        fare = DockPairFare(
            origin_dock_id=origin, destination_dock_id=destination,
            amount=amount, currency=currency, is_active=is_active,
        )
        self.session.add(fare)
        await self.session.flush()
        return fare

    async def find_by_id(self, fare_id: uuid.UUID) -> DockPairFare | None:
        res = await self.session.execute(select(DockPairFare).where(DockPairFare.id == fare_id))
        return res.scalar_one_or_none()

    async def find_by_pair(self, origin: uuid.UUID, destination: uuid.UUID) -> DockPairFare | None:
        res = await self.session.execute(
            select(DockPairFare).where(
                DockPairFare.origin_dock_id == origin,
                DockPairFare.destination_dock_id == destination,
            )
        )
        return res.scalar_one_or_none()

    async def list(
        self,
        origin: uuid.UUID | None = None,
        destination: uuid.UUID | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[DockPairFare]:
        q = select(DockPairFare)
        if origin is not None:
            q = q.where(DockPairFare.origin_dock_id == origin)
        if destination is not None:
            q = q.where(DockPairFare.destination_dock_id == destination)
        if is_active is not None:
            q = q.where(DockPairFare.is_active.is_(is_active))
        q = q.order_by(DockPairFare.origin_dock_id, DockPairFare.destination_dock_id).offset(skip).limit(limit)
        return list((await self.session.execute(q)).scalars())

    async def update(self, fare_id: uuid.UUID, **values) -> DockPairFare | None:
        from app.core.timeutil import naive_utcnow
        await self.session.execute(
            update(DockPairFare).where(DockPairFare.id == fare_id).values(updated_at=naive_utcnow(), **values)
        )
        await self.session.flush()
        # populate_existing: the UPDATE bypassed the identity map.
        res = await self.session.execute(
            select(DockPairFare).where(DockPairFare.id == fare_id).execution_options(populate_existing=True)
        )
        return res.scalar_one_or_none()
