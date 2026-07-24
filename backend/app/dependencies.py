"""Temporary development authentication for Track B.

See setup.md section 5 for full context. Trusts an X-Debug-User-Id header
with zero verification. Replace with real JWT decoding once Track A's
auth is merged. Never deploy this outside your own machine.

Query-param fallback
---------------------
Browsers' EventSource API (used for the observability SSE stream) cannot
send custom headers on its request. So both dependencies below also accept
the same values as query params (?user_id=...&role=...) as a fallback when
the header is absent. This is only used by the /observability/stream
route today. Header-based auth remains the primary path for every normal
JSON endpoint (wallet, dock, admin) and is unaffected by this change.
"""
import uuid

from fastapi import Header, HTTPException, Query


def get_current_user_id(
    x_debug_user_id: str | None = Header(default=None, alias="X-Debug-User-Id"),
    user_id: str | None = Query(default=None),
) -> uuid.UUID:
    raw = x_debug_user_id or user_id
    if not raw:
        raise HTTPException(
            status_code=401,
            detail=(
                "Missing X-Debug-User-Id header (or user_id query param). This is a "
                "temporary dev-only auth stub — see app/dependencies.py for why, and "
                "replace it once Track A's real auth is wired in."
            ),
        )
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise HTTPException(
            status_code=401, detail="user id must be a valid UUID, e.g. 11111111-1111-1111-1111-111111111111"
        )


def require_admin(
    x_debug_role: str | None = Header(default=None, alias="X-Debug-Role"),
    role: str | None = Query(default=None),
) -> None:
    """Very thin dev-only admin gate for the Admin Dashboard / observability
    endpoints.

    Real deployments must replace this with a role claim decoded from the
    JWT (Track A's `role` field on User — see docs/database/auth_schema.md).
    Accepts X-Debug-Role header OR ?role= query param (see module docstring
    for why the query param exists).
    """
    if (x_debug_role or role) != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail=(
                "This endpoint requires X-Debug-Role: ADMIN (header) or ?role=ADMIN "
                "(query param) — dev stub, replace with real role check."
            ),
        )