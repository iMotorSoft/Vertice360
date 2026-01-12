from __future__ import annotations

import asyncio
import hashlib
import hmac
import json

from backend import globalVar
from backend.modules.vertice360_workflow_demo import services, store


def assert_event_contract(events: list[dict]) -> None:
    for event in events:
        if event.get("type") != "CUSTOM":
            continue
        value = event.get("value") or {}
        if isinstance(value, dict) and value.get("ticketId"):
            assert event.get("correlationId") == value.get("ticketId")


def test_engine_inbound_hello_creates_events(event_recorder, mock_meta_send):
    inbound = {
        "provider": "meta_whatsapp",
        "channel": "whatsapp",
        "from": "+5491112345678",
        "to": "+5491100000000",
        "messageId": "msg-hello-1",
        "text": "Hola",
        "timestamp": 1710000000000,
        "mediaCount": 0,
    }

    result = asyncio.run(services.process_inbound_message(inbound))
    ticket_id = result.get("ticketId")

    assert ticket_id
    assert ticket_id in store.tickets
    assert len(mock_meta_send) == 1

    event_names = {event["name"] for event in event_recorder}
    assert "ticket.created" in event_names
    assert "messaging.inbound" in event_names
    assert "messaging.outbound" in event_names

    created_event = next(event for event in event_recorder if event["name"] == "ticket.created")
    assert created_event.get("value", {}).get("ticketId") == ticket_id
    assert created_event.get("correlationId") == ticket_id

    assert_event_contract(event_recorder)


def test_engine_inbound_docs_assigns_and_starts_sla(event_recorder):
    inbound = {
        "provider": "meta_whatsapp",
        "channel": "whatsapp",
        "from": "+5491100001111",
        "to": "+5491100000000",
        "messageId": "msg-docs-1",
        "text": "Necesito enviar documentacion para reservar",
        "timestamp": 1710000100000,
        "mediaCount": 0,
    }

    result = asyncio.run(services.process_inbound_message(inbound))
    ticket_id = result.get("ticketId")

    assert ticket_id
    ticket = store.tickets[ticket_id]
    assert ticket.get("status") == "WAITING_DOCS"

    event_names = [event["name"] for event in event_recorder]
    assert "ticket.assigned" in event_names
    assert event_names.count("ticket.sla.started") >= 2

    sla_types = {
        event.get("value", {}).get("slaType")
        for event in event_recorder
        if event.get("name") == "ticket.sla.started"
    }
    assert {"ASSIGNMENT", "DOC_VALIDATION"}.issubset(sla_types)

    assert_event_contract(event_recorder)


def test_rest_endpoints_smoke(client, event_recorder):
    inbound = {
        "provider": "meta_whatsapp",
        "channel": "whatsapp",
        "from": "+5491199990000",
        "to": "+5491100000000",
        "messageId": "msg-rest-1",
        "text": "Hola",
        "timestamp": 1710000200000,
        "mediaCount": 0,
    }
    result = asyncio.run(services.process_inbound_message(inbound))
    ticket_id = result.get("ticketId")
    event_recorder.clear()

    response = client.get("/api/demo/vertice360-workflow/tickets")
    assert response.status_code == 200
    tickets = response.json()
    assert any(ticket.get("ticketId") == ticket_id for ticket in tickets)

    response = client.get(f"/api/demo/vertice360-workflow/tickets/{ticket_id}")
    assert response.status_code == 200
    detail = response.json()
    assert detail.get("ticketId") == ticket_id

    response = client.post(
        f"/api/demo/vertice360-workflow/tickets/{ticket_id}/assign",
        json={"team": "ADMIN", "name": "Test Agent"},
    )
    assert response.status_code == 201
    assert response.json().get("assignee", {}).get("name") == "Test Agent"

    response = client.post(
        f"/api/demo/vertice360-workflow/tickets/{ticket_id}/docs",
        json={"action": "RECEIVE"},
    )
    assert response.status_code == 201
    assert response.json().get("docsReceivedAt")

    response = client.post(
        f"/api/demo/vertice360-workflow/tickets/{ticket_id}/simulate-breach",
        json={"slaType": "ASSIGNMENT"},
    )
    assert response.status_code == 201
    assert response.json().get("status") == "ESCALATED"

    response = client.post(
        f"/api/demo/vertice360-workflow/tickets/{ticket_id}/close",
        json={"resolutionCode": "DOCS_VALIDATED"},
    )
    assert response.status_code == 201
    assert response.json().get("status") == "CLOSED"

    response = client.post("/api/demo/vertice360-workflow/reset", json={})
    assert response.status_code == 201
    assert response.json().get("ok") is True

    event_names = {event["name"] for event in event_recorder}
    assert "ticket.assigned" in event_names
    assert "ticket.sla.breached" in event_names
    assert "ticket.closed" in event_names
    assert "workflow.reset" in event_names

    assert_event_contract(event_recorder)


def test_meta_webhook_best_effort(client, event_recorder):
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {
                                "phone_number_id": "123",
                                "display_phone_number": "+5491100000000",
                            },
                            "contacts": [{"wa_id": "+5491111111111"}],
                            "messages": [
                                {
                                    "from": "+5491111111111",
                                    "id": "wamid.webhook.1",
                                    "timestamp": "1710000300",
                                    "text": {"body": "Hola desde webhook"},
                                    "type": "text",
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }

    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if globalVar.META_APP_SECRET_IMOTORSOFT:
        signature = "sha256=" + hmac.new(
            globalVar.META_APP_SECRET_IMOTORSOFT.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
        headers["X-Hub-Signature-256"] = signature

    response = client.post("/webhooks/messaging/meta/whatsapp", content=body, headers=headers)
    assert response.status_code == 201
    assert response.json().get("ok") is True

    event_names = {event["name"] for event in event_recorder}
    assert "messaging.inbound.raw" in event_names
    assert "ticket.created" in event_names

    assert_event_contract(event_recorder)
