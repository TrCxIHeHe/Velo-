# Velo Backend

FastAPI async backend for the Velo smart micromobility platform.

## Stack

- **FastAPI** + **SQLAlchemy 2 async** + **asyncpg**
- **PostgreSQL 16** — primary datastore
- **Redis** — ride-token idempotency / future rate-limiting
- **Firebase Admin** — phone-number auth (OTP)
- **Alembic** — database migrations
- **JWT (python-jose)** — access tokens (15 min) + ride tokens (30 s)

## Architecture

```
app/
├── core/          exceptions, response helpers, JWT, Firebase, Redis, security
├── models/        SQLAlchemy ORM models (user, refresh_token, dock, vehicle, ride, wallet, audit_log)
├── auth/          Login / refresh / logout / profile  (Firebase OTP → JWT)
├── ride/          Token-based ride lifecycle  (PENDING → ACTIVE → COMPLETED)
├── dock/          Dock & vehicle management
├── wallet/        INR wallet — top-up, debit, admin adjust
├── admin/         User management, audit log, all-rides view
└── audit/         Immutable audit log writer
```

## Ride Flow

```
1. POST /api/v1/rides/token   { dock_id }          → ride_token (30s JWT) + ride_id  [user app]
2. POST /api/v1/rides/confirm { ride_token, dock_id} → ride ACTIVE, vehicle assigned  [dock hardware]
3. POST /api/v1/rides/{id}/end{ dock_id }           → ride COMPLETED, fare charged    [user app]
```

## Quick Start (Docker)

```bash
cp .env.example .env
# fill in JWT_SECRET, RIDE_TOKEN_SECRET, FIREBASE_* in .env
docker compose up --build
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

## Local Dev

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

## Tests

```bash
pytest                      # all tests with coverage
pytest tests/auth/          # auth only
pytest -k test_wallet       # filter by name
```

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/auth/login` | — | Firebase OTP → tokens |
| POST | `/api/v1/auth/refresh` | — | Rotate refresh token |
| POST | `/api/v1/auth/logout` | — | Revoke refresh token |
| GET | `/api/v1/auth/me` | User | Get profile |
| PATCH | `/api/v1/auth/me` | User | Update name |
| GET | `/api/v1/docks` | User | List active docks |
| GET | `/api/v1/docks/{id}` | User | Dock detail + slots |
| POST | `/api/v1/docks` | Admin | Create dock |
| PATCH | `/api/v1/docks/{id}` | Admin | Update dock |
| POST | `/api/v1/docks/vehicles` | Admin | Add vehicle |
| PATCH | `/api/v1/docks/vehicles/{id}` | Admin | Update vehicle |
| POST | `/api/v1/rides/token` | User | Request ride token |
| POST | `/api/v1/rides/confirm` | None* | Hardware confirms unlock |
| POST | `/api/v1/rides/{id}/end` | User | End ride |
| GET | `/api/v1/rides/active` | User | Current active ride |
| GET | `/api/v1/rides` | User | Ride history |
| GET | `/api/v1/wallet` | User | Balance |
| POST | `/api/v1/wallet/topup` | User | Top up wallet |
| GET | `/api/v1/wallet/transactions` | User | Transaction history |
| POST | `/api/v1/wallet/admin/adjust` | Admin | Admin credit/debit |
| GET | `/api/v1/admin/users` | Admin | List all users |
| PATCH | `/api/v1/admin/users/{id}/role` | Admin | Set role |
| PATCH | `/api/v1/admin/users/{id}/active` | Admin | Activate/deactivate |
| GET | `/api/v1/admin/audit-logs` | Admin | Audit log |
| GET | `/api/v1/admin/rides` | Admin | All rides |

*`/rides/confirm` is authenticated by the short-lived ride token, not a user JWT.

## Fare Calculation

- ₹2/minute, minimum ₹5
- Charged at ride end from user wallet
- Ride token expires in 30 s — prevents lock-holding attacks
