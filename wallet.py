import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Wallet(Base):
    """One wallet per user. Balance is NEVER stored — always computed from
    wallet_transactions (SUM(CREDIT) + SUM(REFUND) - SUM(DEBIT)). This makes
    the balance tamper-resistant and gives us a full audit trail for free.
    """
    __tablename__ = "wallets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True
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