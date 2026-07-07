"""Temporary development authentication for Track B.

See setup.md section 5 for full context. Trusts an X-Debug-User-Id header
with zero verification. Replace with real JWT decoding once Track A's
auth is merged. Never deploy this outside your own machine.
"""
import uuid

from fastapi import Header, HTTPException


def get_current_user_id(
    x_debug_user_id: str | None = Header(default=None, alias="X-Debug-User-Id"),
) -> uuid.UUID:
    if not x_debug_user_id:
        raise HTTPException(
            status_code=401,
            detail=(
                "Missing X-Debug-User-Id header. This is a temporary dev-only "
                "auth stub — see app/dependencies.py for why, and replace it "
                "once Track A's real auth is wired in."
            ),
        )
    try:
        return uuid.UUID(x_debug_user_id)
    except ValueError:
        raise HTTPException(
            status_code=401, detail="X-Debug-User-Id must be a valid UUID, e.g. 11111111-1111-1111-1111-111111111111"
        )


def require_admin(
    x_debug_role: str | None = Header(default=None, alias="X-Debug-Role"),
) -> None:
    """Very thin dev-only admin gate for the Admin Dashboard endpoints.

    Real deployments must replace this with a role claim decoded from the
    JWT (Track A's `role` field on User — see docs/database/auth_schema.md).
    For now, admin endpoints require the header `X-Debug-Role: ADMIN` in
    addition to X-Debug-User-Id, so at least a stray script can't hit
    fleet-wide stats by accident.
    """
    if x_debug_role != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="This endpoint requires X-Debug-Role: ADMIN (dev stub — replace with real role check).",
        )
