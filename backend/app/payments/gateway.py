"""Thin wrapper around the Razorpay SDK.

Isolated behind this class so PaymentService can be unit tested with a fake
gateway instead of hitting the real Razorpay API or needing real keys.
"""
import hashlib
import hmac
from functools import lru_cache

import razorpay

from app.config import settings
from app.core.exceptions import PaymentGatewayNotConfiguredError


class RazorpayGateway:
    def __init__(self, key_id: str, key_secret: str, webhook_secret: str) -> None:
        self.key_id = key_id
        self.key_secret = key_secret
        self.webhook_secret = webhook_secret
        self._client: razorpay.Client | None = None

    def _require_configured(self) -> None:
        if not self.key_id or not self.key_secret:
            raise PaymentGatewayNotConfiguredError()

    @property
    def client(self) -> razorpay.Client:
        self._require_configured()
        if self._client is None:
            self._client = razorpay.Client(auth=(self.key_id, self.key_secret))
        return self._client

    def create_order(self, amount_rupees: float, receipt: str, notes: dict) -> dict:
        """Amount is converted to paise (Razorpay's smallest currency unit)."""
        amount_paise = int(round(amount_rupees * 100))
        return self.client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt,
            "notes": notes,
        })

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        """HMAC-SHA256(webhook_secret, raw_body) must equal the
        X-Razorpay-Signature header, hex-encoded. Does NOT require a
        configured key_id/key_secret — only the webhook secret, so webhooks
        can be verified even before order-creation keys are set up."""
        if not self.webhook_secret:
            raise PaymentGatewayNotConfiguredError()
        expected = hmac.new(
            self.webhook_secret.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)


@lru_cache(maxsize=1)
def get_razorpay_gateway() -> RazorpayGateway:
    return RazorpayGateway(
        settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET, settings.RAZORPAY_WEBHOOK_SECRET
    )
