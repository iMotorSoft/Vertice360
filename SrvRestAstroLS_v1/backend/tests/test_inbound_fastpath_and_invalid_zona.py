from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from backend.modules.vertice360_workflow_demo import services, store


def test_fast_path_greeting_skips_llm() -> None:
    sender = "5491111111111"
    llm_mock = AsyncMock(return_value={"decision": "ask_next_best_question"})
    services._run_ai_workflow_reply = llm_mock

    result = asyncio.run(
        services.process_inbound_message(
            {
                "provider": "meta_whatsapp",
                "channel": "whatsapp",
                "from": sender,
                "to": "5491100000000",
                "messageId": "fastpath-1",
                "text": "hola",
                "timestamp": 1711111111000,
                "mediaCount": 0,
            }
        )
    )

    assert "¿Por qué zona buscás y cuántos ambientes necesitás?" in (
        result.get("replyText") or ""
    )
    assert llm_mock.await_count == 0


def test_invalid_zona_is_rejected_and_valid_zona_is_accepted() -> None:
    sender = "5491222333444"
    services._run_ai_workflow_reply = AsyncMock(return_value=None)

    asyncio.run(
        services.process_inbound_message(
            {
                "provider": "meta_whatsapp",
                "channel": "whatsapp",
                "from": sender,
                "to": "5491100000000",
                "messageId": "zona-1",
                "text": "hola",
                "timestamp": 1711111111001,
                "mediaCount": 0,
            }
        )
    )

    second = asyncio.run(
        services.process_inbound_message(
            {
                "provider": "meta_whatsapp",
                "channel": "whatsapp",
                "from": sender,
                "to": "5491100000000",
                "messageId": "zona-2",
                "text": "bolivia",
                "timestamp": 1711111111002,
                "mediaCount": 0,
            }
        )
    )
    ticket = store._find_active_ticket_by_phone(sender)
    assert ticket is not None
    assert ticket.get("commercial", {}).get("zona") is None
    assert "CABA/GBA" in (second.get("replyText") or "")

    third = asyncio.run(
        services.process_inbound_message(
            {
                "provider": "meta_whatsapp",
                "channel": "whatsapp",
                "from": sender,
                "to": "5491100000000",
                "messageId": "zona-3",
                "text": "palermo",
                "timestamp": 1711111111003,
                "mediaCount": 0,
            }
        )
    )
    assert ticket.get("commercial", {}).get("zona") == "Palermo"
    assert "¿Cuántos ambientes necesitás?" in (third.get("replyText") or "")


def test_rapid_greetings_keep_single_coherent_outbound() -> None:
    sender = "5491333444555"
    services._run_ai_workflow_reply = AsyncMock(return_value=None)

    async def _run() -> None:
        await asyncio.gather(
            services.process_inbound_message(
                {
                    "provider": "meta_whatsapp",
                    "channel": "whatsapp",
                    "from": sender,
                    "to": "5491100000000",
                    "messageId": "rapid-1",
                    "text": "hola",
                    "timestamp": 1711111112001,
                    "mediaCount": 0,
                }
            ),
            services.process_inbound_message(
                {
                    "provider": "meta_whatsapp",
                    "channel": "whatsapp",
                    "from": sender,
                    "to": "5491100000000",
                    "messageId": "rapid-2",
                    "text": "hi",
                    "timestamp": 1711111112002,
                    "mediaCount": 0,
                }
            ),
            services.process_inbound_message(
                {
                    "provider": "meta_whatsapp",
                    "channel": "whatsapp",
                    "from": sender,
                    "to": "5491100000000",
                    "messageId": "rapid-3",
                    "text": "hi",
                    "timestamp": 1711111112003,
                    "mediaCount": 0,
                }
            ),
        )

    asyncio.run(_run())

    ticket = store._find_active_ticket_by_phone(sender)
    assert ticket is not None
    outbound_messages = [
        msg for msg in (ticket.get("messages") or []) if msg.get("direction") == "outbound"
    ]
    assert len(outbound_messages) == 1
    assert "zona" in str(outbound_messages[0].get("text") or "").lower()
