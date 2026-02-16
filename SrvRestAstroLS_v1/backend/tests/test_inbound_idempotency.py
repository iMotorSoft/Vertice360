from __future__ import annotations

import asyncio

from backend.modules.vertice360_workflow_demo import services


def test_same_inbound_processed_once(event_recorder, mock_meta_send) -> None:
    inbound = {
        "provider": "meta_whatsapp",
        "channel": "whatsapp",
        "from": "+5491112340001",
        "to": "+5491100000000",
        "messageId": "wamid.idempotency.1",
        "text": "Hola",
        "timestamp": 1711111111000,
        "mediaCount": 0,
    }

    first = asyncio.run(services.process_inbound_message(dict(inbound)))
    second = asyncio.run(services.process_inbound_message(dict(inbound)))

    assert first.get("duplicate") is not True
    assert second.get("duplicate") is True
    assert second.get("actions") == ["DUPLICATE_INBOUND_IGNORED"]

    assert len(mock_meta_send) == 1
    outbound_events = [event for event in event_recorder if event.get("name") == "messaging.outbound"]
    assert len(outbound_events) == 1
