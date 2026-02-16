from __future__ import annotations

import json

from backend.routes import messaging as messaging_routes


def test_gupshup_webhook_billing_event_is_ignored(client, monkeypatch, event_recorder) -> None:  # noqa: ARG001
    calls = {"ai": 0, "workflow": 0}

    async def fake_ai(*args, **kwargs):  # noqa: ANN002, ANN003
        calls["ai"] += 1
        return None

    async def fake_workflow(*args, **kwargs):  # noqa: ANN002, ANN003
        calls["workflow"] += 1
        return {"ticketId": "VTX-IGNORE-1"}

    monkeypatch.setattr(messaging_routes, "maybe_start_ai_workflow_from_inbound", fake_ai)
    monkeypatch.setattr(messaging_routes, "process_inbound_message", fake_workflow)

    payload = {
        "type": "billing-event",
        "payload": {
            "id": "bill-1",
            "type": "charged",
        },
    }

    response = client.post(
        "/webhooks/messaging/gupshup/whatsapp",
        content=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 201
    assert response.json().get("ok") is True
    assert calls == {"ai": 0, "workflow": 0}


def test_gupshup_webhook_message_event_status_is_ignored(client, monkeypatch, event_recorder) -> None:  # noqa: ARG001
    calls = {"ai": 0, "workflow": 0}

    async def fake_ai(*args, **kwargs):  # noqa: ANN002, ANN003
        calls["ai"] += 1
        return None

    async def fake_workflow(*args, **kwargs):  # noqa: ANN002, ANN003
        calls["workflow"] += 1
        return {"ticketId": "VTX-IGNORE-2"}

    monkeypatch.setattr(messaging_routes, "maybe_start_ai_workflow_from_inbound", fake_ai)
    monkeypatch.setattr(messaging_routes, "process_inbound_message", fake_workflow)

    payload = {
        "type": "message-event",
        "payload": {
            "id": "status-1",
            "type": "delivered",
            "payload": {"text": "status wrapper"},
        },
    }

    response = client.post(
        "/webhooks/messaging/gupshup/whatsapp",
        content=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 201
    assert response.json().get("ok") is True
    assert calls == {"ai": 0, "workflow": 0}


def test_gupshup_webhook_inbound_text_triggers_workflow_once(client, monkeypatch, event_recorder) -> None:  # noqa: ARG001
    calls = {"ai": 0, "workflow": 0}

    async def fake_ai(*args, **kwargs):  # noqa: ANN002, ANN003
        calls["ai"] += 1
        return None

    async def fake_workflow(*args, **kwargs):  # noqa: ANN002, ANN003
        calls["workflow"] += 1
        return {"ticketId": "VTX-INBOUND-1"}

    monkeypatch.setattr(messaging_routes, "maybe_start_ai_workflow_from_inbound", fake_ai)
    monkeypatch.setattr(messaging_routes, "process_inbound_message", fake_workflow)

    payload = {
        "type": "message",
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
    assert response.json().get("ok") is True
    assert calls == {"ai": 0, "workflow": 1}
