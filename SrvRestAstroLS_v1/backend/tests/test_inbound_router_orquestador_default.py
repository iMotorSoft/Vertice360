from __future__ import annotations

import json

import pytest

from backend.routes import messaging as messaging_routes


@pytest.mark.parametrize(
    "router_mode_state,payload,expected_calls,expected_routed",
    [
        (
            "unset",
            {
                "type": "message",
                "payload": {
                    "id": "inbound-default-01",
                    "type": "text",
                    "source": "5491112340001",
                    "destination": "5491100000000",
                    "payload": {"text": "hi"},
                },
            },
            {"orq": 1, "workflow": 0},
            "orquestador",
        ),
        (
            "none",
            {
                "type": "user-event",
                "sender": "5491112340001",
                "text": "hi",
            },
            {"orq": 0, "workflow": 0},
            None,
        ),
    ],
)
def test_inbound_router_defaults_to_orquestador_when_mode_is_unset_or_none(
    client, monkeypatch, router_mode_state, payload, expected_calls, expected_routed, event_recorder  # noqa: ARG001
) -> None:
    calls = {"orq": 0, "workflow": 0}

    if router_mode_state == "unset":
        monkeypatch.delattr(messaging_routes.globalVar, "V360_INBOUND_ROUTER_MODE", raising=False)
    else:
        monkeypatch.setattr(messaging_routes.globalVar, "V360_INBOUND_ROUTER_MODE", None, raising=False)

    async def fake_orquestador_ingest(
        *,
        provider: str,
        user_phone: str,
        text: str,
        provider_message_id: str | None = None,
        provider_meta: dict | None = None,
    ):
        calls["orq"] += 1
        return {
            "ok": True,
            "routed": "orquestador",
            "ticket_id": "ORQ-DEFAULT-1",
            "lead_id": "LEAD-DEFAULT-1",
            "conversation_id": "CONV-DEFAULT-1",
            "vera_send_ok": True,
        }

    async def fake_workflow(*args, **kwargs):  # noqa: ANN002, ANN003
        calls["workflow"] += 1
        return {"ticketId": "WF-UNUSED-1"}

    monkeypatch.setattr(messaging_routes.orquestador_demo_services, "ingest_from_provider", fake_orquestador_ingest)
    monkeypatch.setattr(messaging_routes, "process_inbound_message", fake_workflow)

    response = client.post(
        "/webhooks/messaging/gupshup/whatsapp",
        content=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 201
    assert response.json().get("ok") is True
    assert response.json().get("routed") == expected_routed
    assert calls == expected_calls
