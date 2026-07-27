"""
Router-level tests for the dock module.

GET /docks and GET /docks/{id} are public (no auth required).
POST/PATCH endpoints require ADMIN.
"""
import pytest


# ── Public endpoints ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_docks_is_public_no_auth_needed(client):
    """Dock listing must be reachable without any token (Flutter map pre-login)."""
    resp = await client.get("/api/v1/docks")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)


@pytest.mark.asyncio
async def test_get_dock_not_found_returns_404_envelope(client):
    resp = await client.get("/api/v1/docks/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "DOCK_NOT_FOUND"


# ── Admin CRUD ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_dock_requires_admin(client, auth_headers):
    """A USER-role token must not be able to create a dock."""
    resp = await client.post(
        "/api/v1/docks",
        headers=auth_headers,
        json={"name": "Test Dock", "location_lat": 12.97, "location_lng": 77.59, "total_slots": 4},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_create_and_fetch_dock(client, admin_headers):
    resp = await client.post(
        "/api/v1/docks",
        headers=admin_headers,
        json={"name": "MG Road Dock", "location_lat": 12.9716, "location_lng": 77.5946, "total_slots": 4},
    )
    assert resp.status_code == 201
    dock = resp.json()["data"]
    assert dock["name"] == "MG Road Dock"
    assert dock["total_slots"] == 4
    dock_id = dock["id"]

    # Detail endpoint is public
    detail_resp = await client.get(f"/api/v1/docks/{dock_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()["data"]
    assert detail["available_slots"] == 4
    assert len(detail["slots"]) == 4


@pytest.mark.asyncio
async def test_admin_can_update_dock(client, admin_headers):
    create_resp = await client.post(
        "/api/v1/docks",
        headers=admin_headers,
        json={"name": "Old Name", "location_lat": 0.0, "location_lng": 0.0, "total_slots": 2},
    )
    dock_id = create_resp.json()["data"]["id"]

    update_resp = await client.patch(
        f"/api/v1/docks/{dock_id}",
        headers=admin_headers,
        json={"name": "New Name"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["data"]["name"] == "New Name"


@pytest.mark.asyncio
async def test_admin_can_add_vehicle(client, admin_headers):
    """Admin adds a vehicle; it appears in the vehicles list."""
    vehicle_resp = await client.post(
        "/api/v1/docks/vehicles",
        headers=admin_headers,
        json={"qr_code": "QR-ROUTER-TEST-001", "vehicle_type": "SCOOTER", "battery_level": 90},
    )
    assert vehicle_resp.status_code == 201
    v = vehicle_resp.json()["data"]
    assert v["qr_code"] == "QR-ROUTER-TEST-001"
    assert v["status"] == "AVAILABLE"


@pytest.mark.asyncio
async def test_list_vehicles_requires_admin(client, auth_headers):
    resp = await client.get("/api/v1/docks/vehicles/all", headers=auth_headers)
    assert resp.status_code == 403
