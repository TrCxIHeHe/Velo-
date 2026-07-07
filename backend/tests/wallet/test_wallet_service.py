"""Unit tests for WalletService — the business-rule layer.

These bypass HTTP entirely and call the service directly against the
repository/db_session fixtures. This is the layer where the money-safety
rules live (insufficient balance, idempotency, positive-amount checks),
so it gets tested in isolation from HTTP/routing concerns.
"""
import uuid
from decimal import Decimal

import pytest

from app.exceptions import (
    DuplicateReferenceError,
    InsufficientBalanceError,
    InvalidTransactionAmountError,
    WalletNotFoundError,
)
from app.wallet.repository import WalletRepository
from app.wallet.service import WalletService


@pytest.fixture
def wallet_service(db_session):
    return WalletService(WalletRepository(db_session))


async def test_get_wallet_auto_creates_with_zero_balance(wallet_service, user_id):
    wallet = await wallet_service.get_wallet(user_id)
    assert wallet.user_id == user_id
    assert wallet.balance == Decimal("0")
    assert wallet.currency == "INR"


async def test_credit_increases_balance(wallet_service, user_id):
    await wallet_service.credit(user_id, Decimal("500"), reference_id="topup_1")
    wallet = await wallet_service.get_wallet(user_id)
    assert wallet.balance == Decimal("500")


async def test_debit_decreases_balance(wallet_service, user_id):
    await wallet_service.credit(user_id, Decimal("500"), reference_id="topup_1")
    await wallet_service.debit(user_id, Decimal("120"), reference_id="ride_1")
    wallet = await wallet_service.get_wallet(user_id)
    assert wallet.balance == Decimal("380")


async def test_refund_increases_balance(wallet_service, user_id):
    await wallet_service.credit(user_id, Decimal("500"), reference_id="topup_1")
    await wallet_service.debit(user_id, Decimal("100"), reference_id="ride_1")
    await wallet_service.refund(user_id, Decimal("100"), reference_id="refund_ride_1")
    wallet = await wallet_service.get_wallet(user_id)
    assert wallet.balance == Decimal("500")


async def test_debit_raises_wallet_not_found_when_no_wallet_ever_created(wallet_service, user_id):
    # debit() (unlike credit/refund) does NOT auto-create a wallet, because
    # a debit against a wallet that has never received a rupee is almost
    # certainly a bug upstream (e.g. a ride ending for a user who never
    # topped up) rather than a legitimate zero-balance debit attempt.
    with pytest.raises(WalletNotFoundError):
        await wallet_service.debit(user_id, Decimal("10"), reference_id="ride_x")


async def test_debit_raises_insufficient_balance(wallet_service, user_id):
    await wallet_service.credit(user_id, Decimal("50"), reference_id="topup_1")
    with pytest.raises(InsufficientBalanceError):
        await wallet_service.debit(user_id, Decimal("100"), reference_id="ride_1")
    # Balance must be unaffected by the failed debit.
    wallet = await wallet_service.get_wallet(user_id)
    assert wallet.balance == Decimal("50")


async def test_debit_exact_balance_succeeds(wallet_service, user_id):
    # Boundary case: balance == amount should succeed (">=", not ">").
    await wallet_service.credit(user_id, Decimal("50"), reference_id="topup_1")
    await wallet_service.debit(user_id, Decimal("50"), reference_id="ride_1")
    wallet = await wallet_service.get_wallet(user_id)
    assert wallet.balance == Decimal("0")


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-10")])
async def test_zero_or_negative_amount_rejected(wallet_service, user_id, amount):
    with pytest.raises(InvalidTransactionAmountError):
        await wallet_service.credit(user_id, amount, reference_id="bad")


async def test_duplicate_reference_id_rejected_on_credit(wallet_service, user_id):
    # Simulates a client retrying a recharge request after a network
    # timeout: the same Razorpay payment id must not be credited twice.
    await wallet_service.credit(user_id, Decimal("500"), reference_id="razorpay_pay_1")
    with pytest.raises(DuplicateReferenceError):
        await wallet_service.credit(user_id, Decimal("500"), reference_id="razorpay_pay_1")
    wallet = await wallet_service.get_wallet(user_id)
    assert wallet.balance == Decimal("500")  # only credited once


async def test_duplicate_reference_id_rejected_on_debit(wallet_service, user_id):
    await wallet_service.credit(user_id, Decimal("500"), reference_id="topup_1")
    await wallet_service.debit(user_id, Decimal("30"), reference_id="ride_1")
    with pytest.raises(DuplicateReferenceError):
        await wallet_service.debit(user_id, Decimal("30"), reference_id="ride_1")
    wallet = await wallet_service.get_wallet(user_id)
    assert wallet.balance == Decimal("470")  # only debited once


async def test_same_reference_id_different_wallets_is_allowed(wallet_service):
    # Idempotency is scoped per-wallet, not global — two different users
    # topping up in the same Razorpay batch settlement could coincidentally
    # share an external reference in a bad integration; this test documents
    # that our implementation trusts reference_id uniqueness only within
    # a single wallet's own ledger.
    user_a, user_b = uuid.uuid4(), uuid.uuid4()
    await wallet_service.credit(user_a, Decimal("100"), reference_id="shared_ref")
    await wallet_service.credit(user_b, Decimal("100"), reference_id="shared_ref")
    wallet_a = await wallet_service.get_wallet(user_a)
    wallet_b = await wallet_service.get_wallet(user_b)
    assert wallet_a.balance == Decimal("100")
    assert wallet_b.balance == Decimal("100")


async def test_transaction_history_ordering(wallet_service, user_id):
    await wallet_service.credit(user_id, Decimal("100"), reference_id="r1")
    await wallet_service.credit(user_id, Decimal("50"), reference_id="r2")
    txns = await wallet_service.get_transactions(user_id)
    # Most recent first.
    assert txns[0].reference_id == "r2"
    assert txns[1].reference_id == "r1"


async def test_wallet_isolated_per_user(wallet_service, user_id):
    other_user = uuid.uuid4()
    await wallet_service.credit(user_id, Decimal("100"), reference_id="r1")
    other_wallet = await wallet_service.get_wallet(other_user)
    assert other_wallet.balance == Decimal("0")
