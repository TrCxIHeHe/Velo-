import hashlib
import hmac
import json
import uuid

import pytest

from app.audit.repository import AuditLogRepository
from app.core.exceptions import InvalidWebhookSignatureError
from app.payments.gateway import RazorpayGateway
from app.payments.service import PaymentService
from app.wallet.repository import WalletRepository
from app.wallet.service import WalletService

WEBHOOK_SECRET = "whsec_test"


def _gateway() -> RazorpayGateway:
    return RazorpayGateway(key_id="", key_secret="", webhook_secret=WEBHOOK_SECRET)


def _signed_event(payload: dict) -> tuple[bytes, str]:
    body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return body, signature


def _captured_event(user_id: uuid.UUID, payment_id: str, amount_paise: int) -> dict:
    return {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "amount": amount_paise,
                    "notes": {"user_id": str(user_id)},
                }
            }
        },
    }


@pytest.mark.asyncio
async def test_webhook_credits_wallet_on_payment_captured(db_session):
    wallet_service = WalletService(WalletRepository(db_session), AuditLogRepository(db_session))
    svc = PaymentService(_gateway(), wallet_service)
    user_id = uuid.uuid4()

    body, signature = _signed_event(_captured_event(user_id, "pay_abc123", 50000))  # ₹500.00
    await svc.handle_webhook(body, signature)

    wallet = await wallet_service.get_balance(user_id)
    assert wallet.balance == 500.0


@pytest.mark.asyncio
async def test_webhook_rejects_invalid_signature(db_session):
    wallet_service = WalletService(WalletRepository(db_session))
    svc = PaymentService(_gateway(), wallet_service)
    body, _ = _signed_event(_captured_event(uuid.uuid4(), "pay_bad", 1000))

    with pytest.raises(InvalidWebhookSignatureError):
        await svc.handle_webhook(body, "not-the-real-signature")


@pytest.mark.asyncio
async def test_webhook_ignores_non_creditable_events(db_session):
    wallet_service = WalletService(WalletRepository(db_session))
    svc = PaymentService(_gateway(), wallet_service)
    user_id = uuid.uuid4()

    body, signature = _signed_event({
        "event": "payment.failed",
        "payload": {"payment": {"entity": {"id": "pay_x", "amount": 1000, "notes": {"user_id": str(user_id)}}}},
    })
    await svc.handle_webhook(body, signature)

    wallet = await wallet_service.get_balance(user_id)
    assert wallet.balance == 0.0


@pytest.mark.asyncio
async def test_webhook_retry_does_not_double_credit(db_session):
    """Razorpay retries a webhook on any non-2xx response — the same
    payment_id arriving twice must credit the wallet exactly once."""
    wallet_service = WalletService(WalletRepository(db_session), AuditLogRepository(db_session))
    svc = PaymentService(_gateway(), wallet_service)
    user_id = uuid.uuid4()

    body, signature = _signed_event(_captured_event(user_id, "pay_retry_1", 20000))  # ₹200
    await svc.handle_webhook(body, signature)
    await svc.handle_webhook(body, signature)  # retry — same payment_id

    wallet = await wallet_service.get_balance(user_id)
    assert wallet.balance == 200.0
