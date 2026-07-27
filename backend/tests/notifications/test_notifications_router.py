import pytest


@pytest.mark.asyncio
async def test_register_device_token_requires_auth(client):
    resp = await client.post("/api/v1/notifications/device-token", json={"fcm_token": "abc"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_notifications_requires_auth(client):
    resp = await client.get("/api/v1/notifications")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_register_device_token_and_list_notifications(client, auth_headers):
    resp = await client.post(
        "/api/v1/notifications/device-token", json={"fcm_token": "test-device-token"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    resp = await client.get("/api/v1/notifications", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["total"] == 0
    assert body["items"] == []
