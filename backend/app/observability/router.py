import asyncio
import json
import time
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.repository import AdminRepository
from app.admin.service import AdminService
from app.database import get_db
from app.dependencies import require_admin
from app.observability.events import event_bus
from app.response import success_response

router = APIRouter(prefix="/observability", tags=["observability"])

# How often the server pushes each event type down the SSE connection.
# These replace what used to be client-side setInterval() polling — the
# browser now makes exactly one connection (/stream) and receives all three
# kinds of updates (live requests, endpoint stats, founder metrics) through
# it, on the server's own clock instead of the tab's.
STATS_PUSH_INTERVAL_S = 5
FOUNDER_PUSH_INTERVAL_S = 10


@router.get("/stats")
async def get_stats(_: None = Depends(require_admin)):
    """Still exposed as a plain JSON endpoint for scripts/curl/debugging,
    but the dashboard UI itself no longer polls this — see /stream.
    """
    return success_response(event_bus.stats())


@router.get("/recent")
async def get_recent(limit: int = 100, _: None = Depends(require_admin)):
    return success_response(event_bus.recent(limit))


@router.get("/stream")
async def stream(
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """Single Server-Sent Events connection carrying three named event
    types, each pushed on its own server-side timer:

      event: request_event  — one per HTTP request, pushed immediately
      event: stats          — endpoint/latency/error counters, every 5s
      event: founder        — fleet/revenue/user metrics, every 10s

    This is the only connection the dashboard opens. Previously the
    frontend used setInterval() to poll /stats and /admin/dashboard on top
    of this stream, which meant a browser tab left open generated request
    traffic forever. Moving stats/founder pushes onto the server's own
    clock, multiplexed through this one connection, means there is exactly
    one open connection per dashboard tab and zero repeat HTTP requests.
    """
    queue = event_bus.subscribe()
    admin_service = AdminService(AdminRepository(session))

    async def event_generator():
        last_stats_push = 0.0
        last_founder_push = 0.0
        try:
            # Replay recent request history immediately so a newly-opened
            # dashboard isn't empty until the next real request comes in.
            for e in event_bus.recent(50):
                yield f"event: request_event\ndata: {json.dumps(e)}\n\n"

            while True:
                # Wait briefly for a new request event; on timeout, fall
                # through to check whether a periodic push is due. This
                # single loop drives all three event types without extra
                # background tasks to manage/cancel.
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield f"event: request_event\ndata: {json.dumps(event.to_dict())}\n\n"
                except asyncio.TimeoutError:
                    pass

                now = time.time()

                if now - last_stats_push >= STATS_PUSH_INTERVAL_S:
                    yield f"event: stats\ndata: {json.dumps(event_bus.stats())}\n\n"
                    last_stats_push = now

                if now - last_founder_push >= FOUNDER_PUSH_INTERVAL_S:
                    summary = await admin_service.get_dashboard_summary()
                    yield f"event: founder\ndata: {json.dumps(jsonable_encoder(summary))}\n\n"
                    last_founder_push = now
        except asyncio.CancelledError:
            pass
        finally:
            event_bus.unsubscribe(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    """Serves the dashboard UI itself. Auth is enforced by /stream (which
    requires admin credentials via header or query param), not by this
    route, so the page can load and then connect with credentials.
    """
    html_path = Path(__file__).parent / "dashboard.html"
    return HTMLResponse(
        html_path.read_text(encoding="utf-8"),
        media_type="text/html; charset=utf-8",
    )