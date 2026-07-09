"""HTTP-level tests for the wallet router — proves the full stack (router
-> service -> repository -> db) works end to end, including auth-header
handling and the {"success": true/false, ...} response envelope every
service in this platform must follow (see docs/api/common.md).
"""
import pytest


async def test_get_wallet_requires_auth_header(client):
    resp = await client.get("/api/v1/wallet")
    assert resp.status_code == 401


async def test_get_wallet_creates_and_returns_zero_balance(client, auth_headers):
    resp = await client.get("/api/v1/wallet", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["balance"] == "0.00" or float(body["data"]["balance"]) == 0.0


async def test_credit_then_balance_reflects_it(client, auth_headers):
    resp = await client.post(
        "/api/v1/wallet/credit", headers=auth_headers, json={"amount": 500, "reference_id": "topup_1"}
    )
    assert resp.status_code == 201
    assert resp.json()["success"] is True

    resp = await client.get("/api/v1/wallet", headers=auth_headers)
    assert float(resp.json()["data"]["balance"]) == 500.0


async def test_debit_insufficient_balance_returns_400_envelope(client, auth_headers):
    await client.post("/api/v1/wallet/credit", headers=auth_headers, json={"amount": 10, "reference_id": "t1"})
    resp = await client.post("/api/v1/wallet/debit", headers=auth_headers, json={"amount": 100, "reference_id": "r1"})
    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "WALLET_INSUFFICIENT_BALANCE"


async def test_credit_rejects_non_positive_amount_at_schema_level(client, auth_headers):
    # Pydantic's Field(gt=0) on CreditRequest should reject this before it
    # even reaches WalletService — FastAPI returns its own 422 envelope here,
    # not our custom error_response, which is expected and correct.
    resp = await client.post("/api/v1/wallet/credit", headers=auth_headers, json={"amount": 0})
    assert resp.status_code == 422


async def test_transactions_list_reflects_all_operations(client, auth_headers):
    await client.post("/api/v1/wallet/credit", headers=auth_headers, json={"amount": 500, "reference_id": "t1"})
    await client.post("/api/v1/wallet/debit", headers=auth_headers, json={"amount": 30, "reference_id": "r1"})
    resp = await client.get("/api/v1/wallet/transactions", headers=auth_headers)
    data = resp.json()["data"]
    assert len(data) == 2
    types = {t["type"] for t in data}
    assert types == {"CREDIT", "DEBIT"}


async def test_wallets_are_isolated_between_users(client, auth_headers, other_auth_headers):
    await client.post(
        "/api/v1/wallet/credit", headers=auth_headers, json={"amount": 200, "reference_id": "a1"}
    )
    resp_b = await client.get("/api/v1/wallet", headers=other_auth_headers)
    assert float(resp_b.json()["data"]["balance"]) == 0.0
