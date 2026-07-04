# Track B Setup Guide — Wallet + Dock Service

Welcome. This document assumes you're picking this up fresh, own Track B end
to end, and need to actually understand *why* things are structured this way
— not just copy-paste commands. Read it once fully before typing anything.

---

## 1. What was actually broken last time (read this first)

You hit `ModuleNotFoundError: No module named 'app'` when running
`alembic upgrade head`. That error has **one real cause and one contributing
cause**, and it's worth understanding both so it never happens again:

**Real cause:** Alembic (and Python in general) only knows about an `app`
package if you run commands from the directory that *contains* `app/` — i.e.
`backend/`. If you run `alembic upgrade head` from the repo root (`Velo-/`),
Python looks for `app` next to wherever it's standing and doesn't find it.

> **Rule: every backend command (`alembic`, `uvicorn`, `pytest`) is run from
> inside `backend/`, with the venv active. No exceptions.**

**Contributing cause:** the files you'd been given in chat (config.py,
database.py, wallet code, etc.) were shown to you as *text*, but text in a
chat window isn't a file on your disk. Nothing writes itself — you have to
save each one to the exact path shown. That's what this zip solves: everything
is already placed correctly, so you just extract it.

### Three more bugs I found and fixed while assembling this

These weren't your fault — they were inconsistencies from the earlier
session — but they would have blocked you at different points, so it's worth
knowing what changed and why:

1. **`app/wallet/router.py` and `service.py` imported from `app.core.exceptions`**,
   but your actual exceptions file lives at `app/exceptions.py` (there's no
   `app/core/exceptions.py` anywhere in the project). This would have caused
   an `ImportError` the instant you tried to start the server. Fixed: both
   files now import from `app.exceptions`.
2. **`get_current_user_id()` in the wallet router was a stub that always
   raised `NotImplementedError`.** Every single wallet endpoint would 500
   immediately — you'd never even get to test the ledger logic. Fixed: added
   `app/dependencies.py`, a clearly-labeled temporary dev auth stub (details
   in §5).
3. **`requirements/base.txt` installed `psycopg[binary]` (a *sync* Postgres
   driver), but `DATABASE_URL` uses the `postgresql+asyncpg://` scheme**,
   which needs the separate `asyncpg` package. The one installed didn't match
   the one the connection string asked for — you'd have hit
   `ModuleNotFoundError: No module named 'asyncpg'` on the first real DB
   connection. Fixed: swapped to `asyncpg` in `requirements/base.txt`.
4. **The `vehicle_status` model existed but had no table in the migration.**
   First time anything tried to write telemetry, you'd get
   `relation "vehicle_status" does not exist`. Fixed: added the table to
   migration `0001`.

None of this was carelessness on your end — it's exactly the kind of thing
that happens when code is handed over in a chat instead of a working repo.
It's fixed now.

---

## 2. What's in this zip, and what Track B actually owns

Per `docs/decisions` and the architecture doc, **Track B owns**: Wallet
Service, Dock Service, database schema/migrations, Admin Dashboard, and
Infra. Here's the honest status of each after this delivery:

| Area | Status | Where |
|---|---|---|
| Database schema (all tables) | ✅ Done | `alembic/versions/0001_track_b_tables.py` |
| Wallet Service (ledger, credit/debit/refund) | ✅ Done, testable now | `app/wallet/` |
| Dock Service (CRUD, slots, assign/release) | ✅ Done, testable now | `app/dock/` |
| Dock unlock validated against a real ride token | ⏳ Not started — needs Track A's ride-token/QR work first | — |
| Admin Dashboard | ⏳ Not started (Phase 5 per the roadmap) | — |
| Infra (Docker, Coolify, Oracle/Hetzner) | ⏳ Not started (Phase 5) | — |

**What "done today" means concretely:** you can run migrations, start the
API, and hit every wallet and dock endpoint with real database rows being
created and read back correctly. That's the actual foundation everything
else builds on — it's not a demo, it's the real Phase 1 implementation.

---

## 3. Directory layout — where every file goes

Extract this zip so it merges into your existing `Velo-/backend/` folder like
this:

```
Velo-/
└── backend/
    ├── .env.example
    ├── alembic.ini
    ├── alembic/
    │   ├── env.py
    │   ├── script.py.mako
    │   └── versions/
    │       └── 0001_track_b_tables.py
    ├── requirements/
    │   ├── base.txt
    │   └── dev.txt
    └── app/
        ├── __init__.py
        ├── config.py
        ├── database.py
        ├── response.py
        ├── exceptions.py
        ├── dependencies.py
        ├── main.py
        ├── models/
        │   ├── __init__.py
        │   ├── user.py, refresh_token.py        (Track A's tables — included so FKs resolve)
        │   ├── wallet.py, wallet_transaction.py
        │   ├── dock.py, dock_slot.py
        │   ├── vehicle.py, vehicle_status.py
        │   ├── ride.py, ride_event.py
        │   └── notification.py, audit_log.py
        ├── wallet/
        │   ├── __init__.py, schemas.py, repository.py, service.py, router.py
        └── dock/
            ├── __init__.py, schemas.py, repository.py, service.py, router.py
```

If a file already exists at that path (e.g. you already have
`app/config.py`), **overwrite it** with the version in this zip — they're the
corrected versions.

---

## 4. Step-by-step: from zero to running server (Windows / PowerShell)

Your working directory is
`C:\Users\triam\OneDrive\Desktop\Velo-\backend`. Every command below assumes
you're standing there.

```powershell
# 1. Extract the zip so its backend/ folder merges into yours, then:
cd C:\Users\triam\OneDrive\Desktop\Velo-\backend

# 2. Activate your existing venv (you already created backend\.venv)
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies — dev.txt includes base.txt plus test tools
pip install -r requirements\dev.txt

# 4. Create your real .env from the example (only needs to be done once)
copy .env.example .env
# Open .env and set your actual Postgres password. Keep it free of
# special characters (# % @ : /) — see the comment in .env.example for why.

# 5. Confirm scooter_db exists (you already created this) — otherwise:
#    psql -U postgres -c "CREATE DATABASE scooter_db;"

# 6. Run migrations — THIS MUST BE RUN FROM backend\, never the repo root
alembic upgrade head

# 7. Start the API
uvicorn app.main:app --reload
```

If step 6 succeeds you'll see Alembic log each table being created. If step
7 succeeds, open http://127.0.0.1:8000/docs — you should see a Swagger UI
listing `/wallet` and `/docks` endpoints.

---

## 5. The auth stub — what it is and why it's safe to use for now

Every wallet/dock write endpoint needs to know *which user* is calling it.
That's normally Track A's job (Firebase → JWT). Since that isn't merged yet,
`app/dependencies.py` gives you a `get_current_user_id` function that reads a
header instead of a real token:

```
X-Debug-User-Id: 11111111-1111-1111-1111-111111111111
```

Anything sent as this header is trusted with **zero verification**. This is
intentional and temporary — the file has a large comment block explaining
exactly what to replace it with once Track A's JWT decoding exists, and
nothing in `app/wallet/` or `app/dock/` will need to change when you do that
swap, because they only depend on the function's *return type*
(`uuid.UUID`), not its implementation.

**Never deploy this outside your own machine.**

---

## 6. Testing it yourself — copy-paste curl commands

Use any UUID you like as your test user; it doesn't need to exist in the
`users` table for the wallet/dock demo to work (SQLAlchemy only enforces the
foreign key when you try to join against it, which these endpoints don't).

```powershell
$UID = "11111111-1111-1111-1111-111111111111"

# Get (auto-creates) your wallet — balance starts at 0
curl.exe http://127.0.0.1:8000/api/v1/wallet -H "X-Debug-User-Id: $UID"

# Recharge ₹500
curl.exe -X POST http://127.0.0.1:8000/api/v1/wallet/credit `
  -H "X-Debug-User-Id: $UID" -H "Content-Type: application/json" `
  -d '{"amount": 500, "reference_id": "razorpay_test_1"}'

# Spend ₹30 on a ride
curl.exe -X POST http://127.0.0.1:8000/api/v1/wallet/debit `
  -H "X-Debug-User-Id: $UID" -H "Content-Type: application/json" `
  -d '{"amount": 30, "reference_id": "ride_abc123"}'

# Check balance again — should be 470
curl.exe http://127.0.0.1:8000/api/v1/wallet -H "X-Debug-User-Id: $UID"

# See the transaction history
curl.exe http://127.0.0.1:8000/api/v1/wallet/transactions -H "X-Debug-User-Id: $UID"

# Create a dock with 4 slots (creates the dock AND 4 dock_slots rows)
curl.exe -X POST http://127.0.0.1:8000/api/v1/docks `
  -H "X-Debug-User-Id: $UID" -H "Content-Type: application/json" `
  -d '{"name": "MG Road Dock", "latitude": 12.9716, "longitude": 77.5946, "total_slots": 4}'

# List docks (public — no header needed)
curl.exe http://127.0.0.1:8000/api/v1/docks

# Get one dock with its slots + availability (use the id from the create response)
curl.exe http://127.0.0.1:8000/api/v1/docks/<dock_id>
```

If every response has `"success": true`, you're fully working end to end.

---

## 7. Architecture — why the code looks like this

Every feature (wallet, dock, and eventually anything else you add) follows
the same four-layer pattern, matching Track A's auth code so the two
codebases merge cleanly:

```
router.py       → HTTP layer only. Parses request, calls the service,
                   wraps the result in success_response()/error_response().
                   No business logic lives here.
service.py       → Business rules. "Can this debit happen? Is there a slot
                   free?" Raises typed exceptions (from app/exceptions.py)
                   when a rule is violated.
repository.py    → The only place that talks to the database directly
                   (SQLAlchemy queries). No business logic here either —
                   just "get this row" / "insert this row".
schemas.py       → Pydantic models: what a request body must look like,
                   what a response looks like. Validates input for free.
```

**Why split it this way?** If Track A's Ride Service later needs to debit a
wallet when a ride ends, they import `WalletService` and call
`.debit(user_id, fare, reference_id=ride_id)` — they never touch SQL, and
you never touch their ride state machine. Same reasoning applies to Dock:
once Track A builds the real unlock flow, they'll call
`DockService.assign_vehicle()` directly instead of re-implementing slot logic.

### Why the wallet has no `balance` column

`wallets` only stores `id`, `user_id`, `currency`. The actual number you see
in `/wallet` is *computed* every time from `wallet_transactions`:

```
balance = SUM(CREDIT) + SUM(REFUND) - SUM(DEBIT)
```

This is deliberate, from `docs/database/...` and the architecture doc: there
is no balance field for a bug (or an attacker) to directly overwrite. Every
rupee that ever moved is a permanent, append-only row. If a balance ever
looks wrong, `wallet_transactions` is where you look — never `wallets`.
`amount` is always stored positive (there's a DB check constraint on it now,
`ck_wallet_txn_amount_positive`); the sign is implied entirely by `type`.

---

## 8. What's genuinely next (in priority order)

1. **Wire in Track A's real auth** once it's merged — replace the body of
   `get_current_user_id` per the instructions in `app/dependencies.py`.
2. **Dock unlock flow** — once Track A has ride-token generation/validation,
   the dock's `/docks/{id}/assign` endpoint is what their unlock handler
   should call after validating the QR token.
3. **Tests** — add `pytest` cases for `WalletService` (esp. the insufficient
   balance path) and `DockService` (esp. the dock-full path) using
   `aiosqlite` for a fast in-memory DB. `requirements/dev.txt` already has
   what you need (`pytest-asyncio`, `aiosqlite`).
4. **Admin dashboard + infra** — Phase 5 per the roadmap. Don't start these
   yet; Phase 1–3 (wallet, dock, ride integration) is the real risk area.

---

## 9. Common pitfalls (so you don't lose an evening to them again)

- **Always run alembic/uvicorn/pytest from `backend/`**, never the repo root.
- **Postgres password**: no `# % @ : /` characters — they break URL parsing
  in ways that look like an unrelated connection error.
- **A file shown in chat is not a file on disk.** If you're ever unsure
  whether something was actually saved, run `dir app\wallet` (or the
  equivalent folder) and check it's really there before debugging further.
- **`ModuleNotFoundError: No module named 'app'`** almost always means either
  (a) wrong working directory, or (b) venv isn't activated. Check both before
  anything else.
