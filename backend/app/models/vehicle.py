import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from app.types import GUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    qr_code: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="AVAILABLE", index=True)
    battery_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dock_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("docks.id"), nullable=True, index=True
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Vehicle id={self.id} status={self.status}>"
