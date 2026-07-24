"""Captures every HTTP request/response as a RequestEvent and publishes it
to the event bus. Add this once in app/main.py — it wraps every route in
the app automatically, no per-endpoint code needed.
"""
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.observability.events import RequestEvent, event_bus


class RequestTrackingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        latency_ms = (time.perf_counter() - start) * 1000

        # Best-effort: our error_response() envelope always has this shape
        # on failure; we peek at it without consuming the actual response
        # stream the client will still receive.
        error_code = None
        if response.status_code >= 400:
            error_code = getattr(response, "_observability_error_code", None)

        event_bus.publish(
            RequestEvent(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                latency_ms=round(latency_ms, 2),
                user_id=request.headers.get("x-debug-user-id"),
                error_code=error_code,
            )
        )
        return response
