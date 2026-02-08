from __future__ import annotations

from backend.modules.messaging.providers.gupshup.whatsapp.mapper import (
    parse_inbound,
    parse_status,
)


def test_parse_inbound_minimal_payload() -> None:
    payload = {
        "payload": {
            "from": "5491122334455",
            "to": "14155551234",
            "text": "hola",
            "timestamp": "1700000000",
            "id": "msg-123",
        }
    }

    messages = parse_inbound(payload)

    assert len(messages) == 1
    message = messages[0]
    assert message.provider == "gupshup"
    assert message.service == "whatsapp"
    assert message.wa_id == "5491122334455"
    assert message.from_ == "5491122334455"
    assert message.to == "14155551234"
    assert message.text == "hola"
    assert message.timestamp == "1700000000"
    assert message.message_id == "msg-123"
    assert message.raw == payload["payload"]


def test_parse_status_minimal_payload() -> None:
    payload = {
        "status": {
            "messageId": "msg-999",
            "status": "DELIVERED",
            "timestamp": "1700000001",
        }
    }

    statuses = parse_status(payload)

    assert len(statuses) == 1
    status = statuses[0]
    assert status.provider == "gupshup"
    assert status.service == "whatsapp"
    assert status.message_id == "msg-999"
    assert status.status == "delivered"
    assert status.timestamp == "1700000001"
    assert status.raw == payload["status"]


def test_parse_status_message_event_failed_payload() -> None:
    payload = {
        "id": "whatsapp-msg-id-123",
        "gsId": "gs-id-123",
        "type": "failed",
        "destination": "5491130946950",
        "payload": {
            "code": 470,
            "reason": "Message failed because more than 24 hours have passed.",
        },
    }

    statuses = parse_status(payload)
    inbound = parse_inbound(payload)

    assert len(statuses) == 1
    status = statuses[0]
    assert status.provider == "gupshup"
    assert status.service == "whatsapp"
    assert status.message_id == "gs-id-123"
    assert status.status == "failed"
    assert status.raw == payload
    assert inbound == []


def test_parse_inbound_message_wrapper_payload() -> None:
    payload = {
        "app": "vertice360dev",
        "timestamp": 1770565000000,
        "version": 2,
        "type": "message",
        "payload": {
            "id": "inbound-msg-001",
            "source": "541130946950",
            "destination": "5491100000000",
            "type": "text",
            "payload": {"text": "OK DobleVia"},
        },
    }

    messages = parse_inbound(payload)
    statuses = parse_status(payload)

    assert len(messages) == 1
    message = messages[0]
    assert message.provider == "gupshup"
    assert message.service == "whatsapp"
    assert message.from_ == "541130946950"
    assert message.to == "5491100000000"
    assert message.message_id == "inbound-msg-001"
    assert message.text == "OK DobleVia"
    assert statuses == []
