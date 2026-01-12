from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest
from litestar.testing import TestClient

from backend.modules.agui_stream.broadcaster import broadcaster
from backend.modules.vertice360_workflow_demo import services, store
from backend.ls_iMotorSoft_Srv01_demo import create_app


@pytest.fixture(autouse=True)
def reset_workflow_store():
    store.reset_store()
    yield
    store.reset_store()


@pytest.fixture(autouse=True)
def mock_meta_send(monkeypatch):
    monkeypatch.setenv("DEMO_DISABLE_META_SEND", "1")
    calls = []

    async def fake_send(to: str, text: str) -> dict:
        message_id = f"fake-{len(calls) + 1}"
        calls.append({"to": to, "text": text, "messageId": message_id})
        return {"messages": [{"id": message_id}]}

    monkeypatch.setattr(services, "send_message", fake_send)
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
    with TestClient(app) as test_client:
        yield test_client
