from __future__ import annotations

import asyncio

from backend.modules.vertice360_workflow_demo import services


def test_duplicate_outbound_text_is_deduped(event_recorder, mock_meta_send) -> None:
    first = asyncio.run(
        services.process_inbound_message(
            {
                "provider": "meta_whatsapp",
                "channel": "whatsapp",
                "from": "+5491112340777",
                "to": "+5491100000000",
                "messageId": "wamid.dedupe.outbound.1",
                "text": "hi",
                "timestamp": 1711111117000,
                "mediaCount": 0,
            }
        )
    )
    assert "OUTBOUND_SENT" in (first.get("actions") or [])

    second = asyncio.run(
        services.process_inbound_message(
            {
                "provider": "meta_whatsapp",
                "channel": "whatsapp",
                "from": "+5491112340777",
                "to": "+5491100000000",
                "messageId": "wamid.dedupe.outbound.2",
                "text": "hola",
                "timestamp": 1711111118000,
                "mediaCount": 0,
            }
        )
    )

    assert "OUTBOUND_DEDUPED" in (second.get("actions") or [])
    assert len(mock_meta_send) == 1

    outbound_events = [event for event in event_recorder if event.get("name") == "messaging.outbound"]
    assert len(outbound_events) == 1
