"""Simple in-memory broadcaster for AG-UI Server-Sent Events."""

from __future__ import annotations

import asyncio
import json
from typing import Any


def format_sse_message(event_type: str, payload: dict[str, Any]) -> str:
    """Render a minimal SSE message with ``event`` and JSON ``data`` lines."""
    data = json.dumps(payload, separators=(",", ":"))
    return f"event: {event_type}\ndata: {data}\n\n"


class AGUIBroadcaster:
    """Global multi-subscriber broadcaster for AG-UI SSE events."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[str]] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue[str]:
        """Register a new subscriber and return its queue."""
        queue: asyncio.Queue[str] = asyncio.Queue()
        async with self._lock:
            self._subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        """Remove a subscriber queue when the stream closes."""
        async with self._lock:
            self._subscribers.discard(queue)

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        """Broadcast an event payload to all subscribers."""
        message = format_sse_message(event_type, payload)
        async with self._lock:
            subscribers = list(self._subscribers)
        for queue in subscribers:
            await queue.put(message)

    async def publish_raw(self, message: str) -> None:
        """Broadcast a pre-rendered SSE message to all subscribers."""
        async with self._lock:
            subscribers = list(self._subscribers)
        for queue in subscribers:
            await queue.put(message)

    def subscriber_count(self) -> int:
        return len(self._subscribers)


broadcaster = AGUIBroadcaster()

