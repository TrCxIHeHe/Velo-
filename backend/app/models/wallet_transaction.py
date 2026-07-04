import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WalletTransaction(Base):
    """Append-only ledger entry. Never updated or deleted after creation.

    type: CREDIT (recharge) | DEBIT (ride/spend) | REFUND (money back)
    `amount` is always stored positive — the sign is implied by `type`, so a
    bug can never accidentally flip a debit into a credit.
    """
    __tablename__ = "wallet_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(10), nullable=False)  # CREDIT | DEBIT | REFUND
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    reference_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    wallet: Mapped["Wallet"] = relationship("Wallet", back_populates="transactions")

    def __repr__(self) -> str:
        return f"<WalletTransaction id={self.id} type={self.type} amount={self.amount}>"
