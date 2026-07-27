# Merge Conflict Resolution: `origin/integration/complete-backend` → `main`

This document records how every conflict between `main` and `integration/complete-backend` was
resolved, and why. The two branches independently rewrote the entire `backend/app` tree from a
shared ancestor, so nearly every backend file showed as an `add/add` conflict (56 files). The
resolution below treats each module as a unit rather than line-by-line, since the two
implementations diverged in naming/schema, not just formatting.

## Summary of what integration/complete-backend contributes

- Wallet top-up / ride-fare debit / admin balance adjustment, with a full transaction ledger
  (`type` + `source` + `balance_after` per entry).
- Admin dashboard: user management (list/get/set-role/set-active), audit log browsing, all-rides
  view.
- Firebase-based phone auth used for both login and (unchanged) profile verification.
- The full 3-step ride lifecycle: `POST /rides/token` → `POST /rides/confirm` → `POST
  /rides/{id}/end`, replacing main's earlier 5-step QR/unlock flow.

Note: the task brief mentioned "Razorpay payment webhooks" and "FCM notifications." Neither
exists in `integration/complete-backend` as pulled — wallet top-up is a direct authenticated
endpoint (no external payment webhook), and `core/firebase.py` is used only for Firebase ID token
verification at login, not for sending push notifications. This document describes what the
branch actually contains, not the original feature summary.

## 1. Models — consolidation + compatibility shims

- `app/models/dock.py` now defines `Dock`, `DockSlot`, and `Vehicle` together (integration's
  version) instead of three separate files. Same table names/columns as before merge, but with
  `location_lat`/`location_lng`/`address`/`is_active` on `Dock` instead of main's
  `latitude`/`longitude`/`status`.
- `app/models/wallet.py` now defines `Wallet` and `WalletTransaction` together, with `Wallet`
  gaining a `balance` column and `WalletTransaction` gaining `source` (`TOPUP` / `RIDE_FARE` /
  `REFUND` / `ADMIN_ADJUSTMENT`) and `balance_after`.
- **Compatibility shims** were added/kept for every old single-class import path so nothing
  importing `from app.models.dock_slot import DockSlot`, `from app.models.vehicle import
  Vehicle`, or `from app.models.wallet_transaction import WalletTransaction` breaks:
  - `app/models/dock_slot.py` → re-exports `DockSlot` from `app.models.dock`
  - `app/models/vehicle.py` → re-exports `Vehicle` from `app.models.dock`
  - `app/models/wallet_transaction.py` → re-exports `WalletTransaction` from `app.models.wallet`
    (integration already shipped this shim)
- `app/models/ride.py`, `app/models/audit_log.py`, `app/models/user.py`,
  `app/models/refresh_token.py` — took integration's versions (see items 2–3 below for the
  reasoning specific to ride/audit).
- `ride_event.py`, `notification.py`, `vehicle_status.py` were byte-identical on both branches —
  no decision needed.

## 2. Ride model & schema — integration's column names

Adopted `start_dock_id`, `ride_token_jti`, `fare_amount`, `fare_currency`, `started_at`,
`ended_at`, `duration_seconds` (integration) over main's `dock_start_id`/`fare`/`start_at`/
`end_at`. This is the schema the 3-step ride flow (see §4) is built against.

## 3. AuditLog — integration's schema

Adopted `user_id` / `resource_type` / `resource_id` / `meta` over main's `actor_id` /
`entity_type` / `entity_id` / `payload` (JSON). `app/audit/repository.py` was updated to match
(`AuditLogRepository.log(user_id, action, resource_type, resource_id=None, meta=None)`).

## 4. Ride flow — integration's 3-step flow, main's 5-step flow dropped

Kept: `POST /rides/token` (issue a 30s JWT ride token + PENDING ride) → `POST /rides/confirm`
(dock hardware confirms, ride goes ACTIVE, vehicle assigned) → `POST /rides/{id}/end` (ride
COMPLETED, fare settled from wallet). Fare: ₹2/min, minimum ₹5.

Dropped: main's QR-validate/unlock-authorize endpoints (`POST /docks/{id}/validate`, `POST
/docks/{id}/unlock`) and their supporting modules, which are no longer reachable now that ride
tokens are self-contained JWTs instead of Redis-tracked one-time codes:
- `app/ride/event_repository.py` — deleted (no code path uses `RideEventRepository` anymore)
- `app/ride/token_codec.py` — deleted (superseded by JWT issue/verify inline in
  `app/ride/service.py`)
- `backend/tests/ride/test_ride_router.py`, `test_ride_service.py` — deleted (tested the removed
  flow and imported the deleted modules); replaced by integration's
  `tests/ride/test_ride_endpoints.py`, which exercises the 3-step flow end-to-end.

**Redis is now unused.** `app/core/redis.py` still exists (harmless, self-contained) but nothing
imports `get_redis_client` anymore, since the ride-token one-time-use tracking it backed no longer
exists. The `redis` service was dropped from `docker/docker-compose.yml` and CI, and `fakeredis`
was dropped from the test fixtures. `redis` stays in `requirements/base.txt` only because
`app/core/redis.py` still imports it; nothing else depends on it.

## 5. WalletService — integration's service, main's open ledger endpoints dropped

Kept integration's `top_up` / `debit_for_ride` / `admin_adjust` / `check_sufficient_for_ride` /
`list_transactions`, all built against the `type`+`source` transaction ledger. Dropped main's
generic `credit`/`debit`/`refund` endpoints (an open ledger API with no idempotency/reference
tracking) in favor of integration's `reference_id`-deduplicated top-up and admin-adjustment paths.

## 6. AdminService — merged both halves

Integration's user/audit/ride management and main's dashboard stats are genuinely different
features (not overlapping implementations of the same thing), so both were kept:

- `AdminRepository` (main) — composes `WalletRepository`/`DockRepository` for fleet/revenue/user
  stats, so ledger-calculation logic isn't duplicated in the admin layer.
- `AdminUserRepository` / `AdminAuditRepository` / `AdminRideRepository` (integration) — direct
  queries for user list/role/active management, audit log browsing, all-rides view.
- `AdminService` now takes all four repositories and exposes both sets of methods.
- `dock/repository.py` gained back `count_docks()` / `count_all_slots()` /
  `count_occupied_slots()` (main's dashboard queries, adapted to integration's `Dock`/`DockSlot`
  models — same column names already, so no logic changes needed).
- `wallet/repository.py` gained back `count_wallets()` and a new `sum_by_source(source)` (replaces
  main's `sum_all(type_)`, since revenue in the merged schema is more accurately split by `source`
  — `TOPUP`/`RIDE_FARE`/`REFUND` — than by `type`, which only distinguishes CREDIT/DEBIT).

**Route collision found and resolved:** both branches defined `GET /admin/users` for different
purposes — main returned wallet-count stats, integration returned a paginated user list. Kept
integration's `GET /admin/users` (user list) as-is, and moved main's dashboard-stat endpoints to a
`/admin/stats/*` sub-path: `GET /admin/stats/dashboard`, `/admin/stats/fleet`,
`/admin/stats/revenue`, `/admin/stats/users`.

Both branches also guard the whole `/admin` router with a role check — main via `require_admin`,
integration via `Depends(require_role("ADMIN"))`. Kept `require_role("ADMIN")` for the router
(integration's more explicit factory pattern); `require_admin` still exists in
`app/auth/dependencies.py` and is unused, left in place as a working alternative.

## 7. main.py — main's factory + integration's CORS

Kept main's `create_app()` factory pattern and the `AppException` → `error_response` handler.
Added integration's `CORSMiddleware` (`allow_origins=["*"]`, tighten per-env in production) and
its `lifespan` context manager for startup/shutdown logging. Both health checks are present:
`GET /health` (unversioned, for load balancers/uptime checks) and `GET /api/v1/health` (main's
frozen Phase-1 API-contract endpoint).

## 8. alembic — main's env.py pattern, integration's migration chain

- `alembic/env.py`: kept main's `from app import models` (imports the whole package, which
  registers every model via `models/__init__.py`, instead of importing each model module one by
  one) and its `.replace("%", "%%")` escaping on `DATABASE_URL` (prevents `ConfigParser`
  interpolation errors when a password contains `%`).
- `alembic/versions/`: main's single `0001_baseline.py` and integration's two-migration chain
  (`20240101_0000_initial_schema.py` → `20260727_..._track_b_schema_updates.py`) targeted
  different, incompatible schemas built from different divergent models — they can't be
  concatenated. Since the merged models (§1–3) are integration's schema verbatim, and
  integration's two-migration chain produces exactly that schema, main's `0001_baseline.py` was
  dropped and integration's two migrations were kept as the sole migration history.
- `alembic.ini`: kept integration's version (adds `file_template`, `timezone = UTC`, and a
  `[post_write_hooks]` section) since its `file_template` matches the timestamp-prefixed filenames
  the kept migrations already use.

## 9. requirements — main's newer pins

`requirements/base.txt`: kept main's file as-is — it already carries every package integration
needs (`firebase-admin`, `python-jose[cryptography]`, `redis`) at equal-or-newer versions, plus
extras integration didn't have (`orjson`, `structlog`, `python-dotenv`, `python-multipart`).

`requirements/dev.txt`: kept main's pins, added `pytest-cov` (integration's one genuinely useful
addition — matches the coverage step added to CI). Integration's `factory-boy` was dropped (grepped
the test suite — nothing imports it); `greenlet`/`anyio`/`httpx` are transitive dependencies of
`sqlalchemy[asyncio]`/`fastapi` already and don't need direct pins.

## Other conflicts (not covered by the numbered rules above)

- **`.gitignore`**: unioned both — kept main's `.venv/`/`venv/` entries and integration's
  `.coverage`/`htmlcov/`/`.mypy_cache/`/`dist/`/`build/`/`*.log` entries.
- **`.env.example`**: kept main's version — same variables, but with explanatory comments
  (e.g. why `DATABASE_URL` must not contain unescaped `%`/`#`/`@`/`:`/`/`) that integration's
  didn't have.
- **`docker/Dockerfile`**: merged both — kept main's multi-stage build + non-root `appuser` (main)
  and added integration's `HEALTHCHECK` + `PYTHONDONTWRITEBYTECODE`/`PYTHONUNBUFFERED` env vars.
- **`docker/docker-compose.yml`**: based on main's version, minus the now-unused `redis` service
  (§4). A duplicate, out-of-sync `backend/docker-compose.yml` scaffold file (no `redis`, different
  service names, from an early integration-branch commit) was deleted in favor of the one
  canonical `docker/docker-compose.yml`.
- **`.github/workflows/ci.yml`**: based on main's version (matches how the suite actually runs —
  SQLite, no Postgres/Redis service containers needed), bumped `python-version` from `3.11` to
  `3.12` to match the merged Dockerfile, and added integration's coverage-upload step. A duplicate
  `backend/.github/workflows/ci.yml` (GitHub Actions never reads workflows from that nested path —
  dead file) was deleted.
- **`backend/README.md`**: rewritten to describe the actual merged system — module layout, the
  3-step ride flow, and a corrected endpoint table (including the new `/admin/stats/*` paths).
- **Test suite** (`tests/conftest.py`, `tests/{admin,dock,wallet}/*`): kept main's `conftest.py`
  (drives tests through the real `/auth/login` flow with a mocked Firebase client, rather than
  minting JWTs directly) with its now-dead `fakeredis`/`get_redis_client` override removed. Took
  integration's `test_admin_router.py`, `test_dock_router.py`, `test_dock_service.py`,
  `test_wallet_router.py`, `test_wallet_service.py` since those test the app code that was
  actually kept (§4–6). `test_admin_service.py` and `test_auth_service.py` (both new, integration
  only) needed no schema changes but `test_admin_service.py` was updated for `AdminService`'s new
  4-argument constructor (§6).
  - **Bug found and fixed during verification**: `admin_headers` and `auth_headers` both logged in
    as the same mocked Firebase UID, so any test requesting both fixtures together (e.g.
    `test_admin_can_promote_user_to_admin`, `test_wallets_are_isolated_between_users`) got the
    *same* underlying user for both, not two distinct ones. Fixed by giving `admin_headers` its
    own Firebase UID/phone so it always creates a second, distinct user.
- **Leftover scaffold directories** carried over from `integration/complete-backend`'s history —
  `app/api/`, `app/db/`, `app/dependencies.py`, `app/exceptions.py`, `app/middleware/`,
  `app/observability/`, `app/repositories/`, `app/response.py`, `app/schemas/`, `app/services/`,
  `app/utils/`, `app/core/config.py` (a second, unused config module, distinct from the real
  `app/config.py`) — are not wired into `main.py` or imported by any router/service (verified by
  grep). Left in place untouched since removing them wasn't part of the requested conflict
  resolutions, but they are dead code and a good target for a follow-up cleanup PR.
  `backend/pytest_output.txt` (a committed pytest run artifact) and `backend/scripts/
  seed_dev_data.py` (still calls the now-removed `POST /wallet/credit` and `POST /docks/{id}/
  assign` endpoints) were similarly left/removed as noted — `pytest_output.txt` was deleted
  outright since it's pure build output; `seed_dev_data.py` was left in place but is stale and
  needs a follow-up update to match the merged wallet/dock APIs.

## Verification

After resolving all 56 conflicting files (plus deletions/additions), the full backend test suite
was run from a clean virtualenv against `requirements/dev.txt`:

```
78 passed in 5.50s
```

No `<<<<<<<`/`=======`/`>>>>>>>` markers remain anywhere in the tree.
