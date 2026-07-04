import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Dock(Base):
    """Location stored as plain lat/lng floats for MVP portability — this avoids
    a PostGIS dependency in tests (SQLite has no geometry support) and matches
    the "validate first, optimize later" principle from the architecture doc.
    Swap `latitude`/`longitude` for a PostGIS Geography(POINT) column later if
    proximity/radius queries need to happen at the DB level.
    """
    __tablename__ = "docks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    total_slots: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    def __repr__(self) -> str:
        return f"<Dock id={self.id} name={self.name} slots={self.total_slots}>"
