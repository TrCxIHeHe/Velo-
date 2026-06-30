# Track A Phase 1 — Authentication Service

FastAPI backend implementing Firebase phone-auth login, JWT access tokens,
and rotating refresh tokens with reuse detection.

Status: all 32 tests passing. Flutter client not yet started (per approved
sequencing: backend first, Flutter second).

---

## What's implemented

- `POST /api/v1/auth/login` — exchange Firebase ID token for access + refresh token pair
- `POST /api/v1/auth/refresh` — rotate refresh token, get new access + refresh pair
- `POST /api/v1/auth/logout` — revoke a refresh token (idempotent)
- `GET /api/v1/auth/me` — get authenticated user profile
- `PATCH /api/v1/auth/me` — update display name
- `GET /api/v1/health` — liveness probe

Security features per the approved design:
- Phone number is extracted from the verified Firebase token claim only — never accepted as client input.
- Refresh tokens are opaque random strings; only their SHA-256 hash is stored.
- Refresh token rotation with `family_id` tracking: if a previously-rotated (revoked) token is presented again, the entire token family is revoked, forcing re-login. This catches token-theft replay attacks.
- Standard `{success, data}` / `{success: false, error: {code, message}}` response envelope on every endpoint.

---

## Project structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app, health check, exception handlers
│   ├── config.py            # Settings (env vars)
│   ├── database.py          # Async SQLAlchemy engine/session
│   ├── auth/
│   │   ├── router.py        # 5 auth endpoints
│   │   ├── service.py       # Business logic (login/refresh/logout/profile)
│   │   ├── repository.py    # DB access only
│   │   ├── schemas.py       # Pydantic request/response models
│   │   └── dependencies.py  # DI wiring + current_user guard
│   ├── core/
│   │   ├── jwt.py           # Access token encode/decode
│   │   ├── firebase.py      # Firebase Admin SDK wrapper
│   │   ├── security.py      # Token generation + hashing
│   │   ├── exceptions.py    # Typed app exceptions → error codes
│   │   └── response.py      # success_response / error_response helpers
│   └── models/
│       ├── user.py
│       └── refresh_token.py # includes family_id, token_hash index
├── migrations/
│   └── versions/0001_initial_auth.py
├── tests/
│   ├── conftest.py          # in-memory SQLite + mocked Firebase
│   ├── auth/test_router.py  # 24 integration tests
│   └── core/                # 14 unit tests (JWT, hashing)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Setup

### 1. Requirements

- Python 3.12
- Docker + Docker Compose (recommended), or a local PostgreSQL 16 instance
- A Firebase project with Phone Authentication enabled, and a service account JSON key

### 2. Get a Firebase service account key

Firebase Console → Project Settings → Service Accounts → Generate new private key.
Save the downloaded file as `firebase-service-account.json` in the `backend/` folder
(it's gitignored — never commit it).

### 3. Configure environment

```bash
cd backend
cp .env.example .env
```

Edit `.env`:
- `JWT_SECRET` — replace with a real random 256-bit secret (`openssl rand -hex 32`)
- `FIREBASE_PROJECT_ID` — your Firebase project ID
- `FIREBASE_SERVICE_ACCOUNT_PATH` — leave as `./firebase-service-account.json` if you placed it as above
- `DATABASE_URL` — leave as-is if using docker-compose; otherwise point at your local Postgres

---

## Running with Docker (recommended)

```bash
cd backend
docker compose up --build
```

This starts Postgres and the API together. The API will be at `http://localhost:8000`.

Run migrations (from a second terminal, or after the containers are up):

```bash
docker compose exec api alembic upgrade head
```

Check it's alive:

```bash
curl http://localhost:8000/api/v1/health
# {"success":true,"data":{"status":"ok"}}
```

Interactive API docs: `http://localhost:8000/docs`

---

## Running locally without Docker

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
```

Start a local Postgres (or adjust `DATABASE_URL` in `.env` to point at one you already have), then:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

API will be at `http://localhost:8000`.

---

## Running tests

Tests use an in-memory SQLite database and a mocked Firebase service —
no real database, Docker, or Firebase project needed to run them.

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests/ -v
```

Expected: **32 passed**.

Test breakdown:
- `tests/core/test_jwt.py` — 7 tests: token creation, decoding, tamper detection, expiry, wrong-type rejection
- `tests/core/test_security.py` — 7 tests: token generation uniqueness, SHA-256 hashing properties
- `tests/auth/test_router.py` — 18 tests: full HTTP request/response cycle for every endpoint, including the reuse-detection attack scenario

---

## Manual smoke test (without a real Firebase token)

The login endpoint requires a real Firebase ID token in production, since `FirebaseService`
calls the actual Firebase Admin SDK. For local manual testing without a frontend, you have two options:

1. **Use the Firebase Auth REST API** to sign in a test phone number (Firebase emulator suite is recommended for this — see Firebase docs for `firebase emulators:start --only auth`), then pass the resulting ID token to `/api/v1/auth/login`.
2. **Temporarily monkeypatch** `FirebaseService.verify_id_token` in a throwaway script for manual exploration — do not do this against the real running server.

Example call once you have a real token:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"firebase_id_token": "<token>"}'
```

---

## Database migrations

Initial migration (`0001_initial_auth.py`) creates `users` and `refresh_tokens`
with all approved indexes, including the amendment indexes:
`idx_refresh_tokens_hash` and `idx_refresh_tokens_family`.

To create a new migration after changing models:

```bash
alembic revision --autogenerate -m "description of change"
alembic upgrade head
```

To roll back:

```bash
alembic downgrade -1
```

---

## Error codes reference

| Code | HTTP | Meaning |
|---|---|---|
| `AUTH_INVALID_FIREBASE_TOKEN` | 401 | Firebase token invalid/expired |
| `AUTH_MISSING_PHONE` | 400 | Firebase token has no phone_number claim |
| `AUTH_INVALID_TOKEN` | 401 | JWT access token invalid |
| `AUTH_TOKEN_EXPIRED` | 401 | JWT access token expired |
| `AUTH_REFRESH_INVALID` | 401 | Refresh token not found |
| `AUTH_REFRESH_EXPIRED` | 401 | Refresh token past expiry |
| `AUTH_REFRESH_REUSE` | 401 | Revoked refresh token reused — entire session family revoked |
| `AUTH_USER_DEACTIVATED` | 403 | `is_active = false` on the user |
| `AUTH_FORBIDDEN` | 403 | Role check failed |
| `AUTH_USER_NOT_FOUND` | 404 | User lookup failed |

---

## What's next (not in this scope)

Per the approved plan, Flutter Login/Onboarding starts only after this backend
is reviewed and merged. Out of scope for this phase: Ride Service, Wallet
Service, Dock Service, device-binding on refresh tokens, audit logging,
refresh-token cleanup job.
