# ADR-001

Title:
Authentication Service Final Decisions

Status:
Accepted

Date:
2026-06-24

Decisions:

1. Firebase Phone Authentication

2. JWT Access Token
   Lifetime: 15 minutes

3. Refresh Token
   Lifetime: 30 days

4. Refresh Token Rotation
   Required

5. Refresh Token Family Tracking
   Required

6. Refresh Token Reuse Detection
   Required

7. Refresh Tokens Stored As Hashes

8. Logout Endpoint Required

9. Health Endpoint Required

10. Phone Number Source:
    Firebase ID Token Only

11. Modular Monolith Architecture

12. Single FastAPI Application

13. PostgreSQL Source Of Truth