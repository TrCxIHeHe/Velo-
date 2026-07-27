"""
Smoke tests for ride-related endpoints.

Full ride lifecycle tests (token → confirm → end) require real wallet balance
and Firebase auth — those live in integration tests. These tests verify the
HTTP-layer contracts: auth guards, response envelopes, and schema validation.
"""
import pytest


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── Dock endpoints (public) ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_docks_is_public(client):
    """GET /docks must be reachable without auth — Flutter map loads before login."""
    resp = await client.get("/api/v1/docks")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_get_nonexistent_dock_returns_404(client):
    resp = await client.get("/api/v1/docks/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ── Ride endpoints (require auth) ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ride_token_requires_auth(client):
    resp = await client.post(
        "/api/v1/rides/token",
        json={"dock_id": "00000000-0000-0000-0000-000000000001"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_ride_history_requires_auth(client):
    resp = await client.get("/api/v1/rides")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_active_ride_requires_auth(client):
    resp = await client.get("/api/v1/rides/active")
    assert resp.status_code == 401
