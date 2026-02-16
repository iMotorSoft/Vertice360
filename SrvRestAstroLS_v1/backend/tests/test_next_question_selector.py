from __future__ import annotations

import asyncio

from backend.modules.vertice360_workflow_demo import commercial_memory, services, store


def test_next_question_after_zona_ambientes_is_presupuesto() -> None:
    memory = {
        "zona": "Palermo",
        "tipologia": "3 ambientes",
        "presupuesto": None,
        "moneda": None,
        "fecha_mudanza": None,
    }
    missing = commercial_memory.calculate_missing_slots(memory, answered_fields=["zona", "ambientes"])
    question, key = commercial_memory.build_next_best_question(missing)

    assert key == "presupuesto"
    assert question == "¿Cuál es tu presupuesto aproximado y en qué moneda?"


def test_next_question_after_presupuesto_is_mudanza() -> None:
    memory = {
        "zona": "Palermo",
        "tipologia": "3 ambientes",
        "presupuesto": 120000,
        "moneda": "USD",
        "fecha_mudanza": None,
    }
    missing = commercial_memory.calculate_missing_slots(
        memory,
        answered_fields=["zona", "ambientes", "presupuesto"],
    )
    question, key = commercial_memory.build_next_best_question(missing)

    assert key == "fecha_mudanza"
    assert question == "¿Para qué mes y año estimás la mudanza?"


def test_all_slots_complete_sends_summary_once(event_recorder, mock_meta_send) -> None:  # noqa: ARG001
    ticket = asyncio.run(
        store.create_or_get_ticket_from_inbound(
            {
                "ticketId": "VTX-SUMMARY-ONCE",
                "provider": "meta_whatsapp",
                "channel": "whatsapp",
                "customer": {
                    "from": "+5491112340099",
                    "to": "+5491100000000",
                    "provider": "meta_whatsapp",
                    "channel": "whatsapp",
                },
                "subject": "Summary once",
            }
        )
    )

    store.update_ticket_commercial(
        ticket["ticketId"],
        {
            "zona": "Almagro",
            "tipologia": "2 ambientes",
            "presupuesto": 120000,
            "moneda": "USD",
            "fecha_mudanza": "abril 2026",
        },
    )
    slot_memory = ticket["slot_memory"]
    slot_memory["answered_fields"] = ["zona", "ambientes", "presupuesto", "mudanza"]
    slot_memory["summarySent"] = False
    slot_memory["intro_sent"] = True

    first = asyncio.run(
        services.process_inbound_message(
            {
                "ticketId": ticket["ticketId"],
                "provider": "meta_whatsapp",
                "channel": "whatsapp",
                "from": "+5491112340099",
                "to": "+5491100000000",
                "messageId": "wamid.summary.once.1",
                "text": "dale",
                "timestamp": 1711119999000,
                "mediaCount": 0,
            }
        )
    )

    assert "Gracias. Tengo:" in (first.get("replyText") or "")
    assert "¿Querés coordinar visita?" in (first.get("replyText") or "")

    second = asyncio.run(
        services.process_inbound_message(
            {
                "ticketId": ticket["ticketId"],
                "provider": "meta_whatsapp",
                "channel": "whatsapp",
                "from": "+5491112340099",
                "to": "+5491100000000",
                "messageId": "wamid.summary.once.2",
                "text": "hola",
                "timestamp": 1711120000000,
                "mediaCount": 0,
            }
        )
    )

    assert "HANDOFF_SCHEDULING_REPROMPT" in (second.get("actions") or [])
    assert "día y franja horaria" in (second.get("replyText") or "").lower()
    assert len(mock_meta_send) == 2
