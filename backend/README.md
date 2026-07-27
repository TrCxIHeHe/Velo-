# Velo Backend

FastAPI modular-monolith backend for the Velo smart micromobility platform. Merged from Track A
(auth, ride token issuance) and Track B (wallet, dock/fleet, admin dashboards, audit log).

## Stack

- **FastAPI** + **SQLAlchemy 2 async** + **asyncpg**
- **PostgreSQL 16** — primary datastore
- **Firebase Admin** — phone-number auth (OTP) + Cloud Messaging (push)
- **Razorpay** — wallet top-up (order + webhook, signature-verified)
- **Alembic** — database migrations
- **JWT (python-jose)** — access tokens (15 min) + short-lived ride tokens (30 s)
- **slowapi** — per-IP rate limiting (login, ride-token, wallet/payment endpoints)
- **pytest + pytest-asyncio** — test suite runs against in-memory SQLite, zero external deps

## Structure

```
app/
├── main.py         create_app() factory, global exception handlers, router mounting
├── config.py       Settings (env-driven)
├── database.py     engine, session factory, Base
├── types.py        GUID — cross-dialect UUID type (Postgres native / SQLite CHAR(36))
├── core/           exceptions, response helpers, JWT, Firebase, security, rate limiting
├── auth/           Firebase OTP login, JWT issue/refresh/rotation, /auth/me
├── ride/           token-based ride lifecycle (PENDING → ACTIVE → COMPLETED)
├── dock/           dock/slot/vehicle CRUD and availability
├── wallet/         INR wallet — top-up, ride-fare debit, admin adjust (ledger, all audited)
├── payments/       Razorpay order creation + signature-verified webhook → wallet credit
├── notifications/  FCM device-token registration + push-and-persist notification service
├── admin/          fleet/revenue/user stats + user, audit-log, and ride management (role-gated)
├── audit/          audit log writer
└── models/         SQLAlchemy models, all exported from models/__init__.py
```

Each feature module follows repository → service → router → schemas.

## Ride flow

```
1. POST /api/v1/rides/token   { dock_id }           → ride_token (30s JWT) + ride_id   [user app]
2. POST /api/v1/rides/confirm { ride_token, dock_id} → ride ACTIVE, vehicle assigned    [dock hardware]
3. POST /api/v1/rides/{id}/end{ dock_id }            → ride COMPLETED, fare charged     [user app]
```

Fare: ₹2/minute, minimum ₹5, charged from the user's wallet at ride end. The ride token expires in
30s to prevent lock-holding. Ride start/end and low-balance events trigger a best-effort FCM push
(see `notifications/`) — a missing device token or Firebase outage never fails the ride itself.

## Wallet top-up flow

```
1. POST /api/v1/payments/orders    { amount }                → Razorpay order_id + key_id  [user app]
   (client opens Razorpay Checkout with those two values)
2. Razorpay calls POST /api/v1/payments/webhook on payment.captured, HMAC-signed
   → signature verified against RAZORPAY_WEBHOOK_SECRET → wallet credited, idempotent on payment_id
```

`/payments/orders` + the webhook credit the wallet only after Razorpay confirms the payment —
the client never controls its own balance there. **`/wallet/topup` is a separate, pre-existing
endpoint that lets any authenticated user credit their own wallet directly, with no payment
behind it at all.** That's fine for dev/testing (and is what the test suite uses) but is a real
"free money" hole if left reachable in production — gate it behind `require_role("ADMIN")` or
remove it before a real pilot with real money.

> **Update:** `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` / `RAZORPAY_WEBHOOK_SECRET` are intentionally
> left blank for now — no real Razorpay account is wired up yet. `/payments/orders` and the webhook
> will keep returning `503 PAYMENT_GATEWAY_NOT_CONFIGURED` until those are set; this is expected and
> not a bug.

## Security posture

- **Auth**: Firebase-verified phone login → 15-min JWT access tokens + 30-day single-use, rotated
  refresh tokens (reuse revokes the whole session family).
- **Rate limiting**: login (5/min), ride-token request (3/min), wallet top-up + payment order
  creation (10/min) — per-IP, active only when `ENVIRONMENT=production` (see
  `app/core/rate_limit.py` for why it's off elsewhere).
- **CORS**: origin list from `CORS_ORIGINS`; wildcard (`*`) never gets `allow_credentials=True`.
- **Security headers**: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
  `Permissions-Policy` on every response; HSTS added in production.
- **Audit log**: every wallet top-up/ride-fare-debit/admin-adjust and every admin role/active
  change is written to `audit_logs` with the acting user's id.
- **Payments**: wallet is credited only from a Razorpay webhook whose HMAC-SHA256 signature is
  verified against `RAZORPAY_WEBHOOK_SECRET`; idempotent on `payment_id` (retries don't double-credit).
- **DB-level constraints**: `wallet_transactions.amount > 0` is enforced by a CHECK constraint,
  not just service-layer validation.
- All endpoints validate input via Pydantic; every query goes through the ORM (no raw SQL).

## Local development

Requires Python 3.12 (matches CI and `backend/docker/Dockerfile`).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt
cp .env.example .env    # fill in real values — see comments in the file
alembic upgrade head
uvicorn app.main:app --reload
```

Or via Docker (recommended — avoids local Postgres setup entirely):

```bash
cd docker && docker compose up -d
docker compose exec backend alembic upgrade head
```

## Tests

```bash
pytest tests/ -v
```

Fixtures live in `tests/conftest.py`. **Known gap:** SQLite tests cannot validate
`with_for_update()` row-locking (silent no-op on SQLite) — a Postgres-backed concurrency test is
required before this touches real money.

## API endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/auth/login` | — | Firebase OTP → tokens |
| POST | `/api/v1/auth/refresh` | — | Rotate refresh token |
| POST | `/api/v1/auth/logout` | — | Revoke refresh token |
| GET | `/api/v1/auth/me` | User | Get profile |
| PATCH | `/api/v1/auth/me` | User | Update name |
| GET | `/api/v1/docks` | Public | List active docks |
| GET | `/api/v1/docks/{id}` | Public | Dock detail + slots |
| POST | `/api/v1/docks` | Admin | Create dock |
| PATCH | `/api/v1/docks/{id}` | Admin | Update dock |
| GET | `/api/v1/docks/vehicles/all` | Admin | List vehicles |
| POST | `/api/v1/docks/vehicles` | Admin | Add vehicle |
| PATCH | `/api/v1/docks/vehicles/{id}` | Admin | Update vehicle |
| POST | `/api/v1/rides/token` | User | Request ride token |
| POST | `/api/v1/rides/confirm` | None* | Hardware confirms unlock |
| POST | `/api/v1/rides/{id}/end` | User | End ride |
| GET | `/api/v1/rides/active` | User | Current active ride |
| GET | `/api/v1/rides` | User | Ride history |
| GET | `/api/v1/rides/{id}` | User | Ride detail |
| GET | `/api/v1/wallet` | User | Balance |
| POST | `/api/v1/wallet/topup` | User | Direct top-up, no payment check — dev/test only, see warning above |
| GET | `/api/v1/wallet/transactions` | User | Transaction history |
| POST | `/api/v1/wallet/admin/adjust` | Admin | Admin credit/debit |
| POST | `/api/v1/payments/orders` | User | Create Razorpay order for top-up |
| POST | `/api/v1/payments/webhook` | Signature | Razorpay payment.captured → credits wallet |
| POST | `/api/v1/notifications/device-token` | User | Register/update FCM device token |
| GET | `/api/v1/notifications` | User | List own notifications |
| GET | `/api/v1/admin/stats/dashboard` | Admin | Fleet + revenue + user stats |
| GET | `/api/v1/admin/stats/fleet` | Admin | Fleet utilization |
| GET | `/api/v1/admin/stats/revenue` | Admin | Revenue figures |
| GET | `/api/v1/admin/stats/users` | Admin | Wallet count |
| GET | `/api/v1/admin/users` | Admin | List all users |
| GET | `/api/v1/admin/users/{id}` | Admin | User detail |
| PATCH | `/api/v1/admin/users/{id}/role` | Admin | Set role |
| PATCH | `/api/v1/admin/users/{id}/active` | Admin | Activate/deactivate |
| GET | `/api/v1/admin/audit-logs` | Admin | Audit log |
| GET | `/api/v1/admin/rides` | Admin | All rides |
| GET | `/health`, `/api/v1/health` | — | Liveness probe |

*`/rides/confirm` is authenticated by the short-lived ride token, not a user JWT.

See [`../MERGE_CONFLICT_RESOLUTION.md`](../MERGE_CONFLICT_RESOLUTION.md) for how the
`integration/complete-backend` branch was reconciled with `main`.
