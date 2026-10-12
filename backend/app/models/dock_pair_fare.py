import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Numeric, String,
    UniqueConstraint, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import naive_utcnow
from app.database import Base
from app.types import GUID


class DockPairFare(Base):
    """Fixed fare for one *directed* origin → destination dock pair.

    (A → B) and (B → A) are independent rows and may differ. Money is stored
    as NUMERIC(10, 2) — never floating point.
    """

    __tablename__ = "dock_pair_fares"
    __table_args__ = (
        UniqueConstraint("origin_dock_id", "destination_dock_id", name="uq_dock_pair_fare_direction"),
        CheckConstraint("amount > 0", name="ck_dock_pair_fare_amount_positive"),
        CheckConstraint("origin_dock_id <> destination_dock_id", name="ck_dock_pair_fare_distinct_docks"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    origin_dock_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("docks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    destination_dock_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("docks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2, asdecimal=True), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR", server_default="INR")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=naive_utcnow, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=naive_utcnow, server_default=text("now()"), onupdate=naive_utcnow
    )
