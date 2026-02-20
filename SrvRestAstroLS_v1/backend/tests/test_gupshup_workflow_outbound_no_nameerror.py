from __future__ import annotations

import asyncio
from types import SimpleNamespace

from backend.modules.vertice360_workflow_demo import services


def test_gupshup_workflow_outbound_helper_no_nameerror(monkeypatch) -> None:
    monkeypatch.setattr(services.globalVar, "GUPSHUP_WA_SENDER", "+5491100000000", raising=False)

    async def fake_gupshup_send_text(to: str, text: str):
        assert to == "5491130946950"
        assert text == "test outbound"
        return SimpleNamespace(provider_message_id="gs-msg-001", raw={"id": "gs-msg-001"})

    monkeypatch.setattr(services, "gupshup_send_text", fake_gupshup_send_text)

    result = asyncio.run(
        services._send_whatsapp_text("gupshup_whatsapp", "5491130946950", "test outbound")
    )

    assert result.get("id") == "gs-msg-001"
    assert result.get("raw") == {"id": "gs-msg-001"}
    assert result.get("from") == "+5491100000000"
    assert result.get("vera_send_ok") is True


def test_gupshup_sender_missing_returns_controlled_error(monkeypatch) -> None:
    monkeypatch.setattr(services.globalVar, "GUPSHUP_APP_NAME", "app-dev", raising=False)
    monkeypatch.setattr(services.globalVar, "GUPSHUP_API_KEY", "key-dev", raising=False)
    monkeypatch.setattr(services.globalVar, "GUPSHUP_WA_SENDER", "", raising=False)

    async def fake_gupshup_send_text(to: str, text: str):  # noqa: ARG001
        raise AssertionError("send_text should not be called when sender is missing")

    monkeypatch.setattr(services, "gupshup_send_text", fake_gupshup_send_text)

    result = asyncio.run(
        services._send_whatsapp_text_with_context(
            "gupshup_whatsapp",
            "5491130946950",
            "hola",
            ticket_id="VTX-001",
            correlation_id="corr-001",
        )
    )

    assert result.get("vera_send_ok") is False
    assert result.get("status") == "error"
    error = result.get("error") or {}
    assert error.get("type") == "GupshupSenderMissing"
