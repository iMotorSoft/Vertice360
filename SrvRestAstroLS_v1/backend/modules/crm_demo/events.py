from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from backend.modules.agui_stream import broadcaster


def _epoch_ms() -> int:
    return int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)


def envelope(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "CUSTOM",
        "timestamp": _epoch_ms(),
        "name": event_type,
        "value": payload,
        "correlationId": str(uuid.uuid4()),
    }


async def publish(event_type: str, payload: dict[str, Any]) -> None:
    await broadcaster.publish(event_type, envelope(event_type, payload))
