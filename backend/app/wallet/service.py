import uuid

from app.config import settings
from app.core.exceptions import (
    DuplicateReferenceError, InsufficientBalanceError,
    InvalidTransactionAmountError, WalletNotFoundError,
)
from app.wallet.repository import WalletRepository
from app.wallet.schemas import TransactionListResponse, TransactionResponse, WalletResponse


class WalletService:
    def __init__(self, wallet_repo: WalletRepository) -> None:
        self.wallet_repo = wallet_repo

    async def _get_or_create_wallet(self, user_id: uuid.UUID):
        wallet = await self.wallet_repo.find_by_user_id(user_id)
        if wallet is None:
            wallet = await self.wallet_repo.create(user_id, settings.WALLET_DEFAULT_CURRENCY)
        return wallet

    async def get_balance(self, user_id: uuid.UUID) -> WalletResponse:
        wallet = await self._get_or_create_wallet(user_id)
        return WalletResponse.model_validate(wallet)

    async def top_up(
        self, user_id: uuid.UUID, amount: float, reference_id: str | None = None
    ) -> WalletResponse:
        if amount <= 0:
            raise InvalidTransactionAmountError()
        if reference_id:
            existing = await self.wallet_repo.find_transaction_by_reference(reference_id)
            if existing:
                raise DuplicateReferenceError()

        wallet = await self.wallet_repo.find_by_user_id_for_update(user_id)
        if wallet is None:
            wallet = await self.wallet_repo.create(user_id, settings.WALLET_DEFAULT_CURRENCY)

        new_balance = wallet.balance + amount
        await self.wallet_repo.update_balance(wallet.id, new_balance)
        await self.wallet_repo.create_transaction(
            wallet.id, "CREDIT", "TOPUP", amount, new_balance, reference_id
        )
        wallet.balance = new_balance
        return WalletResponse.model_validate(wallet)

    async def debit_for_ride(
        self, user_id: uuid.UUID, amount: float, ride_id: uuid.UUID
    ) -> WalletResponse:
        """Called internally by ride service to settle fare."""
        if amount <= 0:
            raise InvalidTransactionAmountError()

        wallet = await self.wallet_repo.find_by_user_id_for_update(user_id)
        if wallet is None:
            raise WalletNotFoundError()
        if wallet.balance < amount:
            raise InsufficientBalanceError()

        new_balance = wallet.balance - amount
        await self.wallet_repo.update_balance(wallet.id, new_balance)
        await self.wallet_repo.create_transaction(
            wallet.id, "DEBIT", "RIDE_FARE", amount, new_balance,
            reference_id=f"ride:{ride_id}", note=f"Fare for ride {ride_id}"
        )
        wallet.balance = new_balance
        return WalletResponse.model_validate(wallet)

    async def admin_adjust(
        self, user_id: uuid.UUID, amount: float, note: str | None, reference_id: str | None
    ) -> WalletResponse:
        if amount == 0:
            raise InvalidTransactionAmountError()

        if reference_id:
            existing = await self.wallet_repo.find_transaction_by_reference(reference_id)
            if existing:
                raise DuplicateReferenceError()

        wallet = await self.wallet_repo.find_by_user_id_for_update(user_id)
        if wallet is None:
            wallet = await self.wallet_repo.create(user_id, settings.WALLET_DEFAULT_CURRENCY)

        new_balance = wallet.balance + amount
        if new_balance < 0:
            raise InsufficientBalanceError()

        await self.wallet_repo.update_balance(wallet.id, new_balance)
        txn_type = "CREDIT" if amount > 0 else "DEBIT"
        await self.wallet_repo.create_transaction(
            wallet.id, txn_type, "ADMIN_ADJUSTMENT", abs(amount), new_balance, reference_id, note
        )
        wallet.balance = new_balance
        return WalletResponse.model_validate(wallet)

    async def check_sufficient_for_ride(self, user_id: uuid.UUID) -> bool:
        wallet = await self.wallet_repo.find_by_user_id(user_id)
        if wallet is None:
            return False
        return wallet.balance >= settings.WALLET_MIN_RIDE_BALANCE

    async def list_transactions(
        self, user_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> TransactionListResponse:
        wallet = await self._get_or_create_wallet(user_id)
        txns, total = await self.wallet_repo.list_transactions(wallet.id, skip, limit)
        return TransactionListResponse(
            items=[TransactionResponse.model_validate(t) for t in txns],
            total=total,
        )
