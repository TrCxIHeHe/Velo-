"""
Router-level tests for the admin module.

Tests hit the actual HTTP layer via AsyncClient backed by an in-memory
SQLite database.  auth_headers / admin_headers fixtures are in conftest.py.
"""
import pytest


# ── Auth guard tests ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_endpoints_reject_unauthenticated(client):
    """Every admin endpoint must return 401 when no token is supplied."""
    resp = await client.get("/api/v1/admin/users")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_endpoints_reject_non_admin_user(client, auth_headers):
    """A valid USER-role JWT must be forbidden from admin endpoints."""
    resp = await client.get("/api/v1/admin/users", headers=auth_headers)
    assert resp.status_code == 403


# ── User management ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_can_list_users(client, admin_headers):
    resp = await client.get("/api/v1/admin/users", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "items" in body["data"]
    assert isinstance(body["data"]["total"], int)


@pytest.mark.asyncio
async def test_admin_can_promote_user_to_admin(client, admin_headers, auth_headers):
    """Fetch the regular user's ID, then promote them, then verify the role."""
    # Get list to find the regular user
    users_resp = await client.get("/api/v1/admin/users", headers=admin_headers)
    users = users_resp.json()["data"]["items"]
    # Find the USER-role entry (not the admin itself)
    regular = next((u for u in users if u["role"] == "USER"), None)
    assert regular is not None, "Expected at least one USER-role user in the list"

    user_id = regular["id"]
    patch_resp = await client.patch(
        f"/api/v1/admin/users/{user_id}/role",
        headers=admin_headers,
        json={"role": "ADMIN"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["data"]["role"] == "ADMIN"


@pytest.mark.asyncio
async def test_admin_can_deactivate_user(client, admin_headers, auth_headers):
    users_resp = await client.get("/api/v1/admin/users", headers=admin_headers)
    users = users_resp.json()["data"]["items"]
    regular = next((u for u in users if u["role"] == "USER"), None)
    if regular is None:
        pytest.skip("No USER-role user found; skipping deactivation test")

    user_id = regular["id"]
    resp = await client.patch(
        f"/api/v1/admin/users/{user_id}/active",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is False


# ── Audit log ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_can_read_audit_log(client, admin_headers):
    resp = await client.get("/api/v1/admin/audit-logs", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "items" in body["data"]


# ── Rides overview ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_can_list_all_rides(client, admin_headers):
    resp = await client.get("/api/v1/admin/rides", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "items" in body["data"]
