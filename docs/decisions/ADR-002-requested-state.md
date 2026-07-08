**1. Vehicle assignment concurrency**

`app/ride/repository.py` — `SELECT ... FOR UPDATE`, single row, transaction-scoped:

```python
async def find_available_for_assignment(self, min_battery: int) -> Vehicle | None:
    result = await self.session.execute(
        select(Vehicle)
        .where(
            Vehicle.status == "AVAILABLE",
            Vehicle.dock_id.is_not(None),
            Vehicle.battery_pct.is_not(None),
            Vehicle.battery_pct >= min_battery,
        )
        .order_by(Vehicle.last_seen_at.desc().nullslast())
        .limit(1)
        .with_for_update()
    )
    return result.scalar_one_or_none()
```

`with_for_update()` = `SELECT ... FOR UPDATE`. Row locked till commit/rollback. Two concurrent `/ride/request` calls hitting same vehicle: second blocks at DB level till first transaction ends, re-reads, sees `RESERVED`, moves to next row. No app-level lock, no race window, no double-assign.

Caveat, said before, saying again: **no-op on SQLite.** Tests pass on fake concurrency (single connection, serialized anyway). Real protection only proven on Postgres — not tested against real Postgres in this sandbox, no Postgres instance available here. Flag: run a real concurrent-request test against Postgres before trusting this in prod.

Vehicle marked `RESERVED` **inside same request**, before ride row created — no gap between lock read and reservation write.

---

**2. Redis key structure**

One key pattern only:

```
ride:jti:{jti}  →  value: "{ride_id}"   TTL: 30s
```

Full lifecycle:
```
issue():   SET ride:jti:<uuid4> "<ride_id>" NX EX 30
consume(): GETDEL ride:jti:<uuid4>   → atomic read+delete
```

No other Redis usage. No session cache, no OTP, no rate-limit keys — out of scope, not built, not asked.

- `NX` on issue → guards against jti collision (never fires in practice, uuid4).
- `GETDEL` on consume → atomic one-shot. Second call same key = `nil` = `RideTokenReusedError`. Natural expiry after 30s = same `nil` = same error, no distinction made (by design — "expired" and "already used" look identical to an attacker, no information leak).
- Value is the **ride_id**, not user_id — JWT payload carries `sub` already. Redis value exists purely to bind jti→ride without touching JWT payload shape (your instruction: payload minimal).

---

**3. Track B model parity — field by field**

Diffed every copied model against Track B source (`velo_trackb/backend/app/models/`):

| Model | Field | Track B | Track A | Match |
|---|---|---|---|---|
| **Vehicle** | id | GUID pk | GUID pk | ✅ |
| | qr_code | String(255) unique | same | ✅ |
| | status | String(20) default AVAILABLE | same | ✅ |
| | battery_pct | Integer nullable | same | ✅ |
| | dock_id | GUID FK docks.id nullable | same | ✅ |
| | last_seen_at | DateTime(tz) nullable | same | ✅ |
| **Dock** | id | GUID pk | GUID pk | ✅ |
| | name | String(255) | same | ✅ |
| | latitude/longitude | Float | same | ✅ |
| | total_slots | Integer default 0 | same | ✅ |
| | status | String(20) default ACTIVE | same | ✅ |
| | created_at | DateTime(tz) default utcnow | same | ✅ |
| **DockSlot** | id | GUID pk | GUID pk | ✅ |
| | dock_id | GUID FK docks.id | same | ✅ |
| | slot_number | Integer | same | ✅ |
| | vehicle_id | GUID FK vehicles.id nullable | same | ✅ |
| | is_occupied | Boolean default False | same | ✅ |
| | is_charging | Boolean default False | same | ✅ |
| **Ride** | id | GUID pk | GUID pk | ✅ |
| | user_id | GUID FK users.id | same | ✅ |
| | vehicle_id | GUID FK vehicles.id nullable | same | ✅ |
| | dock_start_id/dock_end_id | GUID FK docks.id nullable | same | ✅ |
| | status | String(30) default REQUESTED | same | ✅ |
| | fare | Numeric(10,2) nullable | same | ✅ |
| | start_at/end_at | DateTime(tz) nullable | same | ✅ |
| | created_at | DateTime(tz) default utcnow | same | ✅ |
| **RideEvent** | id, ride_id, event_type, payload(JSON), created_at | — | — | ✅ all match |
| **AuditLog** | id, actor_id, action, entity_type, entity_id, payload(JSON), created_at | — | — | ✅ all match |
| **types.GUID** | full TypeDecorator, PG↔SQLite dialect switch | — | byte-identical copy | ✅ |

**Zero drift.** Every column, type, nullable flag, FK target, default, index name — identical. Straight `cp`, not retyped, not reinterpreted. Ran a diff to be sure:All 7 files byte-identical to Track B source. Confirmed, not asserted.