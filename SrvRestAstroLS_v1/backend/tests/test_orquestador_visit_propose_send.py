from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from backend.modules.messaging.providers.gupshup.whatsapp import client as gupshup_client
from backend.modules.vertice360_orquestador_demo import services


def _wire_visit_propose_stubs(monkeypatch) -> dict[str, Any]:
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
        "phone_e164": "+5491130946950",
    }

    def get_ticket_context(conn: Any, ticket_id: str):  # noqa: ARG001
        if ticket_id != "ticket-1":
            return None
        return dict(context)

    def find_advisor_by_name(conn: Any, advisor_name: str | None):  # noqa: ARG001
        if not advisor_name:
            return None
        return {
            "id": "advisor-1",
            "full_name": advisor_name,
        }

    def create_visit_proposal(
        conn: Any,  # noqa: ARG001
        *,
        ticket_id: str,
        conversation_id: str,
        lead_id: str,
        advisor_id: str | None,
        mode: str,
        option1: Any | None,
        option2: Any | None,
        option3: Any | None,
        message_out: str,
    ):
        return {
            "id": "proposal-1",
            "ticket_id": ticket_id,
            "conversation_id": conversation_id,
            "lead_id": lead_id,
            "advisor_id": advisor_id,
            "mode": mode,
            "option1": option1,
            "option2": option2,
            "option3": option3,
            "message_out": message_out,
        }

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
            "id": "msg-propose-1",
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
        stage: str | None = None,
        project_id: str | None = None,  # noqa: ARG001
        assigned_advisor_id: str | None = None,  # noqa: ARG001
        last_message_snippet: str | None = None,  # noqa: ARG001
        visit_scheduled_at: Any | None = None,  # noqa: ARG001
    ):
        return {
            "id": ticket_id,
            "stage": stage,
            "last_activity_at": "2026-03-01T00:00:00+00:00",
            "last_message_snippet": last_message_snippet,
            "visit_scheduled_at": visit_scheduled_at,
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
        row = {
            "id": f"evt-{len(state['events']) + 1}",
            "correlation_id": correlation_id,
            "domain": domain,
            "name": name,
            "actor": actor,
            "payload": payload or {},
        }
        state["events"].append(row)
        return row

    def run_in_transaction(callback):
        return callback(object())

    monkeypatch.setattr(services.repo, "get_ticket_context", get_ticket_context)
    monkeypatch.setattr(services.repo, "find_advisor_by_name", find_advisor_by_name)
    monkeypatch.setattr(services.repo, "create_visit_proposal", create_visit_proposal)
    monkeypatch.setattr(services.repo, "insert_message", insert_message)
    monkeypatch.setattr(services.repo, "update_ticket_activity", update_ticket_activity)
    monkeypatch.setattr(services.repo, "ensure_messages_provider_columns", ensure_messages_provider_columns)
    monkeypatch.setattr(services.repo, "update_message_provider_result", update_message_provider_result)
    monkeypatch.setattr(services.repo, "insert_event", insert_event)
    monkeypatch.setattr(services.db, "run_in_transaction", run_in_transaction)

    return state


def _wire_gupshup_enabled(monkeypatch) -> None:
    monkeypatch.setattr(services.globalVar, "gupshup_whatsapp_enabled", lambda: True, raising=False)
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


def test_visit_propose_sends_gupshup_and_persists_provider_result(client, monkeypatch) -> None:
    state = _wire_visit_propose_stubs(monkeypatch)
    _wire_gupshup_enabled(monkeypatch)

    async def fake_post(self, url: str, *, data=None, headers=None, timeout=None):  # noqa: ANN001, ARG001
        assert str(url).endswith("/wa/api/v1/msg")
        assert (data or {}).get("destination") == "+5491130946950"
        assert timeout == 15.0
        request = httpx.Request("POST", str(url))
        return httpx.Response(200, json={"messageId": "gs-propose-123"}, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    option1 = datetime(2026, 3, 2, 13, 0, tzinfo=timezone.utc).isoformat()
    response = client.post(
        "/api/demo/vertice360-orquestador/visit/propose",
        json={
            "ticket_id": "ticket-1",
            "advisor_name": "Asesor Demo",
            "message_out": "Te propongo una visita mañana.",
            "mode": "propose",
            "option1": option1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticket_id"] == "ticket-1"
    assert payload["proposal_id"] == "proposal-1"
    assert payload["message_id"] == "msg-propose-1"
    assert payload["send_ok"] is True
    assert payload["provider"] == "gupshup"
    assert payload["provider_status"] == "sent"
    assert payload["provider_message_id"] == "gs-propose-123"
    assert payload["provider_error"] is None

    assert state["provider_columns_ensured"] == 1
    assert len(state["provider_updates"]) == 1
    assert state["provider_updates"][0]["message_id"] == "msg-propose-1"
    assert state["provider_updates"][0]["provider_status"] == "sent"
    assert state["provider_updates"][0]["provider_message_id"] == "gs-propose-123"


def test_visit_propose_skips_when_gupshup_disabled(client, monkeypatch) -> None:
    state = _wire_visit_propose_stubs(monkeypatch)
    monkeypatch.setattr(services.globalVar, "gupshup_whatsapp_enabled", lambda: False, raising=False)

    async def fail_if_called(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("Gupshup HTTP should not be called when disabled")

    monkeypatch.setattr(httpx.AsyncClient, "post", fail_if_called)

    response = client.post(
        "/api/demo/vertice360-orquestador/visit/propose",
        json={
            "ticket_id": "ticket-1",
            "message_out": "Te propongo una visita mañana.",
            "mode": "propose",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticket_id"] == "ticket-1"
    assert payload["send_ok"] is False
    assert payload["provider"] == "gupshup"
    assert payload["provider_status"] == "skipped"
    assert payload["provider_message_id"] is None
    assert payload["provider_error"] == "missing_config"

    assert state["provider_columns_ensured"] == 1
    assert len(state["provider_updates"]) == 1
    assert state["provider_updates"][0]["provider_status"] == "skipped"
    assert state["provider_updates"][0]["provider_error"] == "missing_config"
