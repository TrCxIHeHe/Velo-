import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wallet import Wallet, WalletTransaction


class WalletRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_by_user_id(self, user_id: uuid.UUID) -> Wallet | None:
        result = await self.session.execute(select(Wallet).where(Wallet.user_id == user_id))
        return result.scalar_one_or_none()

    async def find_by_user_id_for_update(self, user_id: uuid.UUID) -> Wallet | None:
        result = await self.session.execute(
            select(Wallet).where(Wallet.user_id == user_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def create(self, user_id: uuid.UUID, currency: str = "INR") -> Wallet:
        wallet = Wallet(user_id=user_id, balance=0.0, currency=currency)
        self.session.add(wallet)
        await self.session.flush()
        return wallet

    async def update_balance(self, wallet_id: uuid.UUID, new_balance: float) -> None:
        from sqlalchemy import update
        from datetime import datetime, timezone
        await self.session.execute(
            update(Wallet).where(Wallet.id == wallet_id).values(
                balance=new_balance,
                updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
        await self.session.flush()

    async def create_transaction(
        self,
        wallet_id: uuid.UUID,
        txn_type: str,
        source: str,
        amount: float,
        balance_after: float,
        reference_id: str | None = None,
        note: str | None = None,
    ) -> WalletTransaction:
        txn = WalletTransaction(
            wallet_id=wallet_id,
            type=txn_type,
            source=source,
            amount=amount,
            balance_after=balance_after,
            reference_id=reference_id,
            note=note,
        )
        self.session.add(txn)
        await self.session.flush()
        return txn

    async def find_transaction_by_reference(self, reference_id: str) -> WalletTransaction | None:
        result = await self.session.execute(
            select(WalletTransaction).where(WalletTransaction.reference_id == reference_id)
        )
        return result.scalar_one_or_none()

    async def list_transactions(
        self, wallet_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> tuple[list[WalletTransaction], int]:
        count_result = await self.session.execute(
            select(func.count()).where(WalletTransaction.wallet_id == wallet_id)
        )
        total = count_result.scalar_one()
        result = await self.session.execute(
            select(WalletTransaction)
            .where(WalletTransaction.wallet_id == wallet_id)
            .order_by(WalletTransaction.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars()), total

    async def count_wallets(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(Wallet))
        return result.scalar_one()

    async def sum_by_source(self, source: str) -> Decimal:
        """Sum transaction amounts for a given `source` (TOPUP | RIDE_FARE |
        REFUND | ADMIN_ADJUSTMENT) — powers the admin revenue dashboard."""
        result = await self.session.execute(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.source == source
            )
        )
        return Decimal(str(result.scalar_one()))
