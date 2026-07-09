# Integration Change Log — `Trcxi-TrackB` + `vishi` → `integration/main`

Branch: `integration/main` · Test suite: 94/94 passing

This is a complete record of every change made during the merge. Nothing below was silently
resolved — each entry states what existed on each branch, what was kept/changed, and why.

---

## 1. Repository structure

| Action | Path | Reason |
|---|---|---|
| Base | entire `backend/` tree | Branched from `Trcxi-TrackB` (newer Docker/requirements conventions) |
| Grafted in, unmodified | `app/auth/`, `app/ride/`, `app/audit/`, `scooter/` (Flutter app), `docs/` | Track A exclusive, no TrackB equivalent |
| Grafted in, unmodified | `app/core/exceptions.py` (later modified, §4), `firebase.py`, `jwt.py`, `redis.py`, `response.py` (later deleted, §3), `security.py` | Track A exclusive |
| Grafted in, unmodified | `tests/auth/`, `tests/ride/`, `tests/core/` | Track A exclusive test suites |
| Deleted | `backend/migrations/` (vishi's Alembic dir) | Superseded — see §5 |
| Deleted | `app/core/config.py` | Dead scaffold, body was `# configuration`, zero imports anywhere |
| Deleted | `app/core/security.py` (TrackB's stub, before Track A's real one overwrote it) | Same — dead scaffold, `# jwt/security` |
| Deleted | `app/db/base.py`, `app/db/session.py` | Dead scaffold, zero imports — real DB setup lives in `app/database.py` |
| Deleted | `app/api/`, `app/repositories/`, `app/schemas/`, `app/services/`, `app/utils/`, `app/middleware/` | Empty `__init__.py`-only packages, zero imports, leftover scaffolding |
| Deleted | `app/exceptions.py`, `app/response.py` (flat TrackB duplicates) | Superseded by `app/core/exceptions.py` / `app/core/response.py` — see §3 |
| Deleted | `app/dependencies.py` (debug auth stub) | Replaced by real auth — see §2 |
| Deleted | `tests/Conftest.py` | Case-collision with `tests/conftest.py` — see §6 |
| Deleted | root `context.md`, `setup.md`, `backend/TRACKB_NEXT_STEPS.md` | Stale single-track dev-session notes, no longer accurate post-merge |

---

## 2. Auth wiring (the actual integration seam)

Track B's `wallet`, `dock`, `admin` routers were built against a temporary dev stub:
`app.dependencies.get_current_user_id` / `require_admin`, reading an `X-Debug-User-Id` header
with zero verification. Track A's real auth (`app.auth.dependencies`) exposes `CurrentUser`
(a full `User` object) and `RequireAdmin`, not a bare UUID function — the two were never
designed to be call-compatible.

**Fix (plumbing, not a new feature):**
- Added two adapter functions to `app/auth/dependencies.py`:
  ```python
  async def get_current_user_id(current_user: CurrentUser) -> uuid.UUID:
      return current_user.id

  async def require_admin(admin_user: RequireAdmin) -> None:
      return None
  ```
- Repointed every import in `wallet/router.py`, `wallet/service.py`, `dock/router.py`,
  `dock/service.py`, `admin/router.py` from `app.dependencies` to `app.auth.dependencies`.
- Deleted `app/dependencies.py` entirely — the stub is no longer reachable from anywhere.

No business logic in wallet/dock/admin changed. Same function names, same call signatures.

---

## 3. Exceptions & response envelope

**Found:** `app/core/exceptions.py` (Track A) and `app/exceptions.py` (Track B, flat) were
near-duplicates — same `AppException` base, same `{success, error}` envelope shape — but each
had classes the other lacked. Track A's had ride/vehicle exceptions; Track B's had
`WalletNotFoundError`, `InsufficientBalanceError`, `InvalidTransactionAmountError`,
`DuplicateReferenceError`, `DockNotFoundError`, `DockFullError`, `SlotOccupiedError`,
`SlotNotFoundError`.

**Fix:** Union merge — all eight Track B exception classes appended to `app/core/exceptions.py`.
`app/exceptions.py` and `app/response.py` (flat duplicates) deleted; every import repointed to
`app.core.exceptions` / `app.core.response`.

**Second, deeper issue found while checking Flutter frontend compatibility:**
`app.auth.dependencies.get_current_user` raises raw `HTTPException(detail={"code":...,
"message":...})` on every 401 path. FastAPI's own default handler renders that as
`{"detail": {...}}` — not the `{"success": false, "error": {...}}` shape `common.md` mandates,
and not what the Flutter app's `AuthRemoteDataSource._map()` parses
(`response.data['error']['code']`). This was a **pre-existing defect in Track A's own code**,
invisible until the frontend-compatibility check and the wallet/admin router tests both
exercised it.

**Fix:** added a global `HTTPException` handler in `main.py` that normalizes any raw
`HTTPException(detail={code, message})` into the correct envelope — one fix covering all four
raise sites in `get_current_user`. Verified directly:

```
GET /wallet (no token)        -> 401 {'success': False, 'error': {'code': 'AUTH_INVALID_TOKEN', ...}}
GET /wallet (garbage token)   -> 401 {'success': False, 'error': {'code': 'AUTH_INVALID_TOKEN', ...}}
```

---

## 4. HTTPBearer 401-vs-403

**Found:** `bearer_scheme = HTTPBearer()` defaults to returning **403** for a missing
`Authorization` header — FastAPI's own default, not a merge artifact. `common.md`'s frozen
contract states `Missing token: 401 Unauthorized`. This had no test coverage on `vishi` alone;
Track B's `test_get_wallet_requires_auth_header` (`assert 401`) and
`test_admin_endpoints_reject_missing_auth_entirely` (previously asserted `403`, matching the old
stub's behavior) both caught it once merged.

**Fix:** `HTTPBearer(auto_error=False)` + explicit `raise HTTPException(401, ...)` when
`credentials is None`. Corresponding test in `tests/admin/test_admin_router.py` updated from
`assert resp.status_code == 403` to `== 401` to match the documented contract (authenticated-but-
non-admin correctly stays 403).

---

## 5. Dock module — union merge

`app/dock/router.py` and `app/dock/repository.py` existed on both branches at the same path with
**disjoint, non-competing endpoint sets**:

| Endpoint | Source |
|---|---|
| `GET /docks`, `GET /docks/{id}`, `POST /docks`, `POST /docks/{id}/assign`, `POST /docks/{id}/slots/{slot_id}/release` | Track B |
| `POST /docks/{id}/validate`, `POST /docks/{id}/unlock` | Track A |

**Fix:** merged into a single `router.py` containing all seven endpoints, with a new
`get_ride_service()` provider added alongside the existing `get_dock_service()` so the
validate/unlock endpoints can construct a `RideService`. `DockRepository` gained
`find_slot_by_vehicle()` (Track A's one method TrackB's repository lacked; TrackB's
`release_slot()` was already a superset of vishi's version, kept as-is).

---

## 6. `main.py` — rebuilt as `create_app()` factory

TrackB's flat `app = FastAPI(...)` module replaced with a factory pattern (vishi's style — the
only place a global exception handler can live cleanly). Mounts all five routers under
`settings.API_V1_PREFIX`, exposes `GET /api/v1/health` as the canonical health endpoint per
`common.md`'s frozen contract, keeps `GET /` as an unversioned dev convenience only.

---

## 7. Config — union merge

`app/config.py`: TrackB's `WALLET_DEFAULT_CURRENCY`, `WALLET_MIN_RIDE_BALANCE` kept; vishi's
`REDIS_URL`, `RIDE_TOKEN_SECRET`, `RIDE_TOKEN_ALGORITHM`, `RIDE_TOKEN_TTL_SECONDS`,
`VEHICLE_BATTERY_MIN_THRESHOLD` added. No overlapping keys, pure union. Same additions mirrored
into `.env.example`. `firebase-service-account.json` added to `.gitignore` (was missing on both
branches).

---

## 8. Requirements

Kept Track B's exact-pinned split files (`requirements/base.txt`, `requirements/dev.txt`) as
canonical — newer, more precise than vishi's loose `>=` pins. Restored packages TrackB's set was
missing, needed by the grafted auth/ride code: `firebase-admin==6.5.0`,
`python-jose[cryptography]==3.3.0`, `redis==5.0.0` (base), `fakeredis` (dev).

---

## 9. Docker

- `docker-compose.yml`: kept TrackB's file as canonical (postgres + backend + adminer), added a
  `redis` service (Track A's ride-token flow needs it) and the `firebase-service-account.json`
  volume mount. `RIDE_TOKEN_SECRET` added to the backend service's environment block.
- `Dockerfile`: unchanged — TrackB's multi-stage, non-root build was already correct.

---

## 10. Migrations — full rebuild, not a merge

**Found:** both branches independently created a migration named `0001` with `down_revision =
None`, in two different directories (`backend/migrations/` vishi, `backend/alembic/` TrackB).
TrackB's `0001` additionally re-created `users`/`refresh_tokens` — tables it doesn't own — because
it needed the FK targets. Running both in sequence would throw `DuplicateTable`; there is no
shared revision lineage to reconcile.

**Fix:** both histories deleted. A fresh `0001_baseline.py` generated via
`alembic revision --autogenerate` (run against a throwaway SQLite DB — no live Postgres was
available in the build environment; **flagged for a mandatory Postgres dry-run in CI before this
lands**) against the full merged 12-model set. One manual fix applied to the generated file: the
autogenerated script referenced `app.types.GUID()` without importing `app.types` — added
`import app.types` at the top. Revision ID renamed `0001` for a clean single head.

**Verified directly:**
```
alembic upgrade head    -> creates all 12 tables: docks, users, audit_logs, notifications,
                            refresh_tokens, vehicles, wallets, dock_slots, rides, vehicle_status,
                            wallet_transactions, ride_events
alembic downgrade base  -> drops cleanly, correct FK-respecting order
alembic upgrade head    -> re-applies cleanly (round-trip confirmed)
```

---

## 11. Tests

- **Case-collision fixed:** `tests/conftest.py` (vishi) and `tests/Conftest.py` (TrackB) are the
  same file on case-insensitive filesystems. Merged into one `tests/conftest.py`.
- **Auth fixtures rewritten:** `auth_headers` / `admin_headers` previously (TrackB) built
  `X-Debug-User-Id` headers directly. Now issue real Bearer tokens via `POST /auth/login` against
  a mocked Firebase service. `admin_headers` promotes the logged-in user's DB row to `role=ADMIN`
  after login — `require_role` re-reads from the DB on every request, so the already-issued token
  stays valid.
- **New fixture `other_auth_headers`:** a second real user, for isolation tests. Replaces
  TrackB's hardcoded two-UUID `X-Debug-User-Id` pairs.
- **`user_id` fixture restored:** plain UUID generator for direct service-layer unit tests
  that bypass HTTP/auth entirely.
- **`fakeredis` API mismatch fixed** in two places: the installed version exposes `.close()`, not
  `.aclose()` as vishi's original code assumed.
- **Stale imports fixed:** two test files still imported from the deleted flat `app.exceptions`.
- **Two test assertions updated** to match the real (correct) auth contract instead of the
  retired stub's behavior — both documented and justified above, not silently patched.

**Result:** 94/94 tests passing — `tests/auth`, `tests/ride`, `tests/core` (Track A),
`tests/dock`, `tests/wallet`, `tests/admin` (Track B, now running against real auth).

---

## 12. Frontend (`scooter/` — Flutter, Track A)

**Checked, not modified.** The Flutter app currently implements only the auth feature — no
ride, dock, or wallet screens exist yet on either branch.

Verified field-by-field against the merged backend:

| Frontend expects | Backend provides | Match |
|---|---|---|
| `POST /api/v1/auth/login` with `{firebase_id_token}` | Same | Yes |
| Response `data.access_token`, `data.refresh_token`, `data.user{id, phone_number, name, role, created_at}` | `SessionResponse`/`UserResponse` schemas, exact field names | Yes |
| `POST /api/v1/auth/refresh` with `{refresh_token}` | Same | Yes |
| Any 401 triggers `TokenInterceptor`'s refresh-and-retry | Now correctly returns 401 with the `{success,error}` envelope (§3, §4 fixes) | Yes — was broken pre-fix |
| `AuthRemoteDataSource._map()` reads `response.data['error']['code']` for non-401 errors | `AppException` subclasses already produced this shape; raw `HTTPException` 401s did not until §3's fix | Yes — fixed |

**No Dart code changes were required.** The two backend fixes in §3/§4 were necessary specifically
*because* of this compatibility check — without them, the app's token-refresh interceptor and
error-mapping logic would have silently misbehaved against certain 401 responses.

**Not yet checked, because it doesn't exist yet:** ride/dock/wallet screens, QR display, maps.

---

## 14. Post-integration fixes (found by review, not caught during the merge itself)

**`.env.example` was incomplete and had one invented field.** It was missing `JWT_ALGORITHM`,
`ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `FIREBASE_PROJECT_ID`,
`FIREBASE_SERVICE_ACCOUNT_PATH`, and `API_V1_PREFIX` — six real `Settings` fields from
`app/config.py` — and included `GOOGLE_APPLICATION_CREDENTIALS`, which doesn't correspond to
any actual field (the real field is `FIREBASE_SERVICE_ACCOUNT_PATH`). Rebuilt to be an exact 1:1
match against `Settings`, verified field-by-field.

**CI workflow was at the wrong path.** `backend/.github/workflows/ci.yml` — GitHub Actions only
ever reads workflows from the repository root's `.github/workflows/`, so this file would never
have actually triggered on GitHub as committed. Moved to `.github/workflows/ci.yml`. Also renamed
from "Track B CI" to "Backend CI" and updated triggers from `**track-b**`-pattern branches to
`main`/`integration/main`, since the workflow now covers the full merged test suite, not just
Track B's.

**Python version standardized to 3.11, not 3.12.** The Docker image and CI were both pinned to
3.12 with no stated reason. Checked every pinned dependency's `requires_python` metadata directly
against PyPI (not assumed): all support 3.10+, so nothing in the requirements actually needs
3.12 — the pin was arbitrary. Standardized on **3.11** in both `docker/Dockerfile` and
`.github/workflows/ci.yml`: new enough to be current, but a more conservative choice than the
newest release for compatibility with libraries (ML or otherwise) that tend to lag a Python
version behind on day-one support. Local dev on 3.10 (confirmed by one team member) remains fully
supported — nothing requires exactly 3.11.

## 15. Explicitly not done (per scope)

- `POST /ride/start`, `POST /ride/end` — not implemented (confirmed absent on both branches).
- Wallet debit on ride `COMPLETED` — not implemented; `ride.service -> wallet.service` edge does
  not exist yet.
- No hardware/MQTT communication of any kind.
- `POST /docks` still has no admin-role gate (any authenticated user can create a dock) — flagged,
  intentionally left as an open decision, not resolved here.
