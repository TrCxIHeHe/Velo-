# System Report — Post-Integration State, Tradeoffs, and Scaling Roadmap (Code Level)

Reflects `integration/main`. For the whole-system report including hardware/infra not yet
built, see `FULL_SYSTEM_REPORT.md`.

---

## 1. What actually works today, end to end

| Capability | Status |
|---|---|
| Phone auth via Firebase, JWT issue/refresh/rotation, logout, get/patch profile | Working, tested |
| Ride request → vehicle assignment (battery/status-aware) | Working, tested |
| Dynamic ride-token (QR) issuance, 30s TTL, one-time use via Redis | Working, tested |
| Dock: list/get (public), create/assign/release (authenticated) | Working, tested |
| QR validation + unlock authorization at a dock | Working, tested — **stops at the authorization decision, no hardware call** |
| Wallet: get/create, credit, debit, refund, transaction history, per-user isolation | Working, tested |
| Admin dashboard: fleet/revenue/user aggregates, role-gated | Working, tested |
| Flutter app: Firebase login, onboarding, profile view/edit, token refresh, session expiry handling | Working, verified against merged backend contract |

**Not working / not built:** `/ride/start`, `/ride/end`, any wallet debit triggered by ride
completion, any MQTT/hardware communication, any Flutter screen beyond auth.

---

## 2. Architecture as it stands

Single FastAPI modular monolith, five vertical modules (`auth`, `ride`, `dock`, `wallet`,
`admin`) each following repository → service → router, wired through `create_app()`. One
PostgreSQL database (SQLite in tests only), Redis for ride-token one-time-use state, Firebase
Admin SDK for phone-auth verification. This matches the frozen architectural constraints
(modular monolith, no microservices/CQRS/Kafka/k8s) exactly.

---

## 3. Tradeoffs and decisions made during integration

**User/RefreshToken model ownership went to Track B, not the module owner (Track A).**
Track A owns auth conceptually, but its own `types.py` GUID fix was never applied to its own
`User`/`RefreshToken` models — Track B's copies were correct. Schema-correctness overrode
"the owning track wins," documented so future contributors know why.

**The migration history was discarded entirely rather than reconciled.** Two independent `0001`
histories with overlapping tables and no shared lineage cannot be merged incrementally without
real risk. Given neither branch had a live, seeded database anyone depended on, a clean rebuild
was lower-risk. **This is a one-time move** — all future schema changes must be incremental on
top of this baseline.

**Auth failures were normalized to a single envelope shape via a global exception handler rather
than rewriting every raise site.** Faster, lower-risk. Acceptable for MVP.

**Dock creation has no admin-role gate.** Left as-is deliberately rather than silently adding a
permission check that wasn't asked for. Real gap for pilot, flagged, unresolved.

**No live Postgres was available to validate the baseline migration.** Round-trip-verified
against SQLite only. Real, stated gap.

---

## 4. What changes post-MVP (code level)

- Implement `POST /ride/end` and wire `ride.service → wallet.service` for fare debit.
- Gate `POST /docks` behind `RequireAdmin`.
- Postgres-backed row-locking test for wallet debit and dock-slot assignment.
- Run `alembic --autogenerate --check` against real Postgres, not SQLite.
- Exercise CI on every PR against `integration/main`, including the Postgres test.

See `FULL_SYSTEM_REPORT.md` for the hardware/infra/frontend additions beyond the codebase.
