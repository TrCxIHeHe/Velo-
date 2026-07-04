import uuid

from sqlalchemy import Boolean, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DockSlot(Base):
    """Physical slot state within a dock. vehicle_id is null when the slot is empty."""
    __tablename__ = "dock_slots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dock_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("docks.id"), nullable=False, index=True
    )
    slot_number: Mapped[int] = mapped_column(Integer, nullable=False)
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=True
    )
    is_occupied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_charging: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return f"<DockSlot dock_id={self.dock_id} slot={self.slot_number} occupied={self.is_occupied}>"
