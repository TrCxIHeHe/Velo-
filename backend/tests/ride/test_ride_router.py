import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dock import Dock
from app.models.vehicle import Vehicle

V1 = "/api/v1"


async def _seed_dock_and_vehicle(db_session: AsyncSession, battery=85):
    dock = Dock(name="Test Dock", latitude=1.0, longitude=1.0, total_slots=4, status="ACTIVE")
    db_session.add(dock)
    await db_session.flush()
    vehicle = Vehicle(qr_code=f"qr-{uuid.uuid4()}", status="AVAILABLE", battery_pct=battery, dock_id=dock.id)
    db_session.add(vehicle)
    await db_session.flush()
    await db_session.commit()
    return dock, vehicle


class TestRequestRide:
    async def test_no_auth_returns_401(self, client: AsyncClient):
        response = await client.post(f"{V1}/ride/request")
        assert response.status_code == 401

    async def test_no_vehicle_returns_409(self, client: AsyncClient, auth_headers):
        response = await client.post(f"{V1}/ride/request", headers=auth_headers)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "VEHICLE_UNAVAILABLE"

    async def test_assigns_vehicle_returns_201(self, client: AsyncClient, auth_headers, db_session):
        await _seed_dock_and_vehicle(db_session)
        response = await client.post(f"{V1}/ride/request", headers=auth_headers)
        assert response.status_code == 201
        assert response.json()["data"]["status"] == "ASSIGNED"


class TestFullRideFlow:
    async def test_request_token_validate_unlock(self, client: AsyncClient, auth_headers, db_session):
        dock, vehicle = await _seed_dock_and_vehicle(db_session)

        r1 = await client.post(f"{V1}/ride/request", headers=auth_headers)
        ride_id = r1.json()["data"]["id"]

        r2 = await client.post(f"{V1}/ride/token", headers=auth_headers)
        assert r2.status_code == 201
        ride_token = r2.json()["data"]["ride_token"]

        r3 = await client.post(f"{V1}/docks/{dock.id}/validate", json={"ride_token": ride_token})
        assert r3.status_code == 200
        assert r3.json()["data"]["status"] == "UNLOCK_PENDING"

        r4 = await client.post(f"{V1}/docks/{dock.id}/unlock", json={"ride_id": ride_id})
        assert r4.status_code == 200
        body = r4.json()["data"]
        assert body["status"] == "ACTIVE"
        assert body["vehicle_id"] == str(vehicle.id)

        r5 = await client.get(f"{V1}/ride/status/{ride_id}", headers=auth_headers)
        assert r5.json()["data"]["status"] == "ACTIVE"

    async def test_reused_token_rejected_at_dock(self, client: AsyncClient, auth_headers, db_session):
        dock, _ = await _seed_dock_and_vehicle(db_session)
        await client.post(f"{V1}/ride/request", headers=auth_headers)
        token = (await client.post(f"{V1}/ride/token", headers=auth_headers)).json()["data"]["ride_token"]

        await client.post(f"{V1}/docks/{dock.id}/validate", json={"ride_token": token})
        r2 = await client.post(f"{V1}/docks/{dock.id}/validate", json={"ride_token": token})
        assert r2.status_code == 409
        assert r2.json()["error"]["code"] == "RIDE_TOKEN_REUSED"

    async def test_unlock_before_validate_rejected(self, client: AsyncClient, auth_headers, db_session):
        dock, _ = await _seed_dock_and_vehicle(db_session)
        r1 = await client.post(f"{V1}/ride/request", headers=auth_headers)
        ride_id = r1.json()["data"]["id"]

        r2 = await client.post(f"{V1}/docks/{dock.id}/unlock", json={"ride_id": ride_id})
        assert r2.status_code == 409
        assert r2.json()["error"]["code"] == "RIDE_INVALID_STATE"

    async def test_token_without_active_ride_rejected(self, client: AsyncClient, auth_headers):
        response = await client.post(f"{V1}/ride/token", headers=auth_headers)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "RIDE_INVALID_STATE"