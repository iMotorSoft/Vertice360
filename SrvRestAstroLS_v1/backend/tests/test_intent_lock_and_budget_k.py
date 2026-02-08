from __future__ import annotations

import asyncio

from backend import globalVar
from backend.modules.vertice360_ai_workflow_demo import store as ai_store
from backend.modules.vertice360_workflow_demo import services, store


def _output_for_message(message_id: str) -> dict:
    run_id = ai_store.inbound_message_index.get(message_id)
    assert run_id
    run = ai_store.get_run(run_id)
    assert run
    return run.get("output") or {}


def test_intent_lock_and_budget_k(monkeypatch):
    monkeypatch.setattr(globalVar, "OpenAI_Key", "")
    monkeypatch.setattr(globalVar, "VERTICE360_AI_WORKFLOW_REPLY", True)
    ai_store.reset_store()
    store.reset_store()

    first = asyncio.run(
        services.process_inbound_message(
            {
                "provider": "meta_whatsapp",
                "channel": "whatsapp",
                "from": "+5491100000009",
                "to": "+5491100000000",
                "messageId": "msg-lock-1",
                "text": "busco depto",
                "timestamp": 1710000600000,
                "mediaCount": 0,
            }
        )
    )
    ticket_id = first.get("ticketId")
    assert ticket_id

    asyncio.run(
        services.process_inbound_message(
            {
                "provider": "meta_whatsapp",
                "channel": "whatsapp",
                "from": "+5491100000009",
                "to": "+5491100000000",
                "messageId": "msg-lock-2",
                "text": "almagro, 3 ambientes",
                "timestamp": 1710000601000,
                "mediaCount": 0,
                "ticketId": ticket_id,
            }
        )
    )

    third = asyncio.run(
        services.process_inbound_message(
            {
                "provider": "meta_whatsapp",
                "channel": "whatsapp",
                "from": "+5491100000009",
                "to": "+5491100000000",
                "messageId": "msg-lock-3",
                "text": "120K usd",
                "timestamp": 1710000602000,
                "mediaCount": 0,
                "ticketId": ticket_id,
            }
        )
    )

    output = _output_for_message("msg-lock-3")
    assert output.get("primaryIntent") == "property_search"

    reply_text = (third.get("replyText") or "").lower()
    assert "puedo ayudarte con disponibilidad" not in reply_text
    assert ("mud" in reply_text) or ("visita" in reply_text)
