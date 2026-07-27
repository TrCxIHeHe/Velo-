import hashlib
import hmac
import json
import uuid

import pytest

from app.main import app
from app.payments.gateway import RazorpayGateway, get_razorpay_gateway

WEBHOOK_SECRET = "whsec_router_test"


@pytest.fixture
def fake_gateway():
    gateway = RazorpayGateway(key_id="", key_secret="", webhook_secret=WEBHOOK_SECRET)
    app.dependency_overrides[get_razorpay_gateway] = lambda: gateway
    yield gateway
    app.dependency_overrides.pop(get_razorpay_gateway, None)


@pytest.mark.asyncio
async def test_create_order_requires_auth(client, fake_gateway):
    resp = await client.post("/api/v1/payments/orders", json={"amount": 100})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_order_without_keys_returns_503(client, auth_headers, fake_gateway):
    resp = await client.post("/api/v1/payments/orders", json={"amount": 100}, headers=auth_headers)
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "PAYMENT_GATEWAY_NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_webhook_with_bad_signature_returns_400(client, fake_gateway):
    resp = await client.post(
        "/api/v1/payments/webhook",
        content=b'{"event": "payment.captured"}',
        headers={"X-Razorpay-Signature": "garbage"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_webhook_credits_wallet_end_to_end(client, auth_headers, fake_gateway):
    # Discover the authenticated user's id via /auth/me so the webhook's
    # notes.user_id matches a real user.
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["data"]["id"]

    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_router_test_1",
                    "amount": 30000,  # ₹300
                    "notes": {"user_id": user_id},
                }
            }
        },
    }
    body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()

    resp = await client.post(
        "/api/v1/payments/webhook", content=body, headers={"X-Razorpay-Signature": signature}
    )
    assert resp.status_code == 200

    balance_resp = await client.get("/api/v1/wallet", headers=auth_headers)
    assert balance_resp.json()["data"]["balance"] == 300.0
