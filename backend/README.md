# Velo Backend

FastAPI modular-monolith backend for the **Velo** smart micromobility platform. The project combines authentication, ride management, wallet, fleet management, payments, notifications, and admin dashboards into a single backend.

## Tech Stack

- **FastAPI** + **SQLAlchemy 2 (Async)** + **asyncpg**
- **PostgreSQL 16**
- **Redis**
- **Firebase Admin SDK** (Phone Authentication + FCM)
- **Razorpay** (Wallet top-ups)
- **Alembic** (Database migrations)
- **python-jose** (JWT authentication)
- **slowapi** (Rate limiting)
- **pytest + pytest-asyncio**

---

# Project Structure

```
app/
├── main.py         create_app() factory, exception handlers, router mounting
├── config.py       Environment-based settings
├── database.py     Engine, session factory, Base
├── types.py        Cross-dialect GUID type
├── core/           Security, JWT, Firebase, helpers
├── auth/           Authentication
├── ride/           Ride lifecycle
├── dock/           Dock & vehicle management
├── wallet/         Wallet & transactions
├── payments/       Razorpay integration
├── notifications/  Push notifications
├── admin/          Admin APIs
├── audit/          Audit logging
└── models/         SQLAlchemy models
```

Each feature follows the same architecture:

```
Router
   ↓
Service
   ↓
Repository
   ↓
Database
```

---

# Ride Flow

```
User App
    │
    │ POST /rides/token
    ▼
Ride Token (30s)

    │
    │ POST /rides/confirm
    ▼
Ride ACTIVE

    │
    │ POST /rides/{id}/end
    ▼
Ride COMPLETED

    │
    ▼
Wallet Debited
```

Fare calculation:

- ₹2 / minute
- Minimum fare: ₹5

---

# Wallet Top-up Flow

```
User
   │
   │ POST /payments/orders
   ▼
Razorpay Order

   │
   │ Payment
   ▼

Razorpay Webhook
   │
   ▼
Wallet Credited
```

Wallet credits occur **only** after a valid Razorpay webhook is received.

> **Note**
>
> `/wallet/topup` exists only for development/testing and should be disabled or admin-protected before production.

---

# Security

- Firebase phone authentication
- JWT access tokens (15 min)
- Refresh token rotation
- Ride tokens (30 seconds)
- Role-based authorization
- Rate limiting
- Audit logging
- Database-level constraints
- Security headers
- ORM-only queries (no raw SQL)

---

# Local Development

## Prerequisites

Install:

- Python 3.12+
- Docker Desktop (recommended)
- Git

Clone the repository:

```bash
git clone <repository-url>
cd Velo-/backend
```

---

# Environment Setup

Copy the example environment file:

```bash
cp .env.example .env
```

Update the required values inside `.env`.

Important settings include:

- Database
- Redis
- JWT keys
- Firebase
- Razorpay (optional for development)

---

# Running with Docker (Recommended)

Move into the Docker directory:

```bash
cd docker
```

Start all services:

```bash
docker compose up -d
```

Run database migrations:

```bash
docker compose exec backend alembic upgrade head
```

Verify the services:

```bash
docker compose ps
```

Open Swagger UI:

```
http://localhost:8000/docs
```

Health endpoint:

```
http://localhost:8000/health
```

---

## Docker Development Workflow

The backend source code is bind-mounted into the container.

```yaml
volumes:
  - ../:/app
```

This means:

- Changes made locally are immediately visible inside the container.
- New Alembic migrations are created directly inside your repository.
- No files need to be copied from the container.

---

# Running without Docker

Create a virtual environment:

```bash
python -m venv .venv
```

Linux/macOS

```bash
source .venv/bin/activate
```

Windows

```powershell
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements/dev.txt
```

Copy the environment file:

```bash
cp .env.example .env
```

Run migrations:

```bash
alembic upgrade head
```

Start the server:

```bash
uvicorn app.main:app --reload
```

---

# Database Migrations

Generate a migration after modifying SQLAlchemy models.

Local:

```bash
alembic revision --autogenerate -m "add vehicle status"
```

Docker:

```bash
docker compose exec backend \
alembic revision --autogenerate -m "add vehicle status"
```

Apply migrations:

Local:

```bash
alembic upgrade head
```

Docker:

```bash
docker compose exec backend alembic upgrade head
```

Check migration status:

```bash
docker compose exec backend alembic current
```

View migration history:

```bash
docker compose exec backend alembic history
```

---

# Alembic & GUID

This project uses a custom SQLAlchemy UUID type:

```python
from app.types import GUID
```

Occasionally Alembic autogeneration may render:

```python
app.types.GUID()
```

instead of

```python
GUID()
```

If that happens:

1. Add

```python
from app.types import GUID
```

to the migration.

2. Replace every occurrence of

```python
app.types.GUID()
```

with

```python
GUID()
```

This is an Alembic limitation with custom `TypeDecorator` classes and does **not** affect runtime behavior.

---

# Resetting the Database

Delete everything:

```bash
docker compose down -v
```

Start fresh:

```bash
docker compose up -d
```

Recreate the schema:

```bash
docker compose exec backend alembic upgrade head
```

---

# Running Tests

```bash
pytest tests/ -v
```

Current test suite uses SQLite.

> **Known limitation**
>
> SQLite does not support `SELECT ... FOR UPDATE`, so row-locking behavior cannot be fully tested. PostgreSQL integration tests should be added before production deployment.

---

# Useful Docker Commands

Start services

```bash
docker compose up -d
```

Stop services

```bash
docker compose down
```

Restart services

```bash
docker compose restart
```

Backend logs

```bash
docker compose logs -f backend
```

PostgreSQL shell

```bash
docker compose exec postgres psql -U postgres scooter_db
```

Redis CLI

```bash
docker compose exec redis redis-cli
```

Current migration

```bash
docker compose exec backend alembic current
```

Migration history

```bash
docker compose exec backend alembic history
```

Generate migration

```bash
docker compose exec backend alembic revision --autogenerate -m "message"
```

Apply migrations

```bash
docker compose exec backend alembic upgrade head
```

---

# API Documentation

Interactive API documentation is available after starting the backend.

Swagger UI

```
http://localhost:8000/docs
```

OpenAPI JSON

```
http://localhost:8000/openapi.json
```

---

# API Endpoints

| Method | Endpoint | Auth | Description |
|---------|----------|------|-------------|
| POST | `/api/v1/auth/login` | — | Firebase OTP login |
| POST | `/api/v1/auth/refresh` | — | Refresh access token |
| POST | `/api/v1/auth/logout` | — | Logout |
| GET | `/api/v1/auth/me` | User | Current user |
| PATCH | `/api/v1/auth/me` | User | Update profile |
| GET | `/api/v1/docks` | Public | List docks |
| GET | `/api/v1/docks/{id}` | Public | Dock details |
| POST | `/api/v1/docks` | Admin | Create dock |
| PATCH | `/api/v1/docks/{id}` | Admin | Update dock |
| GET | `/api/v1/docks/vehicles/all` | Admin | List vehicles |
| POST | `/api/v1/docks/vehicles` | Admin | Create vehicle |
| PATCH | `/api/v1/docks/vehicles/{id}` | Admin | Update vehicle |
| POST | `/api/v1/rides/token` | User | Request ride token |
| POST | `/api/v1/rides/confirm` | Ride Token | Confirm ride |
| POST | `/api/v1/rides/{id}/end` | User | End ride |
| GET | `/api/v1/rides/active` | User | Active ride |
| GET | `/api/v1/rides` | User | Ride history |
| GET | `/api/v1/rides/{id}` | User | Ride details |
| GET | `/api/v1/wallet` | User | Wallet balance |
| POST | `/api/v1/wallet/topup` | User | Development top-up |
| GET | `/api/v1/wallet/transactions` | User | Transaction history |
| POST | `/api/v1/wallet/admin/adjust` | Admin | Admin adjustment |
| POST | `/api/v1/payments/orders` | User | Razorpay order |
| POST | `/api/v1/payments/webhook` | Signature | Razorpay webhook |
| POST | `/api/v1/notifications/device-token` | User | Register FCM token |
| GET | `/api/v1/notifications` | User | Notifications |
| GET | `/api/v1/admin/stats/dashboard` | Admin | Dashboard |
| GET | `/api/v1/admin/stats/fleet` | Admin | Fleet statistics |
| GET | `/api/v1/admin/stats/revenue` | Admin | Revenue statistics |
| GET | `/api/v1/admin/stats/users` | Admin | User statistics |
| GET | `/api/v1/admin/users` | Admin | Users |
| GET | `/api/v1/admin/users/{id}` | Admin | User details |
| PATCH | `/api/v1/admin/users/{id}/role` | Admin | Change role |
| PATCH | `/api/v1/admin/users/{id}/active` | Admin | Activate/deactivate user |
| GET | `/api/v1/admin/audit-logs` | Admin | Audit logs |
| GET | `/api/v1/admin/rides` | Admin | Ride management |
| GET | `/health` | — | Health check |

---

# Additional Documentation

See:

```
MERGE_CONFLICT_RESOLUTION.md
```

for details about how the Track A and Track B branches were merged into the final backend.