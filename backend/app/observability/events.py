"""In-memory event bus + ring buffer for request observability.

Not a queue/broker — this is intentionally simple: a bounded deque holding
the last N request events, plus a set of asyncio.Queues (one per connected
SSE client) that get a copy of every new event pushed to them in real time.

This is process-local. If you ever run multiple uvicorn workers, each
worker will have its own independent buffer/subscribers — the dashboard
will only show traffic that happened to land on the worker it's connected
to. That's fine for a single-instance Oracle/Hetzner deployment (per the
architecture doc's MVP/pilot stages); if you scale to multiple workers
before adding Redis, switch this to a Redis pub/sub channel instead — the
publish/subscribe interface below is written so that swap only touches
this file.
"""
import asyncio
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RequestEvent:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    timestamp: float = field(default_factory=time.time)
    method: str = ""
    path: str = ""
    status_code: int = 0
    latency_ms: float = 0.0
    user_id: str | None = None
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EventBus:
    def __init__(self, max_events: int = 500) -> None:
        self._buffer: deque[RequestEvent] = deque(maxlen=max_events)
        self._subscribers: set[asyncio.Queue] = set()
        # Rolling stats since process start. Reset on restart — fine for a
        # dev/ops dashboard; wire to a real metrics store (Prometheus) later
        # if you need historical data across restarts.
        self.endpoint_counts: dict[str, int] = {}
        self.status_counts: dict[int, int] = {}
        self.error_code_counts: dict[str, int] = {}
        self.latencies: deque[float] = deque(maxlen=1000)

    def publish(self, event: RequestEvent) -> None:
        self._buffer.append(event)

        key = f"{event.method} {event.path}"
        self.endpoint_counts[key] = self.endpoint_counts.get(key, 0) + 1
        self.status_counts[event.status_code] = self.status_counts.get(event.status_code, 0) + 1
        if event.error_code:
            self.error_code_counts[event.error_code] = self.error_code_counts.get(event.error_code, 0) + 1
        self.latencies.append(event.latency_ms)

        dead = []
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._subscribers.discard(q)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        return [e.to_dict() for e in list(self._buffer)[-limit:]]

    def stats(self) -> dict[str, Any]:
        sorted_latencies = sorted(self.latencies)
        p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)] if sorted_latencies else 0
        avg = sum(self.latencies) / len(self.latencies) if self.latencies else 0
        slowest_endpoint = None
        if self.endpoint_counts:
            # crude "slowest" proxy: endpoint whose most recent event had
            # the highest latency in the buffer.
            per_endpoint_latency: dict[str, float] = {}
            for e in self._buffer:
                key = f"{e.method} {e.path}"
                per_endpoint_latency[key] = max(per_endpoint_latency.get(key, 0), e.latency_ms)
            if per_endpoint_latency:
                slowest_endpoint = max(per_endpoint_latency, key=per_endpoint_latency.get)

        return {
            "endpoint_counts": self.endpoint_counts,
            "status_counts": {str(k): v for k, v in self.status_counts.items()},
            "error_code_counts": self.error_code_counts,
            "avg_latency_ms": round(avg, 1),
            "p95_latency_ms": round(p95, 1),
            "slowest_endpoint": slowest_endpoint,
            "total_requests": sum(self.endpoint_counts.values()),
        }


# Single process-wide instance. Imported by the middleware and the router.
event_bus = EventBus()