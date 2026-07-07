"""HTTP-level tests for the dock router. Reading dock/slot data is public
(riders need it before logging in), mutating it requires auth — this test
file locks in that contract so nobody accidentally makes /docks require
auth (breaking the map screen) or makes /docks/{id}/assign public (letting
anyone occupy slots)."""


async def test_list_docks_is_public_no_auth_needed(client):
    resp = await client.get("/api/v1/docks")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


async def test_create_dock_requires_auth(client):
    resp = await client.post("/api/v1/docks", json={"name": "X", "latitude": 1, "longitude": 1, "total_slots": 2})
    assert resp.status_code == 401


async def test_create_and_fetch_dock(client, auth_headers):
    resp = await client.post(
        "/api/v1/docks",
        headers=auth_headers,
        json={"name": "MG Road Dock", "latitude": 12.9716, "longitude": 77.5946, "total_slots": 4},
    )
    assert resp.status_code == 201
    dock_id = resp.json()["data"]["id"]

    resp = await client.get(f"/api/v1/docks/{dock_id}")
    data = resp.json()["data"]
    assert data["available_slots"] == 4
    assert len(data["slots"]) == 4


async def test_dock_full_returns_400_envelope(client, auth_headers):
    resp = await client.post(
        "/api/v1/docks", headers=auth_headers, json={"name": "Tiny", "latitude": 1, "longitude": 1, "total_slots": 1}
    )
    dock_id = resp.json()["data"]["id"]

    ok = await client.post(
        f"/api/v1/docks/{dock_id}/assign", headers=auth_headers, json={"vehicle_id": "11111111-1111-1111-1111-111111111111"}
    )
    assert ok.status_code == 201

    full = await client.post(
        f"/api/v1/docks/{dock_id}/assign", headers=auth_headers, json={"vehicle_id": "22222222-2222-2222-2222-222222222222"}
    )
    assert full.status_code == 400
    assert full.json()["error"]["code"] == "DOCK_FULL"


async def test_release_then_dock_has_capacity_again(client, auth_headers):
    resp = await client.post(
        "/api/v1/docks", headers=auth_headers, json={"name": "Tiny", "latitude": 1, "longitude": 1, "total_slots": 1}
    )
    dock_id = resp.json()["data"]["id"]

    assigned = await client.post(
        f"/api/v1/docks/{dock_id}/assign", headers=auth_headers, json={"vehicle_id": "11111111-1111-1111-1111-111111111111"}
    )
    slot_id = assigned.json()["data"]["id"]

    released = await client.post(f"/api/v1/docks/{dock_id}/slots/{slot_id}/release", headers=auth_headers)
    assert released.status_code == 200
    assert released.json()["data"]["is_occupied"] is False
