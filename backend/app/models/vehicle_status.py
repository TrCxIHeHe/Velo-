import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class VehicleStatus(Base):
    """Time-series IoT telemetry snapshots reported by vehicle hardware."""
    __tablename__ = "vehicle_status"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=False, index=True
    )
    battery_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    location: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    def __repr__(self) -> str:
        return f"<VehicleStatus vehicle_id={self.vehicle_id} battery={self.battery_pct}>"