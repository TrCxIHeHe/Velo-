import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.types import GUID


class Ride(Base):
    """
    Lifecycle:
      PENDING  → user has ride token, hardware not yet confirmed
      ACTIVE   → hardware confirmed unlock, ride in progress
      COMPLETED→ user docked at end dock, fare settled
      CANCELLED→ token expired or aborted before hardware confirmation
    """
    __tablename__ = "rides"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True)
    start_dock_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("docks.id", ondelete="RESTRICT"), nullable=False)
    end_dock_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("docks.id", ondelete="RESTRICT"), nullable=True)

    # status: PENDING | ACTIVE | COMPLETED | CANCELLED
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", server_default="PENDING", index=True)

    ride_token_jti: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fare_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    fare_currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR", server_default="INR")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        server_default=text("now()"), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    user: Mapped["User"] = relationship("User", back_populates="rides", lazy="noload")
    vehicle: Mapped["Vehicle"] = relationship("Vehicle", lazy="noload")
    start_dock: Mapped["Dock"] = relationship("Dock", foreign_keys=[start_dock_id], lazy="noload")
    end_dock: Mapped["Dock"] = relationship("Dock", foreign_keys=[end_dock_id], lazy="noload")
