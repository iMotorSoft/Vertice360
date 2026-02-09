from __future__ import annotations

from litestar.enums import MediaType
from litestar.response import Response

from backend.modules.messaging.providers.meta.whatsapp.client import MetaWhatsAppSendError
from backend.routes import messaging as messaging_routes


def test_unified_send_meta_success_shape(client, monkeypatch) -> None:
    async def fake_meta_send(to: str, text: str):  # noqa: ARG001
        return {"messages": [{"id": "wamid.meta.123"}], "status": "accepted"}

    monkeypatch.setattr(messaging_routes, "send_text_message", fake_meta_send)

    response = client.post(
        "/api/demo/messaging/whatsapp/send",
        json={"provider": "meta", "to": "541130946950", "text": "hola"},
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["ok"] is True
    assert payload["provider"] == "meta"
    assert payload["message_id"] == "wamid.meta.123"
    assert payload["raw"]["status"] == "accepted"


def test_unified_send_meta_failure_returns_502_with_debug_shape(client, monkeypatch) -> None:
    async def fake_meta_send(to: str, text: str):  # noqa: ARG001
        raise MetaWhatsAppSendError(
            400,
            {"error": {"message": "Recipient phone number not in allowed list"}},
        )

    monkeypatch.setattr(messaging_routes, "send_text_message", fake_meta_send)

    response = client.post(
        "/api/demo/messaging/whatsapp/send",
        json={"provider": "meta", "to": "541130946950", "text": "hola"},
    )
    assert response.status_code == 502

    payload = response.json()
    assert payload["ok"] is False
    assert payload["provider"] == "meta"
    assert payload["error"]["type"] == "MetaWhatsAppSendError"
    assert payload["error"]["upstream_status"] == 400
    assert payload["error"]["message"] == "Recipient phone number not in allowed list"
    assert "/messages" in payload["error"]["url"]


def test_unified_send_routes_to_gupshup_handler(client, monkeypatch) -> None:
    async def fake_gupshup_send(self, to: str, text: str):  # noqa: ARG002
        return Response(
            status_code=200,
            media_type=MediaType.JSON,
            content={
                "ok": True,
                "provider": "gupshup",
                "message_id": "gs-msg-123",
                "raw": {"status": "submitted"},
            },
        )

    monkeypatch.setattr(
        messaging_routes.DemoMessagingController,
        "_send_gupshup_whatsapp",
        fake_gupshup_send,
    )

    response = client.post(
        "/api/demo/messaging/whatsapp/send",
        json={"provider": "gupshup", "to": "541130946950", "text": "hola"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["provider"] == "gupshup"
    assert payload["message_id"] == "gs-msg-123"


def test_unified_send_routes_to_gupshup_handler_with_alias_provider(client, monkeypatch) -> None:
    async def fake_gupshup_send(self, to: str, text: str):  # noqa: ARG002
        return Response(
            status_code=200,
            media_type=MediaType.JSON,
            content={
                "ok": True,
                "provider": "gupshup",
                "message_id": "gs-msg-aliased",
                "raw": {"status": "submitted"},
            },
        )

    monkeypatch.setattr(
        messaging_routes.DemoMessagingController,
        "_send_gupshup_whatsapp",
        fake_gupshup_send,
    )

    response = client.post(
        "/api/demo/messaging/whatsapp/send",
        json={"provider": "gupshup_whatsapp", "to": "541130946950", "text": "hola"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["provider"] == "gupshup"
    assert payload["message_id"] == "gs-msg-aliased"
