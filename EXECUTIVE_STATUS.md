# Velo — Implementation Status vs. MVP Architecture

**As of:** 2026-07-28 (updated — Redis security hardening + ride lifecycle UI complete)
**Scope of this report:** compares what's actually built in this repository against the architecture, team-split, security, database, QR-security, and hardware documents provided.

**Bottom line:** the entire software MVP — backend + Flutter — is now built and hardened, end to end: auth, wallet (balance/recharge/history), the full ride lifecycle (map → QR unlock → live tracking → end ride → receipt/fare breakdown), dark mode, and every backend-side security control from the architecture docs that doesn't require a live deployment. **By explicit decision, still out of scope:** the admin dashboard, the marketing website, and all hardware/IoT (ESP32, MQTT, dock/scooter electronics) — coming back to those later. Anything requiring an actual cloud deployment (hosting, monitoring stack, WAF) is also not started, since there's nothing deployed yet.

---

## 1. What's implemented

### Backend (FastAPI + PostgreSQL + Redis)
| Module | Status | Notes |
|---|---|---|
| Auth Service | ✅ | Firebase phone/OTP → **RS256**-signed JWT access tokens (15 min) + rotated refresh tokens (30 day, single-use, reuse revokes session family, **device-bound** via `X-Device-Id`) |
| Ride Service | ✅ | 3-step token→confirm→end lifecycle, fare calc (₹2/min, ₹5 min), wallet debit on end, **atomic Redis SETNX replay protection** on ride-token confirm |
| Wallet Service | ✅ | Ledger model (CREDIT/DEBIT, source enum), audit-logged |
| Dock/Vehicle Service | ✅ | Dock + slot + vehicle CRUD, availability, admin-gated writes, public read endpoints power the Flutter map |
| Admin Service | ✅ | Fleet/revenue/user stats, user management, audit log — API only, no frontend dashboard (by design, see Out of scope) |
| Payments (Razorpay) | ✅ Built, ⚠️ not activated | Order + HMAC-verified webhook → wallet credit, idempotent. Keys intentionally blank — `503` until your team configures them |
| Notifications (FCM) | ✅ | Push-and-persist on ride start/end/low-balance |
| Rate limiting | ✅ | slowapi, **Redis-backed in production** (shared across instances), in-process/disabled elsewhere |
| Audit logging, CORS/security headers, DB constraints, migrations | ✅ | Unchanged from prior pass |
| Test suite | ✅ | **110 tests passing** (105 + 2 Redis-replay-race tests + 3 device-binding tests) |

### Frontend (Flutter) — full ride lifecycle + wallet + dark mode
| Screen | Status | Notes |
|---|---|---|
| Splash / Login / Onboarding / Profile | ✅ | Re-themed; splash now also runs a root/jailbreak check before anything else loads |
| **Map** (bottom-nav tab) | ✅ | `flutter_map` + OpenStreetMap, dock markers, tap → bottom sheet → unlock |
| **Unlock** (bottom-nav tab) | ✅ | Dock-list picker, alternate entry point into the QR flow |
| **QR unlock screen** | ✅ | Requests a ride token, renders it as a QR code, live 30s countdown, polls for dock-hardware confirmation, auto-advances to ride tracking |
| **Ride** (bottom-nav tab / live tracking) | ✅ | Live duration + estimated fare (same formula as the receipt screen), "End Ride" → dock picker → receipt |
| Wallet / Recharge / Transaction History / Ride Receipt & Fare Breakdown | ✅ | From the prior pass, now reachable as a proper Wallet tab instead of a standalone push |
| Dark mode + design system | ✅ | Unchanged from prior pass |
| **Device binding** | ✅ | Persistent per-install device id sent as `X-Device-Id` on every request |
| **Cert-pinning scaffolding** | ✅ | Off by default (no prod cert yet); one `--dart-define` away from active once deployed |
| **Root/jailbreak detection** | ✅ | Blocks app use on a compromised device, fails open only on a plugin error |

Backend: **110/110** tests passing. Flutter: **11/11** tests passing, `flutter analyze` clean.

---

## 2. Explicitly out of scope (by your decision, not a gap)

- **Admin Dashboard** (Next.js) — backend APIs exist and are ready to be consumed whenever you want this built.
- **Marketing website** — not started.
- **All hardware/IoT** — ESP32 firmware (scooter + dock controllers), Mosquitto/MQTT, solenoid locks, charging system. The software side is now fully ready for this: dock/vehicle records, slot occupancy, and the ride-confirm endpoint (`POST /rides/confirm`, "called by dock hardware") are exactly the integration points real hardware will call.

## 3. Still not done (real gaps, not by request — mostly requires an actual deployment)

- **Hosting** (Oracle Free Tier → Hetzner), **Coolify**, **Cloudflare WAF/DDoS**, **Nginx**, **Let's Encrypt** — nothing is deployed anywhere yet, so none of this exists. `docker-compose.yml` (now including Redis) covers local/dev only.
- **Monitoring stack** (Grafana + Prometheus + Loki) — not deployed.
- **MinIO, n8n, Kong** — not deployed; nothing currently needs them (no file uploads, no external workflow triggers yet).
- **PostGIS** — docks still use plain `lat`/`lng` floats, sufficient for map markers; matters once you need real geo queries (nearest-dock, radius search).
- **App-integrity attestation** (Play Integrity / DeviceCheck) — root/jailbreak detection is in; the stronger "is this genuinely our unmodified binary" check is not.

## 4. Known, still-unaddressed issue

- **`POST /wallet/topup`** remains a live, unrestricted self-serve credit endpoint (intentional for dev/testing, documented in `backend/README.md`) — still a "free money" hole to gate or remove before any real-money pilot.

---

## 5. Security architecture — doc vs. reality (updated)

| Control (from Cybersecurity doc) | Status |
|---|---|
| Firebase token verification server-side | ✅ |
| JWT access token, short expiry, **RS256 asymmetric signing** | ✅ |
| Refresh token rotation + reuse detection + **device binding** | ✅ |
| Ride token expiry + one-time use via **Redis SETNX** (atomic, race-free) | ✅ |
| Rate limiting, **Redis-backed** in production | ✅ |
| Input validation via Pydantic, ORM-only queries | ✅ |
| Wallet CHECK constraint, audit log, Razorpay webhook verification | ✅ |
| CORS lockdown, security headers | ✅ |
| Flutter Secure Storage for tokens | ✅ |
| **Root/jailbreak detection** | ✅ |
| **Certificate pinning** | ✅ scaffolded, inactive until a real prod cert exists |
| **Obfuscated release builds** | ✅ documented as a required release step (`scooter/README.md`) |
| App Integrity API (Play Integrity/DeviceCheck) | ❌ Not implemented |
| Cloudflare WAF/DDoS, TLS termination, SSH hardening | ❌ Not implemented (no deployment yet) |

Every backend/mobile security control from the architecture docs that doesn't require an actual cloud deployment is now implemented.

---

## 6. Database schema — doc vs. reality

Unchanged from the prior pass, plus one addition: `refresh_tokens.device_id` (nullable, for device binding). All core tables from the Database Design doc exist and migrate cleanly.

---

## 7. Straight answer

**Software MVP: complete.** Backend (all services + every deployable security control) and Flutter (full ride lifecycle, wallet, dark mode, mobile hardening) are built, tested, and internally consistent with the architecture docs — with two deliberate, documented deviations (RS256 now matches the doc; DB-plus-Redis replay protection now matches the doc's own "most critical" recommendation).

**Deliberately deferred:** admin dashboard, marketing site, hardware/IoT — by your instruction, to revisit later.

**Requires a real deployment before it applies:** hosting, monitoring, WAF, and the app-integrity attestation piece — there's nothing to configure until a server and app-store listing actually exist.
