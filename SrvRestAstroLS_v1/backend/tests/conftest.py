from __future__ import annotations

import sys
from pathlib import Path
import asyncio

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest
import httpx

from backend.modules.agui_stream.broadcaster import broadcaster
from backend.modules.vertice360_workflow_demo import services, store
from backend.ls_iMotorSoft_Srv01_demo import create_app

_ORIGINAL_SEND_WHATSAPP_TEXT = services._send_whatsapp_text
_ORIGINAL_RUN_AI_WORKFLOW_REPLY = services._run_ai_workflow_reply


@pytest.fixture(autouse=True)
def reset_workflow_store():
    store.reset_store()
    services.reset_inbound_dedupe_cache()
    yield
    store.reset_store()
    services.reset_inbound_dedupe_cache()


@pytest.fixture(autouse=True)
def reset_workflow_service_hooks(monkeypatch):
    monkeypatch.setattr(services, "_send_whatsapp_text", _ORIGINAL_SEND_WHATSAPP_TEXT)
    monkeypatch.setattr(services, "_run_ai_workflow_reply", _ORIGINAL_RUN_AI_WORKFLOW_REPLY)


@pytest.fixture(autouse=True)
def mock_meta_send(monkeypatch):
    monkeypatch.setenv("DEMO_DISABLE_META_SEND", "1")
    calls = []

    async def fake_send(to: str, text: str) -> dict:
        message_id = f"fake-{len(calls) + 1}"
        calls.append({"to": to, "text": text, "messageId": message_id})
        return {"messages": [{"id": message_id}]}

    monkeypatch.setattr(services, "send_text_message", fake_send)
    return calls


@pytest.fixture()
def event_recorder(monkeypatch):
    events: list[dict] = []

    async def capture(event_type: str, payload: dict) -> None:
        if not isinstance(payload, dict) or payload.get("type") != "CUSTOM":
            return
        events.append(
            {
                "type": payload.get("type"),
                "name": payload.get("name") or event_type,
                "timestamp": payload.get("timestamp"),
                "correlationId": payload.get("correlationId"),
                "value": payload.get("value") or {},
            }
        )

    monkeypatch.setattr(broadcaster, "publish", capture)
    return events


@pytest.fixture()
def client():
    app = create_app()

    class SyncASGIClient:
        def request(self, method: str, url: str, **kwargs):
            async def _run_request():
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(
                    transport=transport,
                    base_url="http://testserver.local",
                ) as async_client:
                    return await async_client.request(method, url, **kwargs)

            return asyncio.run(_run_request())

        def get(self, url: str, **kwargs):
            return self.request("GET", url, **kwargs)

        def post(self, url: str, **kwargs):
            return self.request("POST", url, **kwargs)

    yield SyncASGIClient()
