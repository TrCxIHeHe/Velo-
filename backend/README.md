# Backend

FastAPI modular-monolith backend for the Zova MVP. Merged from Track A (auth, ride) and
Track B (wallet, dock, admin, infra) — see `../CHANGE_LOG.md` for the full merge record.

## Stack

FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL + PostGIS-ready · Redis · Alembic · Firebase Admin
SDK · Razorpay (planned) · pytest + pytest-asyncio

## Structure

```
app/
├── main.py              create_app() factory, global exception handlers, router mounting
├── config.py             Settings (env-driven)
├── database.py            engine, session factory, Base
├── types.py               GUID — cross-dialect UUID type (Postgres native / SQLite CHAR(36))
├── core/                   exceptions.py, response.py, firebase.py, jwt.py, redis.py, security.py
├── auth/                   Firebase login, JWT issue/refresh/rotation, /auth/me
├── ride/                   ride request, assignment, QR ride-token issuance
├── dock/                   dock/slot CRUD, QR validate + unlock authorization
├── wallet/                 ledger-based credit/debit/refund
├── admin/                  fleet/revenue/user dashboards (role-gated)
├── audit/                  audit log writes
└── models/                 12 SQLAlchemy models, all exported from models/__init__.py
```

Each feature module follows repository → service → router → schemas.

## Local development

Requires Python 3.10+ (all dependencies verified compatible against PyPI metadata down to
3.10). CI and the Docker image both standardize on **3.11** for reproducibility — if your local
interpreter is 3.10, that's fine for running the app and tests locally, but don't be surprised if
CI's exact behavior differs slightly; prefer Docker if you need to match CI/production exactly.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt
cp .env.example .env    # fill in real values — see comments in the file
alembic upgrade head
uvicorn app.main:app --reload
```

Or via Docker (recommended — avoids local Postgres/Redis setup entirely):

```bash
cd docker && docker compose up -d
docker compose exec backend alembic upgrade head
```

## Tests

```bash
pytest tests/ -v
```

94 tests. Fixtures live in `tests/conftest.py` — real Firebase (mocked) + real JWT auth flow via
`auth_headers`/`admin_headers`/`other_auth_headers`, not a debug header stub (that pattern was
retired during the Track A + Track B merge — see `../CHANGE_LOG.md`).

**Known gap:** SQLite tests cannot validate `with_for_update()` row-locking (silent no-op on
SQLite). A Postgres-backed concurrency test is required before this touches real money — see
`../FULL_SYSTEM_REPORT.md`.

## API contract

Frozen and authoritative: `../docs/api/common.md` (versioning, response envelope, error codes),
`../docs/database/auth_schema.md`, `../docs/domain/ride_state_machine.md`,
`../docs/domain/vehicle_state_machine.md`. Do not redesign these — extend around them.
