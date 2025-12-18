from __future__ import annotations

import asyncio
import time
from typing import AsyncGenerator

from litestar import Request, get, post, route
from litestar.response import Response, Stream
from pydantic import BaseModel

from backend.modules.agui_stream.broadcaster import broadcaster

BASE_SSE_HEADERS = {
    "Content-Type": "text/event-stream; charset=utf-8",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}
ALLOWED_ORIGINS = {"http://localhost:3062", "http://127.0.0.1:3062"}


def build_sse_headers(origin: str | None) -> dict[str, str]:
    """Clone base headers and apply explicit CORS for SSE."""
    headers = dict(BASE_SSE_HEADERS)
    allow_origin = origin if origin and origin in ALLOWED_ORIGINS else "http://localhost:3062"
    headers.update(
        {
            "Access-Control-Allow-Origin": allow_origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Accept, Content-Type, Authorization, Cache-Control, Last-Event-ID, X-Requested-With",
            "Vary": "Origin",
        }
    )
    return headers


@get("/api/agui/stream", media_type="text/event-stream", status_code=200)
async def agui_stream(request: Request) -> Stream:
    """Global AG-UI Server-Sent Events stream."""

    async def event_publisher() -> AsyncGenerator[str, None]:
        queue = await broadcaster.subscribe()
        try:
            # 1. Handshake immediately
            yield ": connected\n\n"

            while True:
                try:
                    # 2. Wait for message or timeout for heartbeat
                    message = await asyncio.wait_for(queue.get(), timeout=20.0)
                    yield message
                except asyncio.TimeoutError:
                    # 3. Heartbeat
                    yield ": ping\n\n"
        except asyncio.CancelledError:  # pragma: no cover - transport driven
            raise
        finally:
            await broadcaster.unsubscribe(queue)

    headers = build_sse_headers(request.headers.get("origin"))
    return Stream(content=event_publisher, media_type="text/event-stream", headers=headers)


@route("/api/agui/stream", http_method=["OPTIONS"])
async def agui_stream_preflight(request: Request) -> Response:
    """Explicit CORS preflight for SSE endpoint."""
    headers = build_sse_headers(request.headers.get("origin"))
    return Response(status_code=204, headers=headers)


# --- Debug / Verification ---

class TriggerRequest(BaseModel):
    name: str = "task.created"
    value: dict | None = None


@post("/api/agui/debug/trigger")
async def debug_trigger_event(data: TriggerRequest) -> dict[str, str]:
    """Manually dispatch an SSE event for testing/validation."""
    # Default mock value if none provided
    val = data.value
    if not val:
        val = {
            "id": f"demo-debug-{int(time.time())}",
            "title": "Debug Task from CURL",
            "leadId": "lead-1",
            "stageId": "stage-contacted",
            "dueAt": "2025-12-31T12:00:00Z"
        }

    payload = {
        "type": "CUSTOM",
        "name": data.name,
        "value": val,
        "timestamp": int(time.time() * 1000)
    }

    # Broadcast to all connected clients
    await broadcaster.publish(data.name, payload)
    
    return {
        "status": "published",
        "event_name": data.name,
        "subscribers": str(broadcaster.subscriber_count())
    }
