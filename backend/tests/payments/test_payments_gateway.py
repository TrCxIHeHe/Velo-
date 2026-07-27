import hashlib
import hmac

import pytest

from app.core.exceptions import PaymentGatewayNotConfiguredError
from app.payments.gateway import RazorpayGateway


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_verify_webhook_signature_accepts_valid_signature():
    gateway = RazorpayGateway(key_id="", key_secret="", webhook_secret="whsec_test")
    body = b'{"event": "payment.captured"}'
    signature = _sign("whsec_test", body)
    assert gateway.verify_webhook_signature(body, signature) is True


def test_verify_webhook_signature_rejects_tampered_body():
    gateway = RazorpayGateway(key_id="", key_secret="", webhook_secret="whsec_test")
    body = b'{"event": "payment.captured"}'
    signature = _sign("whsec_test", body)
    tampered = b'{"event": "payment.captured", "extra": "injected"}'
    assert gateway.verify_webhook_signature(tampered, signature) is False


def test_verify_webhook_signature_rejects_wrong_secret():
    gateway = RazorpayGateway(key_id="", key_secret="", webhook_secret="whsec_test")
    body = b'{"event": "payment.captured"}'
    signature = _sign("wrong_secret", body)
    assert gateway.verify_webhook_signature(body, signature) is False


def test_verify_webhook_signature_requires_configured_secret():
    gateway = RazorpayGateway(key_id="", key_secret="", webhook_secret="")
    with pytest.raises(PaymentGatewayNotConfiguredError):
        gateway.verify_webhook_signature(b"{}", "any-signature")


def test_create_order_requires_configured_keys():
    gateway = RazorpayGateway(key_id="", key_secret="", webhook_secret="")
    with pytest.raises(PaymentGatewayNotConfiguredError):
        gateway.create_order(100.0, receipt="r1", notes={})
