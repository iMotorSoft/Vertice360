from __future__ import annotations

import asyncio

from backend.modules.messaging.providers.meta.whatsapp import service as whatsapp_service
from backend.modules.messaging.providers.meta.whatsapp.mapper import waid_to_graph_to


def test_waid_to_graph_to_argentina_mobile() -> None:
    assert waid_to_graph_to("5491130946950") == "541130946950"


def test_waid_to_graph_to_normalizes() -> None:
    assert waid_to_graph_to("+54 11 3094-6950") == "541130946950"


def test_waid_to_graph_to_passthrough() -> None:
    assert waid_to_graph_to("15551234567") == "15551234567"


def test_send_text_message_uses_mapped_to(monkeypatch) -> None:
    captured: dict[str, dict] = {}

    async def fake_post_message(payload: dict, client=None) -> dict:
        captured["payload"] = payload
        return {"messages": [{"id": "msg-1"}]}

    monkeypatch.setattr(whatsapp_service, "post_message", fake_post_message)

    asyncio.run(whatsapp_service.send_text_message("5491130946950", "hola"))

    assert captured["payload"]["to"] == "541130946950"
