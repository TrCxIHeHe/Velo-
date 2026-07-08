import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ride_event import RideEvent


class RideEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log(self, ride_id: uuid.UUID, event_type: str, payload: dict | None = None) -> RideEvent:
        event = RideEvent(ride_id=ride_id, event_type=event_type, payload=payload)
        self.session.add(event)
        await self.session.flush()
        return event
