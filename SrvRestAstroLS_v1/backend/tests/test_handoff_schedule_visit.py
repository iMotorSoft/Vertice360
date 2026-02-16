from __future__ import annotations

import asyncio

from backend import globalVar
from backend.modules.vertice360_ai_workflow_demo import services, store
from backend.modules.vertice360_ai_workflow_demo.langgraph_flow import SCHEDULE_VISIT_FIXED_REPLY


def test_schedule_visit_handoff_emits_action_required(event_recorder, monkeypatch) -> None:
    monkeypatch.setattr(globalVar, "OpenAI_Key", "")
    store.reset_store()

    result = asyncio.run(
        services.run_workflow(
            "vertice360-ai-workflow",
            "¿Querés coordinar visita? Decime día y franja horaria.",
            metadata={"ticketId": "VTX-4242"},
            context={
                "provider": "gupshup_whatsapp",
                "commercialSlots": {
                    "zona": "Palermo",
                    "tipologia": "3 ambientes",
                    "presupuesto": 120000,
                    "moneda": "USD",
                    "fecha_mudanza": "abril 2026",
                },
            },
        )
    )

    output = result.get("output") or {}
    assert output.get("responseText") == SCHEDULE_VISIT_FIXED_REPLY
    assert output.get("handoffRequired") is True

    handoff_event = next(
        (event for event in event_recorder if event.get("name") == "human.action_required"),
        None,
    )
    assert handoff_event is not None

    value = handoff_event.get("value") or {}
    assert value.get("reason") == "schedule_visit"
    assert value.get("ticket_id") == "VTX-4242"
    assert value.get("provider") == "gupshup"
    assert value.get("summary") == {
        "zona": "Palermo",
        "ambientes": 3,
        "presupuesto_usd": 120000,
        "mudanza": "2026-04",
    }
