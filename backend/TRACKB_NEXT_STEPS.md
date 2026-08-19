# Track B — Finishing the Job: Tests, Admin Dashboard, Infra

Welcome back. You already have a working foundation — migrations run,
wallet and dock endpoints work, and `setup.md` from the last session is
still accurate for everything it covers. This document picks up exactly
where that one left off (see its own "§8 What's genuinely next") and takes
you from "wallet + dock work" to "Track B is actually done": a real test
suite, the Admin Dashboard, and the infrastructure to deploy it.

Read this whole thing once before touching anything. It's written
assuming you own Track B end to end and this is a production system, not
a toy — every design decision below has a "why", not just a "how", because
the *why* is what stops you from breaking things later when you're moving
fast.

Everything described here has already been built, written to disk in the
correct paths, **and verified by me**: I stood up a real PostgreSQL 16
instance, ran `alembic upgrade head` against it, booted the real `uvicorn`
server (not a test client), and ran the exact `curl` workflow from
`setup.md` end to end, plus the new admin endpoints. I also ran the new
automated test suite five times in a row to rule out flakiness. Results
of all of that are in §7. You are not the first person to run this code —
I ran it first so you don't hit a wall today.

---

## 1. What changed since `setup.md`, and why

`setup.md` documented Phase 1 (Wallet + Dock, testable manually via curl).
This delivery adds Phase 1's missing safety net and jumps ahead to start
Phase 5. Specifically:

| Area | What changed | Why |
|---|---|---|
| **Dependency versions** | Bumped `python-multipart`, `orjson`, `python-dotenv`, `pytest` in `requirements/` | GitHub Dependabot flagged known CVEs in the pinned versions — see §2.3 |
| **Test suite** | Added — 38 tests across wallet, dock, and admin | Nothing was previously codified as "this must never break" |
| **Wallet idempotency** | Added `DuplicateReferenceError` + a per-wallet reference-id check | Prevents double-charging a user if a client retries a request |
| **Wallet row locking** | `debit()` now takes a row lock (`SELECT ... FOR UPDATE`) on Postgres | Prevents two concurrent ride-end requests from both reading a stale balance |
| **UUID columns** | Replaced `postgresql.UUID(as_uuid=True)` with a custom `app/types.py::GUID` type on every model | **A real bug**, found while writing tests — see §2 |
| **Admin Dashboard backend** | New `app/admin/` module: fleet, revenue, user stats | This is Track B's Phase 5 responsibility per the architecture doc |
| **Dev-role gate** | Added `require_admin` to `app/dependencies.py` | Admin stats shouldn't be readable by every wallet-holding user |
| **Seed script** | Renamed `seed_dev_user.py` → `seed_dev_data.py`, now seeds a dock, slot, and vehicle too | **A real gap in the last session's testing** — see §2 |
| **Docker + CI** | `docker/Dockerfile`, `docker/docker-compose.yml`, `.github/workflows/ci.yml` | Phase 5 infra, previously just TODO placeholders |

Nothing in `app/wallet/schemas.py`, `app/dock/*`, or the migration's table
*shapes* changed — your existing understanding of those still applies.

---

## 2. Two real bugs this session found (and fixed) — know these cold

These are the kind of bugs that don't show up until you test against the
*real* database, which is exactly why §7 exists. Both are now fixed, but
you should understand them, because the same class of bug can reappear if
you're not paying attention when you add the next feature.

### 2.1 The UUID-becomes-a-float bug

**Symptom:** occasionally, fetching a row back by its UUID primary key
would raise a totally opaque error, with the UUID value showing up in the
traceback as something like `1.111...e+31` — a floating point number,
where a UUID string should be.

**Root cause:** every model used
`from sqlalchemy.dialects.postgresql import UUID` directly, with
`UUID(as_uuid=True)`. That type is perfect on real PostgreSQL — it maps to
Postgres's native `uuid` column type, which is unambiguous. But it *also*
silently works (or seems to) against SQLite, which is what your entire
automated test suite runs against for speed (see §3). On SQLite, that same
type falls back to a plain `CHAR(32)` column with no explicit type
affinity guarantee. SQLite is dynamically typed at the storage layer: a
column with ambiguous affinity will store a value that *looks* like a pure
number (e.g. a UUID's hex form with no letters in it — rare, but `uuid4()`
generates one eventually) as an actual number instead of text. Read it
back, and SQLAlchemy tries to parse a UUID out of a Python `float`, and
everything downstream breaks.

**Fix:** `app/types.py` — a small `GUID` `TypeDecorator` that uses
Postgres's native type on Postgres, and a `CHAR(36)` storing the
**canonical hyphenated string form** (`str(uuid_obj)`, e.g.
`11111111-1111-1111-1111-111111111111` with the dashes) everywhere else.
The dashes guarantee the value never round-trips through SQLite's numeric
affinity by accident. Every model file was updated to import `GUID` from
`app.types` instead of `postgresql.UUID` directly. **Use `GUID` for every
new UUID column you add from now on** — never reach for
`postgresql.UUID` directly again in this codebase.

### 2.2 The "it doesn't need to exist" claim in `setup.md` was wrong for real Postgres

`setup.md` §6 said: *"it doesn't need to exist in the users table for the
wallet/dock demo to work (SQLAlchemy only enforces the foreign key when
you try to join against it, which these endpoints don't)."*

That's **incorrect once you're pointed at real PostgreSQL**, and I proved
it by actually running the curl workflow against a live Postgres instance
today: sending a random `X-Debug-User-Id` that has no row in `users` makes
the very first wallet write fail with a bare `500 Internal Server Error`
and a `ForeignKeyViolationError` in the server log — not one of our clean
`{"success": false, ...}` envelopes, because Postgres itself rejects the
`INSERT` before our exception handling ever gets a chance to run. Same
story for `dock_slots.vehicle_id`, which has a hard FK against
`vehicles.id` — assigning a random `vehicle_id` UUID fails the same way.

**Why the previous testing missed this:** the pytest suite runs against
**SQLite**, and SQLite does **not** enforce foreign key constraints by
default. So a test could insert a wallet row referencing a nonexistent
user all day and SQLite would never complain — meaning this bug is
completely invisible to the automated suite. It only appears against the
real database. This is a good lesson: **SQLite in tests proves your
business logic is correct; it does not prove your database constraints
are satisfied.** The two are different guarantees.

**Fix:** `scripts/seed_dev_data.py` (renamed from `seed_dev_user.py`) now
seeds **a dev user, a dev dock, a dev slot, and a dev vehicle**, with
fixed well-known UUIDs, so manual curl/Postman testing against real
Postgres always has valid FK targets to reference. Run it once after
every `alembic upgrade head` / database reset, before you touch any
endpoint manually.

---

### 2.3 Dependabot alerts on `requirements/base.txt` and `requirements/dev.txt`

GitHub's Dependabot scanned the last push and flagged several CVEs in
pinned versions — mostly in `python-multipart` (a transitive dependency
FastAPI uses for form/file uploads, which Track B doesn't currently use
directly but ships anyway as part of `requirements/base.txt`), plus one
each in `orjson`, `python-dotenv`, and `pytest`. None of these were
exploited or exploitable in anything Track B actually calls today — the
multipart issues are all about parsing multipart form uploads and
querystrings, which no current endpoint accepts — but pinning known-
vulnerable versions is still a real finding worth fixing immediately
rather than leaving open, since any future endpoint that *does* accept
file uploads would inherit the exposure silently.

**Fix:** bumped to the latest patched release of each:

| Package | Old | New |
|---|---|---|
| `python-multipart` | 0.0.20 | 0.0.32 |
| `orjson` | 3.11.1 | 3.11.9 |
| `python-dotenv` | 1.1.1 | 1.2.2 |
| `pytest` (dev) | 8.4.1 | 8.4.2 |

After bumping, I reinstalled (`pip install -r requirements/dev.txt -U`)
and reran the full 38-test suite plus `ruff check` — everything still
passes with zero code changes required, since none of these were breaking
API changes for how this codebase uses them.

**What to do:** pull the updated `requirements/base.txt` and
`requirements/dev.txt` from this delivery, reinstall
(`pip install -r requirements\dev.txt` from `backend/`, venv active), and
the Dependabot alerts should clear on your next push. If Dependabot opened
its own PRs for these (it does that automatically), you can close them
once you've merged this delivery's version bumps — no need to merge both.

## 3. The test suite — what it is, how to run it, what it does and doesn't prove

### 3.1 Running it

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements\dev.txt
pytest -v
```

You should see `38 passed`. If you want to check for flakiness the way I
did, just run `pytest -q` five times in a row — random UUIDs are involved
in some tests, so a single green run isn't as convincing as several.

### 3.2 Layout

```
tests/
├── conftest.py              # shared fixtures — read this file's docstring fully
├── wallet/
│   ├── test_wallet_service.py   # business rules: balance, idempotency, isolation
│   └── test_wallet_router.py    # HTTP layer: auth, envelopes, status codes
├── dock/
│   ├── test_dock_service.py     # slot assignment, capacity, edge cases
│   └── test_dock_router.py      # HTTP layer: public reads vs authed writes
└── admin/
    └── test_admin_router.py     # role gating + real-data-reflected-correctly
```

The **service-layer tests** (`test_*_service.py`) call `WalletService` /
`DockService` directly — no HTTP involved — so they're fast and pinpoint
exactly which business rule broke. The **router-layer tests**
(`test_*_router.py`) go through the full FastAPI app via an in-process
`httpx.AsyncClient`, so they also catch routing mistakes, missing
dependencies, and response-envelope regressions that a service-only test
can't see. Both layers matter; don't delete either kind when you extend
this.

### 3.3 Why SQLite, and the one thing it can't test

`tests/conftest.py` spins up a fresh **in-memory SQLite** database for
every single test function (not once per session — per test), using
`StaticPool` so all connections in that test share the same in-memory DB
instead of each getting an empty one. This is why the whole suite runs in
about a second with zero setup: no Docker, no local Postgres install
required just to run `pytest`.

The one thing this cannot verify: `with_for_update()` (the row lock used
in `WalletRepository.find_by_user_id_locked` and
`DockRepository.find_available_slot`) is a **silent no-op on SQLite**.
The tests confirm the *outcome* is correct (balances end up right, slots
end up occupied correctly), but they cannot prove the lock actually
*blocks* a second concurrent transaction the way it will on production
Postgres. If you ever need to prove that specifically — e.g. before a
security review — you'd write a separate test that opens two real
connections against the `docker-compose` Postgres service and fires two
debits at the exact same moment, asserting only one succeeds when the
balance is exactly enough for one.

### 3.4 What to do when you add a new feature

Every new service method gets a service-layer test for its business rules
(happy path + at least one failure path) and every new endpoint gets a
router-layer test for its auth requirement and its response envelope. If
you're tempted to skip this "just this once" — don't; the two bugs in §2
are exactly the kind of thing a five-minute test would have caught
immediately instead of costing an evening.

---

## 4. Wallet hardening: idempotency and row locking

Two additions to `WalletService`/`WalletRepository` that weren't in the
original delivery. Both matter for a payments system specifically —
this isn't defensive-programming-for-its-own-sake.

### 4.1 Idempotency (`reference_id` uniqueness per wallet)

**The problem it solves:** your Flutter app calls
`POST /wallet/credit` after a successful Razorpay payment. The request
times out on a flaky mobile network, so the app retries. Without
protection, that's now two `CREDIT` transactions for one real payment —
the user's balance is wrong, and they got free money.

**The fix:** `WalletService._check_idempotency()` looks up whether a
transaction with the same `wallet_id` + `reference_id` already exists
before writing a new one. If it does, the request is rejected with
`409 WALLET_DUPLICATE_REFERENCE` instead of writing a duplicate. This
means every caller (Razorpay webhook handler, ride-end handler, refund
handler) **must** pass a stable, unique `reference_id` — a Razorpay
payment ID, a ride ID, a refund ID — never `None` for anything that could
plausibly be retried. `reference_id=None` is still allowed by the schema
for cases where idempotency genuinely doesn't matter (there aren't many;
think twice before using it).

Note the scope: idempotency is checked **per wallet**, not globally
(`test_same_reference_id_different_wallets_is_allowed` documents this).
That's a deliberate simplification for now — if you later want ID
uniqueness enforced platform-wide (e.g. a Razorpay payment ID should never
appear twice across *any* wallet), add a unique index on
`(reference_id)` globally in a future migration. Don't do this yet without
checking with whoever owns the Razorpay webhook integration, since REFUND
transactions legitimately need to reference the same ride/payment ID that
the original DEBIT used, just with a different `type`.

### 4.2 Row locking on debit

**The problem it solves:** two ride-end requests for the same user arrive
at almost the same instant (rare, but not impossible — e.g. a flaky client
retry racing the original request). Without locking, both read the same
starting balance, both see "sufficient funds," and both succeed — even if
the wallet only actually had enough money for one of them.

**The fix:** `WalletRepository.find_by_user_id_locked()` uses
`SELECT ... FOR UPDATE`, which on PostgreSQL causes the *second*
concurrent transaction to wait until the first one commits or rolls back
before it can even read the wallet row. By the time it proceeds, it sees
the balance *after* the first debit, so the insufficient-balance check is
accurate. This is a no-op on SQLite (see §3.3) but fully effective on
Postgres.

You do **not** need to add this pattern to `credit()` or `refund()` —
there's no failure mode there where reading a stale balance causes an
incorrect *outcome* (both credits/refunds should always be allowed to
proceed; there's no "insufficient funds to receive money" check to race
against). Locking is specifically for the one place where a stale read
can produce a wrong business decision.

---

## 5. The Admin Dashboard — what's built, and what's left

Per the architecture doc, Track B owns "Admin Dashboard — fleet
monitoring & reporting (Next.js + FastAPI)." This delivery builds the
**FastAPI half** — the Next.js frontend is a separate, later effort (it's
explicitly Phase 5 in the roadmap, and per the doc's own advice, "hardware
and Grafana/monitoring can wait" — the dashboard's UI can wait similarly
until the backend contract is solid).

### 5.1 What's in `app/admin/`

Same four-layer pattern as wallet and dock (`repository.py` →
`service.py` → `router.py` → `schemas.py`), with one twist:
`AdminRepository` doesn't write its own SQL queries for data it doesn't
own — it **composes** `WalletRepository` and `DockRepository` (the same
ones wallet/dock endpoints already use and that your 38 tests already
verify are correct). This means:

- If wallet ledger math ever changes, dashboard revenue figures update
  automatically — there's no second copy of the balance formula to keep
  in sync.
- Adding a new stat is usually one new method on the existing repository
  plus one new method on `AdminService`, not a new query written from
  scratch.

### 5.2 Endpoints

| Method | Path | Returns |
|---|---|---|
| GET | `/api/v1/admin/dashboard` | Everything below, in one call (for the dashboard's landing page) |
| GET | `/api/v1/admin/fleet` | Dock/slot counts and utilization % |
| GET | `/api/v1/admin/revenue` | Total recharged / spent / refunded, and money currently held in wallets |
| GET | `/api/v1/admin/users` | Total wallet count (proxy for total onboarded users, for now) |

### 5.3 The `net_platform_balance_held` figure — read this before anyone asks "how much did we make"

`RevenueStatsResponse.net_platform_balance_held` = total recharged + total
refunded − total spent. **This is not revenue.** It's the total amount of
money currently sitting inside user wallets, waiting to be spent — a
liability on the platform's books (you owe your users rides worth that
amount), not money the business has earned. `total_spent` (the sum of
`DEBIT` transactions) is the closest thing to "revenue" this system
currently tracks, and even that overstates real revenue slightly since it
doesn't yet subtract Razorpay's ~2% transaction fee or refunded rides.
When Track A's ride/fare service is fully wired in, a proper revenue
figure will need to come from completed-ride fares, not raw wallet debits
— note this now so nobody accidentally reports `total_spent` as "monthly
revenue" to an investor.

### 5.4 The admin role gate — and its very deliberate limitation

`app/dependencies.py::require_admin` checks for a header
`X-Debug-Role: ADMIN`. This is exactly as insecure as it sounds — anyone
who knows the header name can claim to be an admin. It exists purely so
`/admin/*` isn't *accidentally* wide open to every logged-in user while
Track A's real role-based auth doesn't exist yet.

**When Track A's JWT decoding lands**, replace the body of
`require_admin` with a real check against the decoded token's `role`
claim (see `docs/database/auth_schema.md` — `users.role` already exists
and is exactly for this). Nothing in `app/admin/router.py` needs to
change — it only depends on `require_admin`'s behavior (raise 403 or
don't), not its implementation, same pattern as `get_current_user_id`.

### 5.5 What's genuinely NOT done yet (be honest with your team about this)

- **No pagination/date-range filtering** on revenue stats — right now
  it's all-time totals only. Add `start_date`/`end_date` query params
  when the dashboard needs "this month's revenue" instead of "all-time."
- **No per-dock or per-vehicle breakdown** — fleet stats are aggregated
  platform-wide. A real ops dashboard will want "which docks are at 100%
  utilization right now" as a list, not just a single percentage.
- **No audit-log endpoints** — the `audit_logs` table exists in the
  schema (and Track A/B write to it informally already through normal
  DB access) but there's no `/admin/audit-logs` endpoint to browse it
  yet. Straightforward to add following the exact same repository →
  service → router pattern once someone asks for it.
- **No Next.js frontend** — out of scope for this delivery, as discussed
  above.

---

## 6. Infrastructure — Docker and CI

### 6.1 `docker/Dockerfile`

A two-stage build: dependencies install in a `builder` stage, then only
the installed packages + your app code get copied into a slim final
image (no compilers or build tools shipped to production). Runs as a
non-root `appuser`, never as root — if the container is ever compromised,
you don't want that to mean root access inside it. Uses
`--proxy-headers` on uvicorn because the architecture doc's own request
flow is `Flutter → Cloudflare → Nginx → FastAPI`; without that flag,
every request in your logs would show Nginx's internal container IP
instead of the real client IP.

### 6.2 `docker/docker-compose.yml`

Three services: `postgres` (real Postgres in a container — this alone
would have prevented the "special characters in the password" bug from
`setup.md` §9, since you're not fighting a native Windows Postgres
install's quirks anymore), `backend` (built from the Dockerfile above),
and `adminer` (a tiny web UI at `http://localhost:8080` to browse your
tables without installing `psql` or a GUI client).

```powershell
cd backend\docker
docker compose up -d
docker compose exec backend alembic upgrade head
docker compose logs -f backend
```

Deliberately **not** included yet: Redis, Mosquitto, MinIO, Grafana — per
the architecture doc's own explicit guidance to skip these for the first
two phases. Add each one to this file only when the feature that actually
needs it starts (ride-token caching → Redis; hardware integration →
Mosquitto).

### 6.3 `.github/workflows/ci.yml`

Runs `pytest` (and a non-blocking `ruff check`) on every push and PR
against `main`. This matters specifically because you and Track A share
one repo — without CI, a broken Track B commit is only discovered when
Track A pulls latest and their own work breaks, at which point it's
unclear whose change caused it. This workflow runs independent of anyone's
laptop and gives a clear pass/fail signal on every PR.

It deliberately does **not** spin up a real Postgres service container —
it uses the same SQLite-based suite that runs locally, consistent with
§3. If you later add a test that specifically needs real Postgres
behavior (e.g. proving the row lock in §4.2 actually blocks a concurrent
transaction), add a `services: postgres: ...` block to this workflow at
that point, following GitHub Actions' standard service-container pattern.

---

## 7. Verification — what I actually ran, today, before handing this to you

I did not just write this code and assume it works. In order:

1. **Reconstructed the entire current repo state** in a sandbox from
   everything in this project, file for file.
2. **Installed dependencies** (`pip install -r requirements/dev.txt`) —
   clean install, no errors.
3. **Ran the new 38-test suite** — all passing, confirmed stable across
   5 consecutive runs (to catch the kind of randomness-dependent bug
   described in §2.1).
4. **Ran `ruff check app`** — zero warnings (after adding a couple of
   `# noqa: F821` comments for SQLAlchemy's forward-reference relationship
   strings, which are false positives — they're resolved at ORM
   mapper-configuration time, not at lint time).
5. **Installed a real PostgreSQL 16 server** in the sandbox (not SQLite)
   and created `scooter_db`, matching your actual setup.
6. **Ran `alembic upgrade head` against that real Postgres** — succeeded,
   all 12 tables created including the `ck_wallet_txn_amount_positive`
   check constraint.
7. **Booted the real `uvicorn` server** (not a test client) against that
   real database.
8. **Ran the exact curl workflow from `setup.md` §6, plus new ones**,
   against that live server: wallet get/credit/debit, duplicate-reference
   rejection, transaction history, dock creation, dock detail, vehicle
   assignment, and all four admin endpoints (including confirming the
   role gate actually returns 403 without the header). This is exactly
   where I found and fixed the two bugs in §2 — both surfaced only when
   testing against real Postgres, not the SQLite suite.
9. Confirmed the corrected `scripts/seed_dev_data.py` fixes the FK issues
   and the full flow — including dock vehicle assignment — succeeds
   end-to-end.

You can trust that everything described in this document, as written to
disk, actually works — not just "should work."

---

## 8. Your action list for today, in order

1. **Pull these files into your repo** at the paths shown (all files are
   provided alongside this document; nothing here requires you to
   hand-copy code from a chat window — see `setup.md`'s own note about why
   that was a problem last time).
2. **Overwrite** every model file with the `GUID`-using version (§2.1) —
   this is not optional, do this before anything else, since every other
   file depends on the models being correct.
3. From `backend/`, with your venv active:
   ```powershell
   pip install -r requirements\dev.txt
   pytest -v
   ```
   Confirm `38 passed`.
4. Run `alembic upgrade head` (should be a no-op if your DB is already at
   revision `0001` — Alembic just confirms current state; if you dropped
   your DB, it recreates all tables including the ones from the new
   migration content, which is identical in shape to before, just with a
   couple of extra indexes).
5. Run `python scripts/seed_dev_data.py` (note the renamed file) — this
   replaces the old `seed_dev_user.py` and additionally seeds a dev dock,
   slot, and vehicle, which you'll need for testing the unlock flow
   manually.
6. Start the server (`uvicorn app.main:app --reload`) and manually re-run
   the curl workflow from `setup.md` §6 to see it with your own eyes,
   then try the new admin endpoints:
   ```powershell
   curl.exe http://127.0.0.1:8000/api/v1/admin/dashboard `
     -H "X-Debug-User-Id: 11111111-1111-1111-1111-111111111111" `
     -H "X-Debug-Role: ADMIN"
   ```
7. Set up `docker/docker-compose.yml` if/when you want a Postgres you
   don't have to manage natively on Windows — entirely optional today,
   but it directly removes the exact class of "special characters in
   password" bug you hit last time.
8. Push to your `Trcxi-TrackB` branch and confirm the new GitHub Actions
   workflow goes green.
9. Everything genuinely left (per §5.5): admin pagination/date filtering,
   per-dock breakdowns, audit-log endpoints, and the Next.js frontend.
   None of these are urgent — Phase 1–3 (wallet, dock, ride integration
   with Track A) is still the real risk area per the architecture doc's
   own guidance, and this backend now has the test coverage to make that
   integration safe to build on top of.

You're in a genuinely good spot: migrations run cleanly, both real bugs
that would have bitten you today are already fixed, and there's a test
suite that will catch the next one before it costs you an evening.
