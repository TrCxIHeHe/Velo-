"""
Integration tests for auth router endpoints.
Firebase verification is mocked. Database is in-memory SQLite.
All tests exercise the full FastAPI request/response cycle.
"""
import pytest
from httpx import AsyncClient

from tests.conftest import MOCK_PHONE, MOCK_UID


FIREBASE_TOKEN = "mock_firebase_id_token"
V1 = "/api/v1"


# ── GET /health ───────────────────────────────────────────────────────────────

class TestHealth:
    async def test_returns_200(self, client: AsyncClient):
        response = await client.get(f"{V1}/health")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["status"] == "ok"


# ── POST /auth/login ──────────────────────────────────────────────────────────

class TestLogin:
    async def test_new_user_created_and_session_returned(self, client: AsyncClient):
        response = await client.post(
            f"{V1}/auth/login", json={"firebase_id_token": FIREBASE_TOKEN}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "Bearer"
        assert data["user"]["phone_number"] == MOCK_PHONE
        assert data["user"]["role"] == "USER"

    async def test_existing_user_returns_session(self, client: AsyncClient, existing_user):
        response = await client.post(
            f"{V1}/auth/login", json={"firebase_id_token": FIREBASE_TOKEN}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["user"]["id"] == str(existing_user.id)

    async def test_invalid_firebase_token_returns_401(self, client: AsyncClient, firebase_mock):
        from app.core.exceptions import InvalidFirebaseTokenError
        firebase_mock.verify_id_token.side_effect = InvalidFirebaseTokenError()
        response = await client.post(
            f"{V1}/auth/login", json={"firebase_id_token": "bad_token"}
        )
        assert response.status_code == 401
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "AUTH_INVALID_FIREBASE_TOKEN"

    async def test_firebase_token_without_phone_returns_400(self, client: AsyncClient, firebase_mock):
        from app.core.exceptions import MissingPhoneNumberError
        firebase_mock.verify_id_token.side_effect = MissingPhoneNumberError()
        response = await client.post(
            f"{V1}/auth/login", json={"firebase_id_token": FIREBASE_TOKEN}
        )
        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "AUTH_MISSING_PHONE"

    async def test_deactivated_user_returns_403(self, client: AsyncClient, existing_user, db_session):
        existing_user.is_active = False
        db_session.add(existing_user)
        await db_session.commit()

        response = await client.post(
            f"{V1}/auth/login", json={"firebase_id_token": FIREBASE_TOKEN}
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "AUTH_USER_DEACTIVATED"


# ── POST /auth/refresh ────────────────────────────────────────────────────────

class TestRefresh:
    async def _login(self, client: AsyncClient) -> dict:
        r = await client.post(
            f"{V1}/auth/login", json={"firebase_id_token": FIREBASE_TOKEN}
        )
        return r.json()["data"]

    async def test_valid_refresh_returns_new_token_pair(self, client: AsyncClient):
        session = await self._login(client)
        response = await client.post(
            f"{V1}/auth/refresh",
            json={"refresh_token": session["refresh_token"]},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "access_token" in data
        assert "refresh_token" in data
        # New tokens must differ from original
        assert data["access_token"] != session["access_token"]
        assert data["refresh_token"] != session["refresh_token"]

    async def test_reused_old_token_revokes_family_including_new_token(self, client: AsyncClient):
        session = await self._login(client)
        old_refresh = session["refresh_token"]

        # Refresh once — get new token pair
        r1 = await client.post(
            f"{V1}/auth/refresh", json={"refresh_token": old_refresh}
        )
        new_refresh = r1.json()["data"]["refresh_token"]

        # Old (already-rotated) token must be rejected as reuse
        r2 = await client.post(
            f"{V1}/auth/refresh", json={"refresh_token": old_refresh}
        )
        assert r2.status_code == 401
        assert r2.json()["error"]["code"] == "AUTH_REFRESH_REUSE"

        # Reuse detection revokes the entire family as a security measure,
        # so the new token (same family) must now ALSO be rejected —
        # this forces the user to log in again, per the approved design.
        r3 = await client.post(
            f"{V1}/auth/refresh", json={"refresh_token": new_refresh}
        )
        assert r3.status_code == 401

    async def test_reuse_revokes_entire_family(self, client: AsyncClient):
        session = await self._login(client)
        old_refresh = session["refresh_token"]

        # Rotate once to generate a new active token in the same family
        r1 = await client.post(
            f"{V1}/auth/refresh", json={"refresh_token": old_refresh}
        )
        new_refresh = r1.json()["data"]["refresh_token"]

        # Present the old (revoked) token — triggers family revocation
        await client.post(f"{V1}/auth/refresh", json={"refresh_token": old_refresh})

        # The newest token in the same family must now also be revoked
        r_final = await client.post(
            f"{V1}/auth/refresh", json={"refresh_token": new_refresh}
        )
        assert r_final.status_code == 401

    async def test_invalid_refresh_token_returns_401(self, client: AsyncClient):
        response = await client.post(
            f"{V1}/auth/refresh", json={"refresh_token": "completely_fake_token"}
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTH_REFRESH_INVALID"


# ── POST /auth/logout ─────────────────────────────────────────────────────────

class TestLogout:
    async def _login(self, client: AsyncClient) -> dict:
        r = await client.post(
            f"{V1}/auth/login", json={"firebase_id_token": FIREBASE_TOKEN}
        )
        return r.json()["data"]

    async def test_logout_revokes_refresh_token(self, client: AsyncClient):
        session = await self._login(client)
        refresh_token = session["refresh_token"]

        r_logout = await client.post(
            f"{V1}/auth/logout", json={"refresh_token": refresh_token}
        )
        assert r_logout.status_code == 200

        # Token must now be rejected
        r_refresh = await client.post(
            f"{V1}/auth/refresh", json={"refresh_token": refresh_token}
        )
        assert r_refresh.status_code == 401

    async def test_logout_is_idempotent(self, client: AsyncClient):
        session = await self._login(client)
        refresh_token = session["refresh_token"]

        await client.post(f"{V1}/auth/logout", json={"refresh_token": refresh_token})
        r2 = await client.post(f"{V1}/auth/logout", json={"refresh_token": refresh_token})
        assert r2.status_code == 200

    async def test_logout_with_unknown_token_returns_200(self, client: AsyncClient):
        r = await client.post(
            f"{V1}/auth/logout", json={"refresh_token": "unknown_token"}
        )
        assert r.status_code == 200


# ── GET /auth/me ──────────────────────────────────────────────────────────────

class TestGetMe:
    async def _get_access_token(self, client: AsyncClient) -> str:
        r = await client.post(
            f"{V1}/auth/login", json={"firebase_id_token": FIREBASE_TOKEN}
        )
        return r.json()["data"]["access_token"]

    async def test_returns_user_profile(self, client: AsyncClient):
        access_token = await self._get_access_token(client)
        response = await client.get(
            f"{V1}/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["phone_number"] == MOCK_PHONE
        assert data["role"] == "USER"

    async def test_missing_token_returns_403(self, client: AsyncClient):
        response = await client.get(f"{V1}/auth/me")
        assert response.status_code == 401  # HTTPBearer returns 401 when Authorization header is absent

    async def test_invalid_token_returns_401(self, client: AsyncClient):
        response = await client.get(
            f"{V1}/auth/me",
            headers={"Authorization": "Bearer not_a_real_jwt"},
        )
        assert response.status_code == 401


# ── PATCH /auth/me ────────────────────────────────────────────────────────────

class TestUpdateMe:
    async def _get_access_token(self, client: AsyncClient) -> str:
        r = await client.post(
            f"{V1}/auth/login", json={"firebase_id_token": FIREBASE_TOKEN}
        )
        return r.json()["data"]["access_token"]

    async def test_updates_name(self, client: AsyncClient):
        access_token = await self._get_access_token(client)
        response = await client.patch(
            f"{V1}/auth/me",
            json={"name": "Ravi Kumar"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "Ravi Kumar"

    async def test_empty_name_rejected(self, client: AsyncClient):
        access_token = await self._get_access_token(client)
        response = await client.patch(
            f"{V1}/auth/me",
            json={"name": ""},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 422
