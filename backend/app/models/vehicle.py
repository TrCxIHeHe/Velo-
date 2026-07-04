import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Vehicle(Base):
    """Schema owned by Track B (DB design). Vehicle Service business logic
    (assignment, health checks) is owned by Track A — this table is here so
    Dock and Wallet can reference it via foreign key."""
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    qr_code: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="AVAILABLE", index=True)
    battery_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dock_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("docks.id"), nullable=True, index=True
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Vehicle id={self.id} status={self.status}>"
