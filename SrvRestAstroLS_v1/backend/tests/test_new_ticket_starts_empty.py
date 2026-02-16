from __future__ import annotations

import asyncio
import time

from backend.modules.vertice360_workflow_demo import services, store


def _seed_ticket(ticket_id: str, phone: str) -> dict:
    return asyncio.run(
        store.create_or_get_ticket_from_inbound(
            {
                "ticketId": ticket_id,
                "provider": "meta_whatsapp",
                "channel": "whatsapp",
                "timestamp": int(time.time() * 1000),
                "text": "seed",
                "customer": {
                    "from": phone,
                    "to": "+5491100000000",
                    "provider": "meta_whatsapp",
                    "channel": "whatsapp",
                },
                "subject": "seed ticket",
            }
        )
    )


def test_new_ticket_from_explicit_reset_starts_empty_and_asks_first_question(mock_meta_send) -> None:
    phone = "+5491112399999"
    old = _seed_ticket("VTX-OLD-HI-001", phone)
    store.update_ticket_commercial(
        old["ticketId"],
        {
            "zona": "Almagro",
            "tipologia": "2 ambientes",
            "presupuesto": 120000,
            "moneda": "USD",
            "fecha_mudanza": "abril 2026",
        },
    )

    result = asyncio.run(
        services.process_inbound_message(
            {
                "provider": "meta_whatsapp",
                "channel": "whatsapp",
                "from": phone,
                "to": "+5491100000000",
                "messageId": "wamid.new.ticket.empty.1",
                "text": "reiniciar",
                "timestamp": int(time.time() * 1000),
            }
        )
    )

    assert result["ticketId"] != old["ticketId"]
    reply = result.get("replyText") or ""
    assert "Gracias. Tengo:" not in reply
    assert "¿Por qué zona buscás y cuántos ambientes necesitás?" in reply

    new_ticket = store.tickets[result["ticketId"]]
    commercial = new_ticket.get("commercial") or {}
    assert commercial.get("zona") is None
    assert commercial.get("tipologia") is None
    assert commercial.get("presupuesto") is None
    assert commercial.get("moneda") is None
    assert commercial.get("fecha_mudanza") is None
    assert (new_ticket.get("slot_memory") or {}).get("answered_fields") == []
