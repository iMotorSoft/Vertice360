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


def test_whatsapp_commercial_memory_flow(monkeypatch):
    monkeypatch.setattr(globalVar, "OpenAI_Key", "")
    monkeypatch.setattr(globalVar, "VERTICE360_AI_WORKFLOW_REPLY", True)
    ai_store.reset_store()

    first = asyncio.run(
        services.process_inbound_message(
            {
                "provider": "meta_whatsapp",
                "channel": "whatsapp",
                "from": "+5491112340001",
                "to": "+5491100000000",
                "messageId": "msg-mem-1",
                "text": "Busco depto",
                "timestamp": 1710000500000,
                "mediaCount": 0,
            }
        )
    )
    ticket_id = first.get("ticketId")
    assert ticket_id

    output_first = _output_for_message("msg-mem-1")
    first_question = output_first.get("recommendedQuestion") or output_first.get("responseText") or ""
    assert output_first.get("decision") == "ask_next_best_question"
    assert ("zona" in first_question.lower()) or ("ambiente" in first_question.lower())

    asyncio.run(
        services.process_inbound_message(
            {
                "provider": "meta_whatsapp",
                "channel": "whatsapp",
                "from": "+5491112340001",
                "to": "+5491100000000",
                "messageId": "msg-mem-2",
                "text": "Caballito 3 ambientes",
                "timestamp": 1710000501000,
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
                "from": "+5491112340001",
                "to": "+5491100000000",
                "messageId": "msg-mem-3",
                "text": "USD 120k",
                "timestamp": 1710000502000,
                "mediaCount": 0,
                "ticketId": ticket_id,
            }
        )
    )

    ticket = store.tickets[ticket_id]
    commercial = ticket.get("commercial") or {}
    assert commercial.get("zona") == "Caballito"
    assert commercial.get("tipologia") == "3 ambientes"
    assert commercial.get("presupuesto") == 120000
    assert commercial.get("moneda") == "USD"

    output_third = _output_for_message("msg-mem-3")
    pragmatics = output_third.get("pragmatics") or {}
    missing_slots = pragmatics.get("missingSlots") or {}
    property_missing = missing_slots.get("property_search") or []

    assert "zona" not in property_missing
    assert "tipologia" not in property_missing
    assert "presupuesto" not in property_missing
    assert "moneda" not in property_missing
    assert output_third.get("missingSlotsCount") == 1

    outbound_text = third.get("replyText") or ""
    outbound_lower = outbound_text.lower()
    assert "mud" in outbound_lower
    assert "zona" not in outbound_lower
    assert "ambiente" not in outbound_lower
