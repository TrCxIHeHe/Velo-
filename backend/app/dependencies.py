"""
Temporary development authentication for Track B.

WHY THIS FILE EXISTS
--------------------
Every wallet/dock endpoint needs to know "which user is calling this?"
That's Track A's job (Firebase login -> JWT access token -> decode it).
Track A isn't finished/merged yet, but Track B can't sit idle waiting —
so this file gives you a *fake but explicit* stand-in.

Your original app/wallet/router.py had this instead:

    def get_current_user_id() -> UUID:
        raise NotImplementedError(...)

which means EVERY wallet endpoint would 500 immediately, even after you
fixed the file-placement problem and got migrations running. That is
why nothing could actually be tested end-to-end last session.

HOW IT WORKS RIGHT NOW (dev only)
----------------------------------
The caller sends a header:

    X-Debug-User-Id: <any UUID>

...and we trust it with zero verification. This is intentionally
insecure. It exists purely so you can hit /api/v1/wallet endpoints
with curl/Postman and prove the wallet logic works, without waiting
on Track A.

DO NOT deploy this anywhere reachable from the internet.

WHEN TRACK A'S REAL AUTH LANDS
--------------------------------
Replace the body of get_current_user_id with something like:

    from fastapi import Depends
    from fastapi.security import HTTPBearer
    from app.core.jwt import JWTService  # Track A's module

    bearer = HTTPBearer()

    def get_current_user_id(creds = Depends(bearer)) -> uuid.UUID:
        payload = JWTService().decode_access_token(creds.credentials)
        return uuid.UUID(payload["sub"])

Nothing in app/wallet/ or app/dock/ needs to change when you do this —
they only import `get_current_user_id` from here and call it as a
FastAPI dependency. Swap the implementation in one place, everything
downstream keeps working.
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
