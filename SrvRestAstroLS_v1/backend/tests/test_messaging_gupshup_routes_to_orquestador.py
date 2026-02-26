from __future__ import annotations

import json

from backend.routes import messaging as messaging_routes


def _sample_inbound_payload() -> dict:
    return {
        "type": "message",
        "payload": {
            "id": "inbound-msg-01",
            "type": "text",
            "source": "5491112340001",
            "destination": "5491100000000",
            "payload": {"text": "hi"},
        },
    }


def test_gupshup_message_routes_to_orquestador_when_mode_is_orquestador(
    client, monkeypatch, event_recorder  # noqa: ARG001
) -> None:
    calls = {"orq": 0, "workflow": 0}
    captured: dict[str, str | None] = {}

    async def fake_ingest_from_provider(
        *,
        user_phone: str,
        text: str,
        provider: str = "gupshup_whatsapp",
        provider_message_id: str | None = None,
        provider_meta: dict | None = None,
    ):
        calls["orq"] += 1
        captured["user_phone"] = user_phone
        captured["text"] = text
        captured["provider"] = provider
        captured["provider_message_id"] = provider_message_id
        captured["channel"] = (provider_meta or {}).get("channel")
        return {
            "ok": True,
            "routed": "orquestador",
            "ticket_id": "ORQ-T-42",
            "lead_id": "LEAD-42",
            "conversation_id": "CONV-42",
            "vera_send_ok": True,
        }

    async def fake_workflow(*args, **kwargs):  # noqa: ANN002, ANN003
        calls["workflow"] += 1
        return {"ticketId": "WF-T-1"}

    monkeypatch.setattr(messaging_routes.orquestador_demo_services, "ingest_from_provider", fake_ingest_from_provider)
    monkeypatch.setattr(messaging_routes, "process_inbound_message", fake_workflow)

    response = client.post(
        "/webhooks/messaging/gupshup/whatsapp",
        content=json.dumps(_sample_inbound_payload()),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 201
    assert response.json() == {"ok": True, "routed": "orquestador", "vera_send_ok": True}
    assert calls == {"orq": 1, "workflow": 0}
    assert captured == {
        "user_phone": "+5491112340001",
        "text": "hi",
        "provider": "gupshup_whatsapp",
        "provider_message_id": "inbound-msg-01",
        "channel": "whatsapp",
    }


def test_gupshup_message_ignores_workflow_mode_and_keeps_orquestador_route(
    client, monkeypatch, event_recorder  # noqa: ARG001
) -> None:
    calls = {"orq": 0, "workflow": 0}

    async def fake_ingest_from_provider(*args, **kwargs):  # noqa: ANN002, ANN003
        calls["orq"] += 1
        return {
            "ok": True,
            "routed": "orquestador",
            "ticket_id": "ORQ-T-42",
            "vera_send_ok": True,
        }

    async def fake_workflow(*args, **kwargs):  # noqa: ANN002, ANN003
        calls["workflow"] += 1
        return {"ticketId": "WF-T-1"}

    monkeypatch.setattr(messaging_routes.orquestador_demo_services, "ingest_from_provider", fake_ingest_from_provider)
    monkeypatch.setattr(messaging_routes, "process_inbound_message", fake_workflow)

    response = client.post(
        "/webhooks/messaging/gupshup/whatsapp",
        content=json.dumps(_sample_inbound_payload()),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 201
    assert response.json() == {"ok": True, "routed": "orquestador", "vera_send_ok": True}
    assert calls == {"orq": 1, "workflow": 0}
