import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from app.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id"), nullable=False, unique=True, index=True
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    transactions: Mapped[list["WalletTransaction"]] = relationship(  # noqa: F821
        "WalletTransaction", back_populates="wallet", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Wallet id={self.id} user_id={self.user_id}>"