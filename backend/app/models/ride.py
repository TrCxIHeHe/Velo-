import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from app.types import GUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Ride(Base):
    __tablename__ = "rides"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id"), nullable=False, index=True
    )
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("vehicles.id"), nullable=True, index=True
    )
    dock_start_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("docks.id"), nullable=True)
    dock_end_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("docks.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="REQUESTED", index=True)
    fare: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    def __repr__(self) -> str:
        return f"<Ride id={self.id} status={self.status}>"
