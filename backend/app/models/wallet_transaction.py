import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from app.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("wallets.id"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    reference_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    wallet: Mapped["Wallet"] = relationship("Wallet", back_populates="transactions")  # noqa: F821

    def __repr__(self) -> str:
        return f"<WalletTransaction id={self.id} type={self.type} amount={self.amount}>"
