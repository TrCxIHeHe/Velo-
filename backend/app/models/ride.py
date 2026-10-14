import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.types import GUID


class Ride(Base):
    """
    Lifecycle:
      PENDING  → user has ride token, hardware not yet confirmed
      ACTIVE   → hardware confirmed unlock, ride in progress
      COMPLETED→ user docked at end dock, fare settled
      CANCELLED→ explicitly cancelled, or superseded by a newer ride token
      EXPIRED  → ride token TTL elapsed without a valid scan
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
    planned_end_dock_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("docks.id", ondelete="RESTRICT"), nullable=True
    )

    # status: PENDING | ACTIVE | COMPLETED | CANCELLED | EXPIRED
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", server_default="PENDING", index=True)

    ride_token_jti: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fare_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    fare_currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR", server_default="INR")
    accepted_fare_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2, asdecimal=True), nullable=True
    )
    accepted_fare_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    accepted_pricing_strategy: Mapped[str | None] = mapped_column(String(50), nullable=True)
    accepted_pricing_reference_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    # Which pricing strategy produced fare_amount, and the record it used (for a
    # dock-pair fare: dock_pair_fares.id). Plain columns (no FK) so the receipt
    # keeps explaining the charge even if the tariff row is later removed.
    pricing_strategy: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pricing_reference_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)

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
    planned_end_dock: Mapped["Dock"] = relationship("Dock", foreign_keys=[planned_end_dock_id], lazy="noload")

    __table_args__ = (
        Index(
            "uq_rides_one_open_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('PENDING', 'ACTIVE')"),
            sqlite_where=text("status IN ('PENDING', 'ACTIVE')"),
        ),
    )
