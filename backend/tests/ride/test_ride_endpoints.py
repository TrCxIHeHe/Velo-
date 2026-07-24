"""Smoke tests for ride endpoints — minimal, no Firebase."""
import pytest


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_ride_token_requires_auth(client):
    resp = await client.post("/api/v1/rides/token", json={"dock_id": "00000000-0000-0000-0000-000000000001"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_docks_requires_auth(client):
    resp = await client.get("/api/v1/docks")
    assert resp.status_code == 401
