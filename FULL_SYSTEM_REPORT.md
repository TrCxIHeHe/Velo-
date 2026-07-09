# Zova — Full System Report
### Current Working State · Tradeoffs & Decisions · Post-MVP Scaling Plan

Scope: the entire proposed system per the architecture doc (`docs/architecture.md`) — software,
hardware, infra, security, and team process — cross-referenced against what is actually built in
`integration/main` today. Where the architecture doc proposes something not yet built, that's
stated explicitly rather than assumed.

---

## PART 1 — Current Working State

### 1.1 What's actually running today (built + tested)

| Layer | Component | State |
|---|---|---|
| Backend | Auth (Firebase phone OTP, JWT, refresh rotation) | Built, tested |
| Backend | Ride request → assignment → QR token issuance | Built, tested |
| Backend | QR validate + unlock authorization | Built, tested — decision only, no hardware call |
| Backend | Dock CRUD + slot assign/release | Built, tested |
| Backend | Wallet ledger (credit/debit/refund/history) | Built, tested |
| Backend | Admin dashboard (fleet/revenue/user aggregates) | Built, tested |
| Frontend | Flutter: Firebase login, onboarding, profile, token refresh | Built, verified against backend contract |
| Infra | PostgreSQL schema (12 tables), one clean baseline migration | Built, verified (SQLite round-trip; Postgres dry-run still pending) |
| Infra | Docker Compose: postgres + redis + backend + adminer | Built |

### 1.2 What the architecture doc proposes that is NOT built yet

| Proposed (doc) | Actual state |
|---|---|
| Ride lifecycle through `COMPLETED`, fare calc, wallet debit | **Not built.** `/ride/end` doesn't exist; `ride.service` never calls `wallet.service` |
| ESP32 dock controller + ESP32 scooter controller (BLE tether, relay kill-switch, QR scanner UART) | **Not built.** No firmware, no MQTT client anywhere in the repo |
| Mosquitto MQTT broker | **Not built/deployed.** `app/mqtt/` doesn't exist yet |
| Leaflet + OpenStreetMap map screens | **Not built.** No map UI in Flutter; only `GET /docks` exists server-side |
| Wallet/ride/dock/map Flutter screens | **Not built.** Only the auth feature exists client-side |
| Grafana + Prometheus + Loki monitoring | **Not built.** No metrics instrumentation anywhere (structured logging only) |
| MinIO object storage | **Not built/deployed.** Nothing writes to object storage yet |
| n8n workflow automation | **Not built/deployed.** Nothing to automate yet — no completed rides, no notifications sent |
| Coolify deploy pipeline, Oracle Free Tier hosting | **Not deployed anywhere.** Docker Compose exists locally only |
| Push notifications (FCM) | **Not built.** `notifications` table exists; nothing writes to it |
| Layered hardware safety control (fuse → relay → ESP32 state machine → cloud supervisor → mechanical fail-safe) | **Not built.** No hardware exists yet — correctly deferred per the doc's own Phase 3 sequencing |

**Read this table as the actual backlog.** The architecture doc is the target; §1.1 is the
current position; the delta is real, sequenced work, not oversight.

---

## PART 2 — Tradeoffs and Decisions

### 2.1 Decisions already made and standing (from the architecture doc, still valid)

- **Modular monolith over microservices.** Correct for a two-person team — the merge exercise
  itself is proof of the cost of *not* having this discipline: two people working in parallel on
  nominally separate "services" still produced two competing `dock` implementations and two
  competing migration histories, inside a single repo, in weeks. Microservices would have made
  that worse at this team size.
- **Open-source replacements for AWS/Google Maps/CloudWatch/S3/EMQX during MVP.** Still the right
  call — none of these are load-bearing decisions yet because none of them are deployed. The risk
  sits entirely in whether the team executes the Oracle→Hetzner→AWS migration path when the
  trigger conditions (28K map requests/month, 50+ docks, real production traffic) are hit.
- **Ledger-based wallet (append-only, computed balance) over a stored balance column.** Already
  implemented exactly as specified. Good call to lock in early — retrofitting a ledger model
  after real transaction history exists is much harder than starting with it.
- **Firebase Auth kept, all business logic in FastAPI/Postgres.** Confirmed correct in practice —
  the merge required zero changes to this boundary.

### 2.2 Decisions made or exposed during integration (new information)

- **The two-track parallel-development model has run its course.** It got two people moving
  independently through the MVP's first phases, but produced exactly the failure modes you'd
  expect: divergent type-correctness, two dock implementations, two migration histories,
  incompatible auth stubs. Continuing this pattern into hardware/wallet-debit work would compound
  the same problem. **Decision: single trunk from `integration/main` forward.**
- **Auth's own models weren't internally consistent with auth's own utility code** — `types.py`
  (GUID) was written by Track A but never applied to Track A's own models. A process gap, not a
  one-off bug — worth a lightweight rule (e.g. a lint rule banning direct `postgresql.UUID`
  imports outside `types.py` itself).
- **A stub built for one track's convenience became load-bearing for another track's entire test
  suite**, and had to be surgically replaced without breaking either. Direct cost of building
  against a placeholder instead of a feature-flagged real dependency. Going forward, any temporary
  stub for a not-yet-merged dependency should implement the *real* interface, not a parallel one.
- **SQLite-only testing was accepted as sufficient for MVP velocity, with a known, explicit gap**
  (row locking is a no-op on SQLite). Fine short-term; has a hard deadline before real money moves
  through the wallet ledger under concurrent load.

### 2.3 Open decisions, not yet made

- Whether `/ride/start` stays implicit (a side effect of dock unlock) or becomes an explicit
  rider-facing endpoint — affects Flutter's ride-feature design, should be decided before that's
  built, not after.
- Whether `POST /docks` requires admin role — currently open to any authenticated user, flagged
  twice, unresolved.
- Whether unlock authorization should be synchronous (backend waits for a dock ack over MQTT) or
  asynchronous (backend responds immediately, dock reports success via a follow-up event) — a
  real latency-vs-reliability tradeoff, should be decided once hardware exists.

---

## PART 3 — Post-MVP Changes for Scaling

Sequenced the way the architecture doc itself sequences things — Pilot (50–500 users, 10
scooters/5 docks) versus Production (50+ scooters/25+ docks) — plus what to actively retire.

### 3.1 Additions at Pilot stage

**Software**
- Complete the ride lifecycle: `/ride/end`, fare calculation, wallet debit integration,
  notification dispatch on ride start/end and low balance.
- MQTT (Mosquitto) integration: dock/scooter telemetry into `vehicle_status`, plus the
  unlock-dispatch decision from §2.3.
- Grafana + Prometheus + Loki, added *before* pilot traffic — retrofitting observability after an
  incident is strictly worse.
- Flutter: QR display + countdown, map/dock screens, active-ride tracking, wallet UI, recharge
  flow (Razorpay).
- Real CI exercising the full test suite plus a Postgres-backed concurrency test on every PR.

**Hardware**
- First real dock + scooter controllers: ESP32-C3 (dock) / ESP32 (scooter) dev boards, QR
  scanner module, solenoid lock + relay, presence/temperature sensors — per the doc's BOM
  (₹2,500–4,300 per dock, ₹1,200–2,150 per scooter in electronics alone).
- The four-layer safety control chain (hardwired power path → ESP32 local state machine → cloud
  supervisor → mechanical fail-safe) — the one piece of the doc carrying real physical-safety
  risk if rushed; should not be compressed to hit a pilot date.

**Infra**
- Migrate Oracle Free Tier → Hetzner VPS (₹1,500–3,000/mo).
- MinIO for object storage (audit exports, daily `pg_dump` backups with retention).
- SIM connectivity (Airtel IoT or similar) for docks, replacing Wi-Fi-only MVP connectivity.
- n8n for operational automation — becomes useful once there's real operational volume.

### 3.2 Additions at Production stage (50+ scooters, 25+ docks)

- Custom PCB design replacing dev boards.
- Managed eSIM replacing individual SIM cards.
- Migration executes for real: Hetzner → AWS/Azure/GCP, MinIO → S3, Mosquitto → EMQX Cloud,
  self-hosted Postgres → managed.
- Revisit the modular-monolith decision — not necessarily to break it up, but to measure whether
  any single module (most likely `ride` or `wallet`) has outgrown co-deployment. A
  measurement-driven decision at that point, not a default assumption.

### 3.3 Deletions / retirements

- **`vishi` and `Trcxi-TrackB` branches** — retire once `integration/main` is confirmed stable in
  a real environment.
- **The two-track-parallel-development process itself** — retire in favor of single-trunk.
- **Debug/dev-only auth shortcuts of any kind** — none reachable outside
  `ENVIRONMENT == "development"`; delete before exposure to any pilot user.
- **SQLite as sufficient proof of correctness for row-locking or Postgres-specific-type code** —
  fine for fast unit tests, not for concurrency/JSONB correctness claims.
- **GPS on the scooter** — explicitly out of scope through Pilot; phone GPS suffices. Don't let it
  creep in early (₹400–800/scooter, antenna routing, battery drain for a Production-stage need).
- **Any hand-rolled dock/router duplication pattern** — the dock-router union-merge in this
  integration was expensive because two people built the same file path independently without an
  interface contract. Any module boundary crossed by more than one contributor should have its
  endpoint list agreed *before* both sides start writing code.

---

## 4. One-line summary for each audience

- **For the incubator:** the software foundation (auth, ride-request, wallet, dock CRUD, admin)
  is built and tested; the two riskiest remaining pieces are hardware integration (unbuilt,
  correctly deferred) and completing the ride-to-payment loop (unbuilt, should be next).
- **For the engineering team:** stop parallel-track development, finish `/ride/end` +
  wallet-debit next, validate the migration and row-locking against real Postgres before any
  pilot user's money touches the wallet ledger.
- **For whoever owns hardware:** nothing in this report changes the doc's own sequencing —
  hardware starts after the software loop closes, and the four-layer safety chain is not a place
  to cut corners for a demo date.
