# Zova — Dock-Based Smart Micromobility

Monorepo for the Zova MVP: FastAPI modular-monolith backend + Flutter mobile app.

**Branch:** `integration/main` — the merged result of Track A (`vishi`: auth, ride, QR/unlock)
and Track B (`Trcxi-TrackB`: wallet, dock, admin, infra). See `CHANGE_LOG.md` for exactly what
was merged and why, and `FULL_SYSTEM_REPORT.md` for current state, tradeoffs, and the post-MVP
scaling plan. `vishi` and `Trcxi-TrackB` are retired — all new work branches from here.

---

## Repository layout

```
.
├── backend/     FastAPI application — see backend/README.md
├── scooter/     Flutter mobile app (auth feature only, for now)
├── docs/        Frozen API standards, auth schema, ride/vehicle state machines, ADRs
├── CHANGE_LOG.md          Every change made during the Track A + Track B merge
├── SYSTEM_REPORT.md       Post-integration state report (code-level)
└── FULL_SYSTEM_REPORT.md  Whole-system report (software + hardware + infra), vs. the
                           architecture doc's full proposal
```

---

## What's working today

| | |
|---|---|
| Auth | Firebase phone OTP → JWT access/refresh, rotation, reuse detection |
| Ride | Request → vehicle assignment → dynamic QR ride-token (30s TTL, one-time use) |
| Dock | CRUD, slot assign/release, QR validate + unlock authorization |
| Wallet | Ledger-based credit/debit/refund, per-user isolation, transaction history |
| Admin | Fleet/revenue/user dashboards, role-gated |
| Mobile | Firebase login, onboarding, profile, token refresh — Flutter |

**Not built yet** (see `FULL_SYSTEM_REPORT.md` §1.2 for the complete list): `/ride/end` and the
fare/wallet-debit-on-completion flow, any hardware/MQTT integration, and every Flutter screen
beyond auth (no map, QR display, or wallet UI yet).

---

## Quick start

```bash
cd backend/docker
docker compose up -d                       # postgres + redis + backend + adminer
docker compose exec backend alembic upgrade head
docker compose logs -f backend
```

API docs: `http://localhost:8000/docs` (development only). Health check:
`GET /api/v1/health`. Adminer (DB browser): `http://localhost:8080`.

Running the backend outside Docker is documented in `backend/README.md`. The Flutter app
(`scooter/`) is a standard `flutter pub get && flutter run` project — see
`scooter/lib/core/constants/api_constants.dart` for the backend base URL to point at your
running instance.

## Running tests

```bash
cd backend
pip install -r requirements/dev.txt
pytest tests/ -v
```

94 tests, all passing as of the last integration run — `tests/auth`, `tests/ride`,
`tests/core`, `tests/dock`, `tests/wallet`, `tests/admin`.

**Known gap:** tests run against SQLite. Row-locking (`with_for_update()`, used in wallet debit
and dock-slot assignment) is a silent no-op on SQLite — it has not been validated against real
Postgres concurrency. Do not treat a green local test run as proof this is safe under concurrent
load. See `FULL_SYSTEM_REPORT.md` §3.1 for the required fix before pilot.

---

## Architecture

Single FastAPI modular monolith. No microservices, no CQRS, no Kafka, no Kubernetes — by
deliberate constraint, not oversight (see `docs/decisions/`). Five vertical modules — `auth`,
`ride`, `dock`, `wallet`, `admin` — each following repository → service → router, wired through
a single `create_app()` factory. PostgreSQL is the single source of truth; Redis holds
ride-token one-time-use state; Firebase Admin SDK verifies phone auth. Full reasoning and the
current Oracle → Hetzner → AWS deployment path are in `docs/architecture.md`.

## Contributing

- One trunk (`integration/main`) going forward — the two-track parallel model that built the MVP
  is retired. See `FULL_SYSTEM_REPORT.md` §2.2 for why.
- Never reintroduce a debug/stub auth path reachable outside `ENVIRONMENT == "development"`.
- `app.dependencies`, `app.exceptions`, `app.response` (the old flat duplicate modules) no longer
  exist — use `app.auth.dependencies`, `app.core.exceptions`, `app.core.response`.
- Any module boundary touched by more than one contributor should have its endpoint list agreed
  before both sides start writing code — the dock-router merge in this integration was the direct
  cost of not doing that.

## Docs index

- `docs/api/common.md` — frozen API standards (versioning, response envelope, error codes)
- `docs/database/auth_schema.md` — auth tables schema
- `docs/domain/ride_state_machine.md`, `docs/domain/vehicle_state_machine.md` — approved state
  machines, source of truth for all ride/vehicle status transitions
- `docs/decisions/ADR-001-auth-phase1.md` — auth phase 1 decisions
- `docs/architecture.md` — the full MVP architecture proposal (stack, phases, hardware, security)
- `CHANGE_LOG.md` — the Track A + Track B merge, in full
- `SYSTEM_REPORT.md` — code-level post-integration report
- `FULL_SYSTEM_REPORT.md` — whole-system report against the full architecture proposal
