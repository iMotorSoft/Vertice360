from __future__ import annotations

import globalVar

from backend.modules.messaging.providers.gupshup.whatsapp.client import GupshupHTTPError
from backend.routes import messaging as messaging_routes


def test_gupshup_demo_send_returns_502_with_debug_shape(client, monkeypatch) -> None:
    monkeypatch.setattr(globalVar, "GUPSHUP_API_KEY", "test-api-key", raising=False)
    monkeypatch.setattr(globalVar, "GUPSHUP_APP_NAME", "test-app", raising=False)
    monkeypatch.setattr(globalVar, "GUPSHUP_SRC_NUMBER", "111222333", raising=False)
    monkeypatch.setattr(globalVar, "GUPSHUP_BASE_URL", "https://api.gupshup.io", raising=False)

    async def fake_send_text_message(self, to: str, text: str):  # noqa: ARG001
        raise GupshupHTTPError(
            status_code=401,
            response_text='{"message":"Invalid API key"}',
            url="https://api.gupshup.io/wa/api/v1/msg",
        )

    monkeypatch.setattr(
        messaging_routes.GupshupWhatsAppService,
        "send_text_message",
        fake_send_text_message,
    )

    response = client.post(
        "/api/demo/messaging/gupshup/whatsapp/send",
        json={"to": "541130946950", "text": "hola"},
    )
    assert response.status_code == 502

    payload = response.json()
    assert payload["ok"] is False
    assert payload["provider"] == "gupshup"

    error = payload["error"]
    assert error["upstream_status"] == 401
    assert error["upstream_body"] == '{"message":"Invalid API key"}'
    assert error["url"] == "https://api.gupshup.io/wa/api/v1/msg"

    env = payload["env"]
    assert "has_api_key" in env
    assert "has_app_name" in env
    assert "has_src_number" in env
    assert env["has_api_key"] is True
    assert env["has_app_name"] is True
    assert env["has_src_number"] is True
    assert env["base_url"] == "https://api.gupshup.io"
