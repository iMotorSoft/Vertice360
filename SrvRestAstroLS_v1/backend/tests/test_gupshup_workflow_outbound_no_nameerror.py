from __future__ import annotations

import asyncio
from types import SimpleNamespace

from backend.modules.vertice360_workflow_demo import services


def test_gupshup_workflow_outbound_helper_no_nameerror(monkeypatch) -> None:
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

