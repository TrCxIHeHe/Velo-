import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.types import GUID


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    balance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR", server_default="INR")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        server_default=text("now()"), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    user: Mapped["User"] = relationship("User", back_populates="wallet", lazy="noload")
    transactions: Mapped[list["WalletTransaction"]] = relationship(
        "WalletTransaction", back_populates="wallet", lazy="noload"
    )


class WalletTransaction(Base):
    """
    type: CREDIT | DEBIT
    source: TOPUP | RIDE_FARE | REFUND | ADMIN_ADJUSTMENT
    """
    __tablename__ = "wallet_transactions"
    __table_args__ = (
        UniqueConstraint("reference_id", name="uq_wallet_txn_reference"),
        CheckConstraint("amount > 0", name="ck_wallet_txn_amount_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("wallets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(10), nullable=False)   # CREDIT | DEBIT
    source: Mapped[str] = mapped_column(String(30), nullable=False)  # TOPUP | RIDE_FARE | REFUND | ADMIN_ADJUSTMENT
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    balance_after: Mapped[float] = mapped_column(Float, nullable=False)
    reference_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    note: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        server_default=text("now()")
    )

    wallet: Mapped["Wallet"] = relationship("Wallet", back_populates="transactions", lazy="noload")
