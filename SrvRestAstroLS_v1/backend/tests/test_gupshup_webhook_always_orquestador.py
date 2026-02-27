from __future__ import annotations

import json

from backend.routes import messaging as messaging_routes


def test_gupshup_webhook_message_always_routes_to_orquestador(client, monkeypatch, event_recorder) -> None:  # noqa: ARG001
    calls = {"orquestador": 0, "workflow": 0}
    captured: dict[str, object] = {}

    async def fake_ingest_from_provider(
        *,
        user_phone: str,
        text: str,
        provider: str = "gupshup_whatsapp",
        provider_message_id: str | None = None,
        provider_meta: dict | None = None,
    ) -> dict:
        calls["orquestador"] += 1
        captured["user_phone"] = user_phone
        captured["text"] = text
        captured["provider"] = provider
        captured["provider_message_id"] = provider_message_id
        captured["provider_meta"] = provider_meta
        return {
            "ok": True,
            "routed": "orquestador",
            "ticket_id": "ORQ-T-1",
            "vera_send_ok": True,
        }

    async def fake_workflow(*args, **kwargs):  # noqa: ANN002, ANN003
        calls["workflow"] += 1
        return {"ticketId": "WF-UNUSED"}

    monkeypatch.setattr(messaging_routes.orquestador_demo_services, "ingest_from_provider", fake_ingest_from_provider)
    monkeypatch.setattr(messaging_routes, "process_inbound_message", fake_workflow)

    payload = {
        "type": "message",
        "app": "vertice360dev",
        "payload": {
            "id": "inbound-msg-01",
            "type": "text",
            "source": "5491112340001",
            "destination": "5491100000000",
            "payload": {"text": "hola"},
        },
    }

    response = client.post(
        "/webhooks/messaging/gupshup/whatsapp",
        content=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 201
    assert response.json() == {"ok": True, "routed": "orquestador", "vera_send_ok": True}
    assert calls == {"orquestador": 1, "workflow": 0}
    assert captured["user_phone"] == "+5491112340001"
    assert captured["text"] == "hola"
    assert captured["provider"] == "gupshup_whatsapp"
    assert captured["provider_message_id"] == "inbound-msg-01"
    provider_meta = captured["provider_meta"] or {}
    assert provider_meta.get("channel") == "whatsapp"
    assert provider_meta.get("app") == "vertice360dev"
