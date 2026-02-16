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


def _complete_profile(phone: str) -> str:
    r1 = asyncio.run(
        services.process_inbound_message(
            {
                "provider": "meta_whatsapp",
                "channel": "whatsapp",
                "from": phone,
                "to": "+5491100000000",
                "messageId": "profile-1",
                "text": "hola",
                "timestamp": 1000,
            }
        )
    )
    ticket_id = r1["ticketId"]

    asyncio.run(
        services.process_inbound_message(
            {
                "provider": "meta_whatsapp",
                "channel": "whatsapp",
                "from": phone,
                "to": "+5491100000000",
                "messageId": "profile-2",
                "text": "Palermo 3 ambientes",
                "timestamp": 2000,
                "ticketId": ticket_id,
            }
        )
    )
    asyncio.run(
        services.process_inbound_message(
            {
                "provider": "meta_whatsapp",
                "channel": "whatsapp",
                "from": phone,
                "to": "+5491100000000",
                "messageId": "profile-3",
                "text": "USD 120k",
                "timestamp": 3000,
                "ticketId": ticket_id,
            }
        )
    )
    asyncio.run(
        services.process_inbound_message(
            {
                "provider": "meta_whatsapp",
                "channel": "whatsapp",
                "from": phone,
                "to": "+5491100000000",
                "messageId": "profile-4",
                "text": "abril 2026",
                "timestamp": 4000,
                "ticketId": ticket_id,
            }
        )
    )
    return ticket_id


def test_handoff_scheduling_short_greeting_does_not_reset(mock_meta_send) -> None:
    phone = "+5491112300001"
    ticket_id = _complete_profile(phone)

    result = asyncio.run(
        services.process_inbound_message(
            {
                "provider": "meta_whatsapp",
                "channel": "whatsapp",
                "from": phone,
                "to": "+5491100000000",
                "messageId": "profile-5",
                "text": "hi",
                "timestamp": 5000,
            }
        )
    )

    assert result["ticketId"] == ticket_id
    assert "¿Por qué zona buscás" not in (result.get("replyText") or "")
    assert "día y franja horaria" in (result.get("replyText") or "").lower()


def test_explicit_reset_command_starts_new_ticket(mock_meta_send) -> None:
    phone = "+5491112300002"
    old = _seed_ticket("VTX-RESET-EXPLICIT", phone)
    store.update_ticket_commercial(
        old["ticketId"],
        {
            "zona": "Palermo",
            "tipologia": "3 ambientes",
            "presupuesto": 180000,
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
                "messageId": "msg-reset-explicit-1",
                "text": "reiniciar",
                "timestamp": int(time.time() * 1000),
            }
        )
    )

    assert result["ticketId"] != old["ticketId"]
    assert "¿Por qué zona buscás y cuántos ambientes necesitás?" in (result.get("replyText") or "")


def test_conversation_state_key_uses_provider_app_phone_not_wamid(monkeypatch) -> None:
    async def fake_send(provider: str, to: str, text: str):  # noqa: ARG001
        return {"id": "mock-msg"}

    monkeypatch.setattr(services, "_send_whatsapp_text", fake_send)

    first = asyncio.run(
        services.process_inbound_message(
            {
                "provider": "gupshup_whatsapp",
                "app": "vertice360dev",
                "channel": "whatsapp",
                "from": "5491130946950",
                "to": "5491100000000",
                "messageId": "wamid-A",
                "text": "hola",
                "timestamp": 1711111111000,
            }
        )
    )

    second = asyncio.run(
        services.process_inbound_message(
            {
                "provider": "gupshup_whatsapp",
                "app": "vertice360dev",
                "channel": "whatsapp",
                "from": "5491130946950",
                "to": "5491100000000",
                "messageId": "wamid-B",
                "text": "ok",
                "timestamp": 1711111112000,
            }
        )
    )

    assert first["ticketId"] == second["ticketId"]
    ticket = store.tickets[first["ticketId"]]
    assert ticket.get("conversationKey") == "gupshup_whatsapp:vertice360dev:5491130946950"
