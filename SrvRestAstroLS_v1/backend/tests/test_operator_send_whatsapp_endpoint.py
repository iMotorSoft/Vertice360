from __future__ import annotations

import asyncio

from backend.modules.vertice360_workflow_demo import store as workflow_store
from backend.routes import messaging as messaging_routes


def test_operator_send_sets_handoff_stage(client, event_recorder, monkeypatch) -> None:
    sent: dict[str, str] = {}

    async def fake_unified(provider: str, to: str, text: str):
        sent["provider"] = provider
        sent["to"] = to
        sent["text"] = text
        return 200, {
            "ok": True,
            "provider": "gupshup",
            "message_id": "op-msg-001",
            "raw": {"status": "submitted"},
        }

    monkeypatch.setattr(messaging_routes, "_send_whatsapp_unified_payload", fake_unified)

    ticket = asyncio.run(
        workflow_store.create_or_get_ticket_from_inbound(
            {
                "ticketId": "VTX-9001",
                "provider": "gupshup_whatsapp",
                "channel": "whatsapp",
                "customer": {"from": "5491130946950", "to": "5491100000000"},
                "subject": "Handoff",
            }
        )
    )
    workflow_store.set_handoff_required(ticket["ticketId"], True, "schedule_visit")

    response = client.post(
        "/api/demo/workflow/operator/send_whatsapp",
        json={
            "provider": "gupshup",
            "to": "5491130946950",
            "text": "Tengo dos franjas para esta semana.",
            "operator_name": "Laura",
            "ticket_id": "VTX-9001",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["provider"] == "gupshup"
    assert payload["message_id"] == "op-msg-001"

    assert sent["provider"] == "gupshup"
    assert sent["to"] == "5491130946950"
    assert sent["text"].startswith("Hola, soy Laura, del equipo de visitas de Vértice360.\n")

    ticket_after = workflow_store.tickets["VTX-9001"]
    assert ticket_after.get("handoffRequired") is True
    assert ticket_after.get("handoffStage") == "operator_engaged"
    assert ticket_after.get("lastOperatorName") == "Laura"

    outbound_event = next(
        (event for event in event_recorder if event.get("name") == "messaging.outbound"),
        None,
    )
    assert outbound_event is not None
    assert outbound_event.get("correlationId") == "VTX-9001"


def test_operator_send_whatsapp_returns_502_shape(client, monkeypatch) -> None:
    async def fake_unified(provider: str, to: str, text: str):  # noqa: ARG001
        return 502, {
            "ok": False,
            "provider": "meta",
            "error": {
                "type": "MetaWhatsAppSendError",
                "message": "Rate limit",
                "upstream_status": 429,
                "upstream_body": "too many requests",
                "url": "https://graph.facebook.com/messages",
            },
        }

    monkeypatch.setattr(messaging_routes, "_send_whatsapp_unified_payload", fake_unified)

    response = client.post(
        "/api/demo/workflow/operator/send_whatsapp",
        json={
            "provider": "meta",
            "to": "5491130946950",
            "text": "Hola",
            "operator_name": "Laura",
        },
    )

    assert response.status_code == 502
    payload = response.json()
    assert payload["ok"] is False
    assert payload["provider"] == "meta"
    assert payload["error"]["upstream_status"] == 429
