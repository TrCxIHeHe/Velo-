"""Tests for the new Admin Dashboard aggregate endpoints (Phase 5).

Verifies: (1) the dev role gate actually blocks non-admins, and (2) the
figures returned match what wallet/dock operations actually produced —
i.e. the dashboard is reading real ledger/slot data, not placeholders.
"""


async def test_admin_endpoints_require_admin_role(client, auth_headers):
    # auth_headers has a valid user id but no X-Debug-Role: ADMIN
    resp = await client.get("/api/v1/admin/dashboard", headers=auth_headers)
    assert resp.status_code == 403


async def test_admin_endpoints_reject_missing_auth_entirely(client):
    resp = await client.get("/api/v1/admin/dashboard")
    assert resp.status_code == 401


async def test_dashboard_reflects_real_wallet_and_dock_activity(client, admin_headers, auth_headers):
    # Create some real activity as a normal user first.
    await client.post("/api/v1/wallet/credit", headers=auth_headers, json={"amount": 500, "reference_id": "t1"})
    await client.post("/api/v1/wallet/debit", headers=auth_headers, json={"amount": 100, "reference_id": "r1"})

    dock_resp = await client.post(
        "/api/v1/docks", headers=auth_headers, json={"name": "Dock A", "latitude": 1, "longitude": 1, "total_slots": 2}
    )
    dock_id = dock_resp.json()["data"]["id"]
    await client.post(
        f"/api/v1/docks/{dock_id}/assign", headers=auth_headers, json={"vehicle_id": "11111111-1111-1111-1111-111111111111"}
    )

    resp = await client.get("/api/v1/admin/dashboard", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert float(data["revenue"]["total_recharged"]) == 500.0
    assert float(data["revenue"]["total_spent"]) == 100.0
    assert float(data["revenue"]["net_platform_balance_held"]) == 400.0

    assert data["fleet"]["total_docks"] == 1
    assert data["fleet"]["total_slots"] == 2
    assert data["fleet"]["occupied_slots"] == 1
    assert data["fleet"]["available_slots"] == 1
    assert data["fleet"]["utilization_pct"] == 50.0

    assert data["users"]["total_wallets"] == 1
