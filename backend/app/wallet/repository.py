import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wallet import Wallet
from app.models.wallet_transaction import WalletTransaction


class WalletRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_by_user_id(self, user_id: uuid.UUID) -> Wallet | None:
        result = await self.session.execute(select(Wallet).where(Wallet.user_id == user_id))
        return result.scalar_one_or_none()

    async def create(self, user_id: uuid.UUID, currency: str = "INR") -> Wallet:
        wallet = Wallet(user_id=user_id, currency=currency)
        self.session.add(wallet)
        await self.session.flush()
        return wallet

    async def get_or_create(self, user_id: uuid.UUID) -> Wallet:
        wallet = await self.find_by_user_id(user_id)
        if wallet is None:
            wallet = await self.create(user_id)
        return wallet

    async def get_balance(self, wallet_id: uuid.UUID) -> Decimal:
        credit_refund = select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
            WalletTransaction.wallet_id == wallet_id,
            WalletTransaction.type.in_(["CREDIT", "REFUND"]),
        )
        debit = select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
            WalletTransaction.wallet_id == wallet_id,
            WalletTransaction.type == "DEBIT",
        )
        credits = (await self.session.execute(credit_refund)).scalar_one()
        debits = (await self.session.execute(debit)).scalar_one()
        return Decimal(credits) - Decimal(debits)

    async def add_transaction(
        self, wallet_id: uuid.UUID, type_: str, amount: Decimal, reference_id: str | None
    ) -> WalletTransaction:
        txn = WalletTransaction(wallet_id=wallet_id, type=type_, amount=amount, reference_id=reference_id)
        self.session.add(txn)
        await self.session.flush()
        return txn

    async def list_transactions(self, wallet_id: uuid.UUID, limit: int = 50, offset: int = 0) -> list[WalletTransaction]:
        result = await self.session.execute(
            select(WalletTransaction)
            .where(WalletTransaction.wallet_id == wallet_id)
            .order_by(WalletTransaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())