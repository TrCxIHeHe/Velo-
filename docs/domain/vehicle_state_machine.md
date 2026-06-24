# docs/domain/vehicle_state_machine.md

# Vehicle State Machine

Version: v1

Owner: Track A

Status: Approved

---

# Purpose

Defines the lifecycle of a scooter.

Every scooter must exist in exactly one state at any point in time.

All backend services must follow this state machine.

Affected Services:

* Vehicle Service
* Ride Service
* Dock Service
* Admin Service
* Notification Service

---

# Core Principle

A vehicle is an independent asset.

A ride references a vehicle.

A vehicle does NOT belong to a ride.

Example:

```text
Vehicle Exists
      ↓
Ride Uses Vehicle
      ↓
Ride Ends
      ↓
Vehicle Continues Existing
```

---

# Vehicle States

```text
AVAILABLE

RESERVED

IN_USE

DOCKING

CHARGING

MAINTENANCE

OFFLINE
```

---

# State Diagram

```text
AVAILABLE
    |
    v
RESERVED
    |
    v
IN_USE
    |
    v
DOCKING
    |
    v
CHARGING
    |
    v
AVAILABLE
```

Failure paths:

```text
AVAILABLE
    |
    +----> MAINTENANCE

CHARGING
    |
    +----> MAINTENANCE

ANY STATE
    |
    +----> OFFLINE
```

---

# State Definitions

---

## AVAILABLE

Meaning:

Vehicle is ready for assignment.

Requirements:

* Online
* Healthy
* Not assigned
* Battery above minimum threshold

Example:

```json
{
  "vehicle_id": "S001",
  "status": "AVAILABLE",
  "battery": 85
}
```

Allowed Next States:

```text
RESERVED
MAINTENANCE
OFFLINE
```

---

## RESERVED

Meaning:

Backend has assigned the scooter.

Ride exists.

User has not started riding yet.

Example:

```text
Ride Status = ASSIGNED

Vehicle Status = RESERVED
```

Allowed Next States:

```text
IN_USE
AVAILABLE
OFFLINE
```

---

## IN_USE

Meaning:

Scooter currently being ridden.

Ride Status:

```text
ACTIVE
```

must exist.

Allowed Next States:

```text
DOCKING
OFFLINE
```

---

## DOCKING

Meaning:

Ride ending process started.

Waiting for:

* Vehicle return
* Dock confirmation
* Lock confirmation

This state exists because:

```text
ACTIVE
```

and

```text
CHARGING
```

are not immediate transitions.

Allowed Next States:

```text
CHARGING
AVAILABLE
OFFLINE
```

---

## CHARGING

Meaning:

Vehicle physically docked.

Battery charging.

Example:

```json
{
  "vehicle_id": "S001",
  "battery": 42,
  "status": "CHARGING"
}
```

Allowed Next States:

```text
AVAILABLE
MAINTENANCE
OFFLINE
```

---

## MAINTENANCE

Meaning:

Vehicle removed from service.

Examples:

* Low battery
* Hardware fault
* Brake issue
* Controller issue
* Manual admin action

Requirements:

Cannot be assigned.

Allowed Next States:

```text
AVAILABLE
OFFLINE
```

---

## OFFLINE

Meaning:

Backend lost communication.

Examples:

* ESP32 offline
* Network failure
* Power loss

Requirements:

Cannot be assigned.

Allowed Next States:

```text
AVAILABLE
MAINTENANCE
```

---

# Transition Rules

| Current     | Next        |
| ----------- | ----------- |
| AVAILABLE   | RESERVED    |
| AVAILABLE   | MAINTENANCE |
| AVAILABLE   | OFFLINE     |
| RESERVED    | IN_USE      |
| RESERVED    | AVAILABLE   |
| RESERVED    | OFFLINE     |
| IN_USE      | DOCKING     |
| IN_USE      | OFFLINE     |
| DOCKING     | CHARGING    |
| DOCKING     | AVAILABLE   |
| DOCKING     | OFFLINE     |
| CHARGING    | AVAILABLE   |
| CHARGING    | MAINTENANCE |
| CHARGING    | OFFLINE     |
| MAINTENANCE | AVAILABLE   |
| MAINTENANCE | OFFLINE     |
| OFFLINE     | AVAILABLE   |
| OFFLINE     | MAINTENANCE |

Everything else:

```text
VEHICLE_INVALID_STATE
```

---

# Assignment Rules

Vehicle may be assigned only if:

```text
AVAILABLE
```

AND

```text
Battery >= Threshold
```

AND

```text
Not Offline
```

AND

```text
Not Maintenance
```

---

# Battery Threshold

Default:

```text
20%
```

Below threshold:

```text
AVAILABLE
```

is forbidden.

Recommended transition:

```text
MAINTENANCE
```

or

```text
CHARGING
```

depending on future operations policy.

---

# Vehicle Ownership Rules

A vehicle can have:

```text
0 active rides
```

or

```text
1 active ride
```

Never:

```text
2 active rides
```

---

# Vehicle Heartbeat

Future hardware integration.

Expected:

```json
{
  "vehicle_id": "S001",
  "battery": 78,
  "gps": {},
  "status": "AVAILABLE"
}
```

Heartbeat interval:

```text
30 seconds
```

Recommended.

---

# Offline Rules

If heartbeat missing:

```text
> 120 seconds
```

Transition:

```text
OFFLINE
```

---

# Admin Actions

Admin may:

```text
Move Vehicle To Maintenance

Restore Vehicle

View Vehicle

Force Offline
```

Admin may NOT:

```text
Force Active Ride

Force Ride Completion
```

Ride Service owns rides.

Vehicle Service owns vehicles.

---

# Related Ride States

Vehicle State

```text
AVAILABLE
```

typically corresponds to:

```text
No Active Ride
```

---

Vehicle State

```text
RESERVED
```

typically corresponds to:

```text
Ride = ASSIGNED
```

---

Vehicle State

```text
IN_USE
```

typically corresponds to:

```text
Ride = ACTIVE
```

---

Vehicle State

```text
DOCKING
```

typically corresponds to:

```text
Ride = END_PENDING
```

---

# Business Invariants

Must never be violated.

1. Vehicle exists in exactly one state.

2. Vehicle can have maximum one active ride.

3. OFFLINE vehicles cannot be assigned.

4. MAINTENANCE vehicles cannot be assigned.

5. CHARGING vehicles cannot be assigned.

6. Vehicle state transitions must follow this document.

7. Ride state and vehicle state must remain consistent.

---

# Future Expansion

Reserved:

* Battery Health Score
* Predictive Maintenance
* GPS Geofencing
* Vehicle Lock State
* Vehicle Firmware Version
* OTA Updates

Excluded from v1.
