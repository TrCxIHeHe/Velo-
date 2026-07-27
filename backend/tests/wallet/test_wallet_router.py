"""
Router-level tests for the wallet module.

All wallet endpoints require a valid Bearer token.
"""
import pytest


# ── Auth guard ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_wallet_requires_auth(client):
    resp = await client.get("/api/v1/wallet")
    assert resp.status_code == 401


# ── Balance ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_wallet_creates_and_returns_zero_balance(client, auth_headers):
    resp = await client.get("/api/v1/wallet", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert float(body["data"]["balance"]) == 0.0
    assert body["data"]["currency"] == "INR"


# ── Top-up ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_topup_increases_balance(client, auth_headers):
    topup_resp = await client.post(
        "/api/v1/wallet/topup",
        headers=auth_headers,
        json={"amount": 500, "reference_id": "router-test-topup-1"},
    )
    assert topup_resp.status_code == 200
    assert topup_resp.json()["success"] is True

    balance_resp = await client.get("/api/v1/wallet", headers=auth_headers)
    assert float(balance_resp.json()["data"]["balance"]) >= 500.0


@pytest.mark.asyncio
async def test_topup_rejects_zero_amount(client, auth_headers):
    """Pydantic Field(gt=0) should reject this with a 422."""
    resp = await client.post(
        "/api/v1/wallet/topup",
        headers=auth_headers,
        json={"amount": 0},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_topup_idempotent_on_same_reference(client, auth_headers):
    """Second call with same reference_id must return 409."""
    ref = "router-idempotent-ref-99"
    first = await client.post(
        "/api/v1/wallet/topup",
        headers=auth_headers,
        json={"amount": 10, "reference_id": ref},
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/v1/wallet/topup",
        headers=auth_headers,
        json={"amount": 10, "reference_id": ref},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "WALLET_DUPLICATE_REFERENCE"


# ── Transactions ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_transactions_list_reflects_topups(client, auth_headers):
    await client.post(
        "/api/v1/wallet/topup",
        headers=auth_headers,
        json={"amount": 100, "reference_id": "txn-list-test-1"},
    )
    resp = await client.get("/api/v1/wallet/transactions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] >= 1
    assert any(t["type"] == "CREDIT" for t in data["items"])


# ── Wallet isolation ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_wallets_are_isolated_between_users(client, auth_headers, admin_headers):
    """
    Top up the regular user's wallet; verify the admin user's balance is unaffected.
    Uses two different committed users so their wallets are truly separate.
    """
    await client.post(
        "/api/v1/wallet/topup",
        headers=auth_headers,
        json={"amount": 200, "reference_id": "isolation-test-user"},
    )

    admin_wallet_resp = await client.get("/api/v1/wallet", headers=admin_headers)
    assert admin_wallet_resp.status_code == 200
    # Admin's wallet should be 0 — they never topped up
    assert float(admin_wallet_resp.json()["data"]["balance"]) == 0.0


# ── Admin adjust ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_adjust_requires_admin_role(client, auth_headers):
    import uuid
    resp = await client.post(
        "/api/v1/wallet/admin/adjust",
        headers=auth_headers,
        json={"user_id": str(uuid.uuid4()), "amount": 50},
    )
    assert resp.status_code == 403
