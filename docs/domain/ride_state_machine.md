# docs/domain/ride_state_machine.md

# Ride State Machine

Version: v1

Owner: Track A

Status: Approved

---

# Purpose

Defines the lifecycle of a ride.

Every ride in the system must exist in exactly one state at any point in time.

All services must follow this state machine.

Affected Services:

* Ride Service
* Vehicle Service
* Dock Service
* Wallet Service
* Notification Service

---

# Core Principle

A user may have:

```text
0 active rides
```

or

```text
1 active ride
```

Never more than one.

---

# Ride States

```text
REQUESTED
ASSIGNED
UNLOCK_PENDING
ACTIVE
END_PENDING
COMPLETED
CANCELLED
FAILED
```

---

# State Diagram

```text
REQUESTED
    |
    v
ASSIGNED
    |
    v
UNLOCK_PENDING
    |
    v
ACTIVE
    |
    v
END_PENDING
    |
    v
COMPLETED
```

Failure paths:

```text
REQUESTED
    |
    +--> CANCELLED

ASSIGNED
    |
    +--> FAILED

UNLOCK_PENDING
    |
    +--> FAILED

ACTIVE
    |
    +--> FAILED
```

---

# State Definitions

---

## REQUESTED

Meaning:

User wants a scooter.

Created when:

```http
POST /ride/request
```

is successful.

Requirements:

* User authenticated
* No active ride exists

Database:

```json
{
  "status": "REQUESTED"
}
```

Allowed Next States:

```text
ASSIGNED
CANCELLED
```

---

## ASSIGNED

Meaning:

Backend has selected a scooter.

Requirements:

* Scooter available
* Dock available

Example:

```json
{
  "ride_id": "R123",
  "vehicle_id": "S001",
  "dock_id": "D001",
  "status": "ASSIGNED"
}
```

Allowed Next States:

```text
UNLOCK_PENDING
FAILED
```

---

## UNLOCK_PENDING

Meaning:

Unlock command issued.

Waiting for dock confirmation.

Example:

```text
QR scanned
```

↓

```text
Dock validating
```

↓

```text
Unlock command sent
```

Allowed Next States:

```text
ACTIVE
FAILED
```

Timeout:

```text
60 seconds
```

After timeout:

```text
FAILED
```

---

## ACTIVE

Meaning:

Scooter is in use.

Ride officially started.

Required Data:

```json
{
  "started_at": "...",
  "vehicle_id": "...",
  "user_id": "..."
}
```

Allowed Next States:

```text
END_PENDING
FAILED
```

---

## END_PENDING

Meaning:

User attempting to end ride.

Waiting for:

* Dock confirmation
* Vehicle lock confirmation

Future hardware integration will trigger this.

Allowed Next States:

```text
COMPLETED
FAILED
```

---

## COMPLETED

Meaning:

Ride finished successfully.

Actions:

* Calculate duration
* Calculate fare
* Store trip record
* Trigger wallet debit
* Trigger notifications

Final State:

```text
TERMINAL
```

No transitions allowed.

---

## CANCELLED

Meaning:

Ride cancelled before unlock.

Examples:

* User cancelled request
* Timeout before assignment

Final State:

```text
TERMINAL
```

---

## FAILED

Meaning:

Unexpected failure.

Examples:

* Dock offline
* Scooter unavailable
* Unlock failed
* Hardware timeout
* Backend timeout

Final State:

```text
TERMINAL
```

---

# Transition Rules

Allowed transitions only.

| Current        | Next           |
| -------------- | -------------- |
| REQUESTED      | ASSIGNED       |
| REQUESTED      | CANCELLED      |
| ASSIGNED       | UNLOCK_PENDING |
| ASSIGNED       | FAILED         |
| UNLOCK_PENDING | ACTIVE         |
| UNLOCK_PENDING | FAILED         |
| ACTIVE         | END_PENDING    |
| ACTIVE         | FAILED         |
| END_PENDING    | COMPLETED      |
| END_PENDING    | FAILED         |

Everything else:

```text
RIDE_INVALID_STATE
```

---

# Ride Creation Rules

Before creating ride:

Validate:

1. User authenticated
2. User active
3. User has no active ride

If violation:

```text
RIDE_ALREADY_ACTIVE
```

---

# Vehicle Assignment Rules

Requirements:

```text
Vehicle Available
```

AND

```text
Vehicle Not In Maintenance
```

AND

```text
Vehicle Battery Above Threshold
```

Default threshold:

```text
20%
```

---

# Timeout Rules

REQUESTED

Maximum:

```text
120 seconds
```

Without assignment:

```text
CANCELLED
```

---

UNLOCK_PENDING

Maximum:

```text
60 seconds
```

Without confirmation:

```text
FAILED
```

---

END_PENDING

Maximum:

```text
120 seconds
```

Without completion:

```text
FAILED
```

---

# Ride Ownership Rules

Only ride owner can:

```text
View Ride
Cancel Ride
End Ride
```

Admin may:

```text
View Ride
```

Only.

---

# Future Expansion

Reserved for:

* Pause Ride
* Transfer Ride
* Reservation System
* Scheduled Booking
* Fleet Operations

Excluded from v1.

---

# Related APIs

Ride Service:

```http
POST /api/v1/ride/request

POST /api/v1/ride/start

POST /api/v1/ride/end

GET /api/v1/ride/{id}

GET /api/v1/ride/status/{id}
```

Vehicle Service:

```http
GET /api/v1/vehicles

GET /api/v1/vehicles/{id}
```

Dock Service:

```http
POST /api/v1/docks/{id}/validate

POST /api/v1/docks/{id}/unlock
```

Wallet Service:

```http
POST /api/v1/wallet/debit
```

triggered only after:

```text
COMPLETED
```

---

# Business Invariants

These rules must never be violated.

1. One active ride per user

2. One scooter assigned to one active ride

3. One ride belongs to exactly one user

4. Completed rides cannot be modified

5. Failed rides cannot become active

6. Cancelled rides cannot be restarted

7. Ride state transitions must follow this document
