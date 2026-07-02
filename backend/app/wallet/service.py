import uuid
from decimal import Decimal

from app.core.exceptions import InsufficientBalanceError, WalletNotFoundError
from app.wallet.repository import WalletRepository
from app.wallet.schemas import TransactionResponse, WalletResponse


class WalletService:
    def __init__(self, repo: WalletRepository) -> None:
        self.repo = repo

    async def get_wallet(self, user_id: uuid.UUID) -> WalletResponse:
        wallet = await self.repo.get_or_create(user_id)
        balance = await self.repo.get_balance(wallet.id)
        return WalletResponse(
            id=wallet.id, user_id=wallet.user_id, currency=wallet.currency,
            balance=balance, created_at=wallet.created_at,
        )

    async def credit(self, user_id: uuid.UUID, amount: Decimal, reference_id: str | None) -> TransactionResponse:
        wallet = await self.repo.get_or_create(user_id)
        txn = await self.repo.add_transaction(wallet.id, "CREDIT", amount, reference_id)
        return TransactionResponse.model_validate(txn)

    async def debit(self, user_id: uuid.UUID, amount: Decimal, reference_id: str | None) -> TransactionResponse:
        wallet = await self.repo.find_by_user_id(user_id)
        if wallet is None:
            raise WalletNotFoundError()
        balance = await self.repo.get_balance(wallet.id)
        if balance < amount:
            raise InsufficientBalanceError()
        txn = await self.repo.add_transaction(wallet.id, "DEBIT", amount, reference_id)
        return TransactionResponse.model_validate(txn)

    async def refund(self, user_id: uuid.UUID, amount: Decimal, reference_id: str | None) -> TransactionResponse:
        wallet = await self.repo.get_or_create(user_id)
        txn = await self.repo.add_transaction(wallet.id, "REFUND", amount, reference_id)
        return TransactionResponse.model_validate(txn)

    async def get_transactions(self, user_id: uuid.UUID, limit: int = 50, offset: int = 0) -> list[TransactionResponse]:
        wallet = await self.repo.get_or_create(user_id)
        txns = await self.repo.list_transactions(wallet.id, limit, offset)
        return [TransactionResponse.model_validate(t) for t in txns]