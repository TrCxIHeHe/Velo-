# Pricing, ride completion and recovery

## 1. Timestamp contract
* DB columns hold **naive UTC** (`TIMESTAMP WITHOUT TIME ZONE`); write with `app.core.timeutil.naive_utcnow()`.
* Every API timestamp is ISO-8601 UTC **with `Z`** (`2026-10-11T10:15:30.123456Z`) via `UTCDateTime`.
* Flutter parses with `parseServerTimestamp` (`lib/core/utils/server_time.dart`), which also accepts legacy
  zone-less strings *as UTC*. Duration is always `now(UTC) - started_at(UTC)`.
* The server-computed `duration_seconds` is authoritative once a ride is completed.

## 2. Pricing design
| Concern | Where |
|---|---|
| Algorithm (strategy) | `app/pricing/strategy.py` (`PricingStrategy`), `fixed_pair.py` |
| Data/config | table `dock_pair_fares` (NUMERIC(10,2), unique per **directed** pair) |
| Orchestration | `RideService` → `PricingService.calculate(ctx)` (quote **and** final fare) |

Only `fixed_dock_pair` exists: fare = the configured amount for (origin → destination). A→B and B→A are
independent rows. Duration is recorded but does not affect the fare. A missing/inactive tariff raises
`FARE_NOT_CONFIGURED` (409); there is no fallback formula. The ride stores `fare_amount`, `fare_currency`,
`pricing_strategy`, `pricing_reference_id` (the tariff row used). When a
destination is selected before unlock, the token request stores
`planned_end_dock_id` and the accepted fare snapshot
(`accepted_fare_amount`, currency, strategy and reference). Completion charges
that snapshot, so later tariff changes cannot alter an already accepted trip.

### Adding a strategy later (distance, time, subscription, promo, surge)
1. Implement `PricingStrategy.calculate(ctx) -> FareResult` (ctx has ride, user, origin, destination, start/end, duration).
2. Register it in `PricingService._build_strategies`.
3. Set `PRICING_STRATEGY=<name>`.

`RideService` is untouched (proved by `tests/pricing/test_pricing_strategy.py::test_new_strategy_plugs_in...`).

## 3. API
All responses use the `{success, data | error}` envelope.

**Fare estimate** (authenticated, read-only; origin comes from the stored ride)
```
GET /api/v1/rides/{ride_id}/fare-estimate?destination_dock_id=<uuid>
-> {"ride_id","origin_dock_id","destination_dock_id","fare_amount":20.5,"currency":"INR",
    "pricing_strategy":"fixed_dock_pair","pricing_reference_id":"<uuid>",
    "wallet_balance":100.0,"sufficient_balance":true}
```
Errors: `RIDE_FORBIDDEN` 403, `RIDE_NOT_FOUND` 404, `RIDE_INVALID_STATE` 409 (not ACTIVE), `DOCK_NOT_FOUND` 404
(missing/inactive), `DOCK_FULL` 400, `RIDE_SAME_DOCK_NOT_ALLOWED` 400, `FARE_NOT_CONFIGURED` 409.

**Pre-ride fare quote** (authenticated, read-only; no ride is created)
```
GET /api/v1/rides/fare-quote?origin_dock_id=<uuid>&destination_dock_id=<uuid>
```
The token request may include `destination_dock_id` to persist this quote as
the planned destination and accepted fare.

**End ride** – `POST /api/v1/rides/{id}/end` body `{"dock_id": "<uuid>"}` (nothing else is read).
Idempotent: repeating it for an already completed ride at the same dock returns that ride, no second charge.

**Tariff admin** (ADMIN only) – `/api/v1/admin/dock-fares`
```
POST   {"origin_dock_id","destination_dock_id","amount":"20.00","currency":"INR","is_active":true}   # 201
GET    ?origin_dock_id=&destination_dock_id=&is_active=
GET    /{id}
PATCH  /{id} {"amount":"22.00","is_active":false}      # deactivate instead of deleting
```
Errors: `FARE_ALREADY_EXISTS` 409, `FARE_INVALID_PAIR` 400, `DOCK_NOT_FOUND` 404, `FARE_NOT_FOUND` 404; amount must be > 0 with ≤ 2 decimals.

**Ride recovery** (ADMIN only) – `POST /api/v1/admin/rides/{ride_id}/recover`
```
{"action":"complete","dock_id":"<destination>","reason":"dev: scooter never docked"}   # ACTIVE ride
{"action":"cancel_pending","reason":"stale qr in dev"}                                  # PENDING ride
```
`complete` runs the identical validated flow as a normal end (configured fare, free slot, wallet debit, scooter
parked). An ACTIVE ride is never just flipped to CANCELLED. Audit actions: `RIDE_RECOVERED_COMPLETED`,
`RIDE_RECOVERED_CANCELLED` (actor = admin, reason in `meta`).

## 4. Migration and first tariffs
```bash
cd backend
alembic upgrade head        # revision a7c3e9d41b52 (adds dock_pair_fares + 2 nullable ride columns)
python scripts/seed_dev_data.py                       # optional dev docks/scooter/wallet
python scripts/set_dev_fares.py --list
# DEVELOPMENT TEST VALUES ONLY - the amount is mandatory, never defaulted:
python scripts/set_dev_fares.py --origin "MG Road Dock" --destination "Koramangala Dock" --amount 20 --reverse-amount 25
```
Production: use the admin API above. No tariff rows are inserted by any migration.

## 5. Transactions & concurrency
`get_db` commits when the handler returns, and routers convert `AppException` into a normal response, so a failure
mid-way would be **committed half-done** (confirmed: a failed wallet debit left the ride COMPLETED, uncharged).
`end_ride`/`recover_ride` therefore roll back on any failure, commit before sending notifications, and use
`SELECT … FOR UPDATE` plus compare-and-set transitions (`RideRepository.transition`) so confirm / cancel / expire /
end cannot overwrite each other. Notification failure never undoes a completed ride.
Limit: row locks and true concurrency are only exercised on PostgreSQL; the test-suite (SQLite) covers the
compare-and-set paths by simulating the interleaving, not real parallel transactions.
The database also enforces one `PENDING` or `ACTIVE` ride per user with a
partial unique index, closing the concurrent token-request check/create race.

## 6. Manual diagnostics for an unrecoverable ride
Recovery refuses (changing nothing) when records disagree. Inspect, in `psql`:
```sql
SELECT id,status,vehicle_id,start_dock_id,end_dock_id,started_at FROM rides WHERE id = '<ride>';
SELECT id,status,slot_id,battery_level FROM vehicles WHERE id = '<vehicle>';        -- want IN_RIDE, slot_id NULL
SELECT id,dock_id,slot_number,is_occupied FROM dock_slots WHERE id = '<slot_from_vehicle>';
SELECT * FROM wallet_transactions WHERE reference_id = 'ride:<ride>';                -- exists => already charged
```
Fix the specific inconsistency in a transaction (e.g. set the vehicle back to `IN_RIDE` with `slot_id = NULL`), then
re-run recovery. Do **not** wipe volumes or flush Redis.

## 7. Business rules chosen
* Returning to the **origin dock is not allowed** (`RIDE_SAME_DOCK_NOT_ALLOWED`; enforced in quote, end and DB check).
* Fares are in the tariff row's currency and must equal the wallet currency (`CURRENCY_MISMATCH` otherwise).
* `rides.fare_amount` and wallet columns remain legacy `FLOAT`; the tariff table is `NUMERIC(10,2)`. The same
  2-decimal value is written to both, so quote = persisted fare = debit.
