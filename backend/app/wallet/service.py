import uuid
from decimal import Decimal

from app.exceptions import (
    DuplicateReferenceError,
    InsufficientBalanceError,
    InvalidTransactionAmountError,
    WalletNotFoundError,
)
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

    async def _check_idempotency(self, wallet_id: uuid.UUID, reference_id: str | None) -> None:
        """Reference IDs (e.g. a Razorpay payment id or a ride id) must map to
        exactly one ledger entry. If a caller retries a request (network
        timeout, double-tap on the client) with the same reference_id, we
        reject the duplicate rather than crediting/debiting the wallet twice.
        """
        if reference_id is None:
            return
        existing = await self.repo.find_transaction_by_reference(wallet_id, reference_id)
        if existing is not None:
            raise DuplicateReferenceError()

    async def credit(self, user_id: uuid.UUID, amount: Decimal, reference_id: str | None) -> TransactionResponse:
        if amount <= 0:
            raise InvalidTransactionAmountError()
        wallet = await self.repo.get_or_create(user_id)
        await self._check_idempotency(wallet.id, reference_id)
        txn = await self.repo.add_transaction(wallet.id, "CREDIT", amount, reference_id)
        return TransactionResponse.model_validate(txn)

    async def debit(self, user_id: uuid.UUID, amount: Decimal, reference_id: str | None) -> TransactionResponse:
        if amount <= 0:
            raise InvalidTransactionAmountError()

        # Row-locked read: on Postgres this blocks any concurrent debit
        # against the same wallet until this transaction commits, so two
        # simultaneous ride-end requests can never both pass the balance
        # check against the same starting balance. No-op on SQLite (tests).
        wallet = await self.repo.find_by_user_id_locked(user_id)
        if wallet is None:
            raise WalletNotFoundError()

        await self._check_idempotency(wallet.id, reference_id)

        balance = await self.repo.get_balance(wallet.id)
        if balance < amount:
            raise InsufficientBalanceError()

        txn = await self.repo.add_transaction(wallet.id, "DEBIT", amount, reference_id)
        return TransactionResponse.model_validate(txn)

    async def refund(self, user_id: uuid.UUID, amount: Decimal, reference_id: str | None) -> TransactionResponse:
        if amount <= 0:
            raise InvalidTransactionAmountError()
        wallet = await self.repo.get_or_create(user_id)
        await self._check_idempotency(wallet.id, reference_id)
        txn = await self.repo.add_transaction(wallet.id, "REFUND", amount, reference_id)
        return TransactionResponse.model_validate(txn)

    async def get_transactions(self, user_id: uuid.UUID, limit: int = 50, offset: int = 0) -> list[TransactionResponse]:
        wallet = await self.repo.get_or_create(user_id)
        txns = await self.repo.list_transactions(wallet.id, limit, offset)
        return [TransactionResponse.model_validate(t) for t in txns]
