import uuid
import pytest

from app.core.exceptions import DuplicateReferenceError, InsufficientBalanceError, InvalidTransactionAmountError
from app.wallet.repository import WalletRepository
from app.wallet.service import WalletService


@pytest.mark.asyncio
async def test_get_balance_creates_wallet_on_first_access(db_session):
    svc = WalletService(WalletRepository(db_session))
    user_id = uuid.uuid4()
    wallet = await svc.get_balance(user_id)
    assert wallet.balance == 0.0
    assert wallet.currency == "INR"


@pytest.mark.asyncio
async def test_top_up_increases_balance(db_session):
    svc = WalletService(WalletRepository(db_session))
    user_id = uuid.uuid4()
    wallet = await svc.top_up(user_id, 100.0)
    assert wallet.balance == 100.0


@pytest.mark.asyncio
async def test_top_up_idempotent_with_reference(db_session):
    svc = WalletService(WalletRepository(db_session))
    user_id = uuid.uuid4()
    await svc.top_up(user_id, 50.0, reference_id="REF-001")
    with pytest.raises(DuplicateReferenceError):
        await svc.top_up(user_id, 50.0, reference_id="REF-001")


@pytest.mark.asyncio
async def test_top_up_rejects_zero(db_session):
    svc = WalletService(WalletRepository(db_session))
    with pytest.raises(InvalidTransactionAmountError):
        await svc.top_up(uuid.uuid4(), 0.0)


@pytest.mark.asyncio
async def test_debit_for_ride_reduces_balance(db_session):
    svc = WalletService(WalletRepository(db_session))
    user_id = uuid.uuid4()
    await svc.top_up(user_id, 200.0)
    await svc.debit_for_ride(user_id, 50.0, uuid.uuid4())
    wallet = await svc.get_balance(user_id)
    assert wallet.balance == 150.0


@pytest.mark.asyncio
async def test_debit_rejects_insufficient_balance(db_session):
    svc = WalletService(WalletRepository(db_session))
    user_id = uuid.uuid4()
    await svc.top_up(user_id, 10.0)
    with pytest.raises(InsufficientBalanceError):
        await svc.debit_for_ride(user_id, 100.0, uuid.uuid4())
