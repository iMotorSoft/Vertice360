from __future__ import annotations

from typing import Any

import httpx

from backend.modules.messaging.providers.gupshup.whatsapp import client as gupshup_client
from backend.modules.vertice360_orquestador_demo import services


def _wire_supervisor_send_stubs(monkeypatch) -> dict[str, Any]:
    state: dict[str, Any] = {
        "messages": [],
        "provider_updates": [],
        "events": [],
        "provider_columns_ensured": 0,
    }

    context = {
        "ticket_id": "ticket-1",
        "conversation_id": "conv-1",
        "lead_id": "lead-1",
        "phone_e164": "5491130946950",
        "assigned_advisor_phone_e164": None,
    }

    def get_ticket_context(conn: Any, ticket_id: str):  # noqa: ARG001
        if ticket_id != "ticket-1":
            return None
        return dict(context)

    def insert_message(
        conn: Any,  # noqa: ARG001
        *,
        conversation_id: str,
        lead_id: str,
        direction: str,
        actor: str,
        text: str,
        provider_message_id: str | None = None,
        provider_meta: dict[str, Any] | None = None,
    ):
        row = {
            "id": "msg-out-1",
            "conversation_id": conversation_id,
            "lead_id": lead_id,
            "direction": direction,
            "actor": actor,
            "text": text,
            "provider_message_id": provider_message_id,
            "provider_meta_jsonb": provider_meta or {},
        }
        state["messages"].append(row)
        return row

    def update_ticket_activity(
        conn: Any,  # noqa: ARG001
        ticket_id: str,
        *,
        stage: str | None = None,  # noqa: ARG001
        project_id: str | None = None,  # noqa: ARG001
        assigned_advisor_id: str | None = None,  # noqa: ARG001
        last_message_snippet: str | None = None,  # noqa: ARG001
        visit_scheduled_at: Any | None = None,  # noqa: ARG001
    ):
        return {
            "id": ticket_id,
            "stage": "En seguimiento",
            "last_activity_at": "2026-02-27T00:00:00+00:00",
            "last_message_snippet": last_message_snippet,
        }

    def ensure_messages_provider_columns(conn: Any):  # noqa: ARG001
        state["provider_columns_ensured"] += 1

    def update_message_provider_result(
        conn: Any,  # noqa: ARG001
        *,
        message_id: str,
        provider_name: str,
        provider_status: str,
        provider_message_id: str | None,
        provider_response: dict[str, Any] | None,
        provider_error: str | None,
        sent_at: Any | None,
    ):
        row = {
            "message_id": message_id,
            "provider_name": provider_name,
            "provider_status": provider_status,
            "provider_message_id": provider_message_id,
            "provider_response": provider_response or {},
            "provider_error": provider_error,
            "sent_at": sent_at,
        }
        state["provider_updates"].append(row)
        return row

    def insert_event(
        conn: Any,  # noqa: ARG001
        *,
        correlation_id: str,
        domain: str,
        name: str,
        actor: str,
        payload: dict[str, Any] | None = None,
    ):
        event = {
            "id": f"evt-{len(state['events']) + 1}",
            "correlation_id": correlation_id,
            "domain": domain,
            "name": name,
            "actor": actor,
            "payload": payload or {},
        }
        state["events"].append(event)
        return event

    def run_in_transaction(callback):
        return callback(object())

    monkeypatch.setattr(services.repo, "get_ticket_context", get_ticket_context)
    monkeypatch.setattr(services.repo, "insert_message", insert_message)
    monkeypatch.setattr(services.repo, "update_ticket_activity", update_ticket_activity)
    monkeypatch.setattr(services.repo, "ensure_messages_provider_columns", ensure_messages_provider_columns)
    monkeypatch.setattr(services.repo, "update_message_provider_result", update_message_provider_result)
    monkeypatch.setattr(services.repo, "insert_event", insert_event)
    monkeypatch.setattr(services.db, "run_in_transaction", run_in_transaction)
    return state


def _wire_gupshup_config(monkeypatch) -> None:
    monkeypatch.setattr(services.globalVar, "GUPSHUP_APP_NAME", "test-app", raising=False)
    monkeypatch.setattr(services.globalVar, "GUPSHUP_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(services.globalVar, "GUPSHUP_WA_SENDER", "+5491100000000", raising=False)
    monkeypatch.setattr(
        services.globalVar,
        "get_gupshup_wa_sender_provider_value",
        lambda: "5491100000000",
        raising=False,
    )

    monkeypatch.setattr(
        gupshup_client.GupshupConfig,
        "from_env",
        classmethod(
            lambda cls: gupshup_client.GupshupConfig(
                base_url="https://api.gupshup.io",
                api_key="test-key",
                app_name="test-app",
                sender_e164="+5491100000000",
                source_number="5491100000000",
            )
        ),
    )


def test_supervisor_send_success(client, monkeypatch) -> None:
    state = _wire_supervisor_send_stubs(monkeypatch)
    _wire_gupshup_config(monkeypatch)

    async def fake_post(self, url: str, *, data=None, headers=None, timeout=None):  # noqa: ANN001, ARG001
        assert str(url).endswith("/wa/api/v1/msg")
        assert (data or {}).get("destination") == "+5491130946950"
        assert timeout == 15.0
        request = httpx.Request("POST", str(url))
        return httpx.Response(200, json={"messageId": "gs-out-123"}, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    response = client.post(
        "/api/demo/vertice360-orquestador/supervisor/send",
        json={
            "ticket_id": "ticket-1",
            "text": "Hola desde supervisor",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["send_ok"] is True
    assert payload["provider"] == "gupshup"
    assert payload["provider_message_id"] == "gs-out-123"
    assert payload["error"] is None
    assert payload["message_id"] == "msg-out-1"
    assert payload["ticket_id"] == "ticket-1"

    assert state["provider_columns_ensured"] == 1
    assert len(state["provider_updates"]) == 1
    assert state["provider_updates"][0]["provider_status"] == "sent"
    assert state["provider_updates"][0]["provider_message_id"] == "gs-out-123"


def test_supervisor_send_error(client, monkeypatch) -> None:
    state = _wire_supervisor_send_stubs(monkeypatch)
    _wire_gupshup_config(monkeypatch)

    async def fake_post(self, url: str, *, data=None, headers=None, timeout=None):  # noqa: ANN001, ARG001
        request = httpx.Request("POST", str(url))
        raise httpx.ReadTimeout("timed out", request=request)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    response = client.post(
        "/api/demo/vertice360-orquestador/supervisor/send",
        json={
            "ticket_id": "ticket-1",
            "text": "Hola desde supervisor",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["send_ok"] is False
    assert payload["provider"] == "gupshup"
    assert payload["provider_message_id"] is None
    assert payload["error"] == "gupshup_timeout"
    assert payload["message_id"] == "msg-out-1"
    assert payload["ticket_id"] == "ticket-1"

    assert state["provider_columns_ensured"] == 1
    assert len(state["provider_updates"]) == 1
    assert state["provider_updates"][0]["provider_status"] == "error"
    assert state["provider_updates"][0]["provider_error"] == "gupshup_timeout"
