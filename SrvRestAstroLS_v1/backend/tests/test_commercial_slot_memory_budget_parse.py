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


def test_commercial_memory_budget_parse(monkeypatch):
    monkeypatch.setattr(globalVar, "OpenAI_Key", "")
    monkeypatch.setattr(globalVar, "VERTICE360_AI_WORKFLOW_REPLY", True)
    ai_store.reset_store()

    inbound_first = {
        "provider": "meta_whatsapp",
        "channel": "whatsapp",
        "from": "+5491112340000",
        "to": "+5491100000000",
        "messageId": "msg-commercial-1",
        "text": "Busco depto en Caballito 3 ambientes",
        "timestamp": 1710000400000,
        "mediaCount": 0,
    }
    first = asyncio.run(services.process_inbound_message(inbound_first))
    ticket_id = first.get("ticketId")
    assert ticket_id

    inbound_budget = {
        "provider": "meta_whatsapp",
        "channel": "whatsapp",
        "from": "+5491112340000",
        "to": "+5491100000000",
        "messageId": "msg-commercial-2",
        "text": "USD 120k",
        "timestamp": 1710000401000,
        "mediaCount": 0,
        "ticketId": ticket_id,
    }
    asyncio.run(services.process_inbound_message(inbound_budget))

    ticket = store.tickets[ticket_id]
    commercial = ticket.get("commercial") or {}
    assert commercial.get("zona") == "Caballito"
    assert commercial.get("tipologia") == "3 ambientes"
    assert commercial.get("presupuesto") == 120000
    assert commercial.get("moneda") == "USD"

    output = _output_for_message("msg-commercial-2")
    pragmatics = output.get("pragmatics") or {}
    missing_slots = pragmatics.get("missingSlots") or {}
    property_missing = missing_slots.get("property_search") or []

    assert "zona" not in property_missing
    assert "tipologia" not in property_missing
    assert output.get("missingSlotsCount") == 1

    question = output.get("recommendedQuestion") or output.get("responseText") or ""
    question_lower = question.lower()
    assert "mud" in question_lower
    assert "zona" not in question_lower
    assert "ambiente" not in question_lower
