# docs/api/common.md

# API Standards and Conventions

Version: v1

Status: Approved

---

# Overview

This document defines the standards that every API in the platform must follow.

All services must comply with these rules.

Services:

* Authentication Service
* User Service
* Ride Service
* Vehicle Service
* Dock Service
* Wallet Service
* Notification Service
* Admin Service

---

# Base URL

Development:

```http
http://localhost:8000/api/v1
```

Production:

```http
https://api.company.com/api/v1
```

---

# API Versioning

All endpoints must be versioned.

Correct:

```http
/api/v1/auth/me
/api/v1/auth/refresh
/api/v1/user/profile
```

Incorrect:

```http
/auth/me
/auth/refresh
/user/profile
```

---

# Versioning Policy

Rules:

1. Breaking changes require a new API version.
2. Existing versions remain supported for at least 6 months after a new version is released.
3. New fields may be added to responses without changing version.
4. Existing fields may not be renamed or removed in the same version.

---

# Authentication

Phone numbers must only be accepted from a verified Firebase ID Token.

Backend services must never trust a client-supplied phone number during authentication.

Firebase is the source of truth for phone verification.

Protected endpoints require:

```http
Authorization: Bearer <access_token>
```

Missing token:

```http
401 Unauthorized
```

Invalid token:

```http
401 Unauthorized
```

Expired token:

```http
401 Unauthorized
```

---

# Success Response Format

All successful responses must follow:

```json
{
  "success": true,
  "data": {}
}
```

Example:

```json
{
  "success": true,
  "data": {
    "user_id": "123"
  }
}
```

---

# Error Response Format

All error responses must follow:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message"
  }
}
```

Example:

```json
{
  "success": false,
  "error": {
    "code": "AUTH_INVALID_TOKEN",
    "message": "Access token is invalid"
  }
}
```

---

# HTTP Status Codes

200 OK

201 Created

400 Bad Request

401 Unauthorized

403 Forbidden

404 Not Found

409 Conflict

422 Validation Error

429 Too Many Requests

500 Internal Server Error

---

# Error Code Convention

Format:

```text
<SERVICE>_<ERROR>
```

Examples:

AUTH_INVALID_OTP

AUTH_EXPIRED_TOKEN

RIDE_ALREADY_ACTIVE

DOCK_OFFLINE

WALLET_INSUFFICIENT_FUNDS

---

# Roles

Supported Roles:

USER

ADMIN

---

# User Constraints

Rules:

1. One phone number per account
2. One Firebase UID per account
3. One active ride per user
4. Users must be authenticated before ride creation

---

# Timestamp Format

All timestamps:

ISO 8601 UTC

Example:

```json
{
  "created_at": "2026-06-24T12:30:00Z"
}
```

---

# UUID Usage

All primary identifiers should use UUIDs.

Examples:

user_id

ride_id

dock_id

vehicle_id

transaction_id

---

# Pagination Standard

Future endpoints:

```json
{
  "success": true,
  "data": {
    "items": [],
    "page": 1,
    "page_size": 20,
    "total": 200
  }
}
```

---

# Security Standards

Access Token:
15 minutes

Refresh Token:
30 days

Refresh Token Rotation:
Mandatory

Refresh Token Reuse Detection:
Mandatory

Refresh Token Family Tracking:
Mandatory

Refresh Token Storage:
Hashed only

HTTPS:
Mandatory in production

---

# Official Auth Phase 1 Contract

The following endpoints are the approved Phase 1 auth contract:

POST /api/v1/auth/login

POST /api/v1/auth/refresh

POST /api/v1/auth/logout

GET /api/v1/auth/me

PATCH /api/v1/auth/me

GET /api/v1/health

---

# Deprecation Policy

Deprecated endpoints:

1. Must be documented
2. Must remain available for minimum 6 months
3. Must provide migration guidance
