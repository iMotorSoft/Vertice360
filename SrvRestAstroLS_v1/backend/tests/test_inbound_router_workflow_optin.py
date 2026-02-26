from __future__ import annotations

import json

from backend.routes import messaging as messaging_routes


def test_inbound_router_workflow_optin_is_ignored_and_routes_to_orquestador(
    client, monkeypatch, event_recorder  # noqa: ARG001
) -> None:
    calls = {"orq": 0, "workflow": 0}
    monkeypatch.setattr(
        messaging_routes.globalVar, "V360_INBOUND_ROUTER_MODE", "workflow", raising=False
    )

    async def fake_orquestador_ingest(*args, **kwargs):  # noqa: ANN002, ANN003
        calls["orq"] += 1
        return {
            "ok": True,
            "routed": "orquestador",
            "ticket_id": "ORQ-UNUSED-1",
            "lead_id": "LEAD-UNUSED-1",
            "conversation_id": "CONV-UNUSED-1",
            "vera_send_ok": True,
        }

    async def fake_workflow(*args, **kwargs):  # noqa: ANN002, ANN003
        calls["workflow"] += 1
        return {"ticketId": "WF-1"}

    monkeypatch.setattr(messaging_routes.orquestador_demo_services, "ingest_from_provider", fake_orquestador_ingest)
    monkeypatch.setattr(messaging_routes, "process_inbound_message", fake_workflow)

    payload = {
        "type": "message",
        "payload": {
            "id": "inbound-workflow-optin-01",
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
    assert calls == {"orq": 1, "workflow": 0}
