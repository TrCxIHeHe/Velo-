import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.types import GUID


class Dock(Base):
    """Physical dock station containing one or more slots."""
    __tablename__ = "docks"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location_lat: Mapped[float] = mapped_column(Float, nullable=False)
    location_lng: Mapped[float] = mapped_column(Float, nullable=False)
    address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    total_slots: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        server_default=text("now()"), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    slots: Mapped[list["DockSlot"]] = relationship("DockSlot", back_populates="dock", lazy="noload")


class DockSlot(Base):
    """Individual slot within a dock. Holds zero or one vehicle."""
    __tablename__ = "dock_slots"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    dock_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("docks.id", ondelete="CASCADE"), nullable=False, index=True)
    slot_number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_occupied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        server_default=text("now()")
    )

    dock: Mapped["Dock"] = relationship("Dock", back_populates="slots", lazy="noload")
    vehicle: Mapped["Vehicle"] = relationship("Vehicle", back_populates="slot", uselist=False, lazy="noload")


class Vehicle(Base):
    """Scooter/bike. Lives in exactly one dock slot when docked."""
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    qr_code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(50), nullable=False, default="SCOOTER")
    battery_level: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    # status: AVAILABLE | IN_RIDE | MAINTENANCE
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="AVAILABLE", server_default="AVAILABLE")
    slot_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("dock_slots.id", ondelete="SET NULL"), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        server_default=text("now()"), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    slot: Mapped["DockSlot"] = relationship("DockSlot", back_populates="vehicle", lazy="noload")
