from __future__ import annotations

import asyncio
import re
from typing import Any

import pytest

from backend.modules.vertice360_orquestador_demo import services


FORBIDDEN_WORDS = ("asistente", "bot")


def _wire_repo_stubs(
    monkeypatch,
    *,
    existing_contact: bool,
    inferred_project: dict[str, Any] | None,
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "messages": [],
        "events": [],
        "lead_exists": bool(existing_contact),
        "conversation_exists": bool(existing_contact),
        "ticket_exists": bool(existing_contact),
    }

    lead = {"id": "lead-1", "phone_e164": "+5491130946950"}
    conversation = {"id": "conv-1"}
    ticket = {
        "id": "ticket-1",
        "conversation_id": "conv-1",
        "lead_id": "lead-1",
        "project_id": inferred_project.get("id") if inferred_project else None,
        "stage": "Nuevo",
        "summary_jsonb": {},
    }

    def get_project_by_code(conn: Any, project_code: str):  # noqa: ARG001
        if not inferred_project:
            return None
        if str(project_code or "").strip().upper() == str(inferred_project.get("code") or "").upper():
            return inferred_project
        return None

    def list_project_codes(conn: Any):  # noqa: ARG001
        if inferred_project:
            return [str(inferred_project.get("code") or "")]
        return []

    def get_lead_by_phone(conn: Any, phone_e164: str):  # noqa: ARG001
        return lead if state["lead_exists"] else None

    def create_lead(conn: Any, phone_e164: str, source: str):  # noqa: ARG001
        state["lead_exists"] = True
        return lead

    def touch_lead(conn: Any, lead_id: str, source: str):  # noqa: ARG001
        return lead

    def get_open_conversation_for_lead(conn: Any, lead_id: str):  # noqa: ARG001
        return conversation if state["conversation_exists"] else None

    def create_conversation(conn: Any, lead_id: str):  # noqa: ARG001
        state["conversation_exists"] = True
        return conversation

    def get_ticket_by_conversation(conn: Any, conversation_id: str):  # noqa: ARG001
        return ticket if state["ticket_exists"] else None

    def create_ticket(
        conn: Any,
        conversation_id: str,
        lead_id: str,
        project_id: str | None,
        last_message_snippet: str,  # noqa: ARG001
    ):
        created = dict(ticket)
        created["project_id"] = project_id
        state["ticket_exists"] = True
        ticket.update(created)
        return created

    def update_ticket_activity(
        conn: Any,
        ticket_id: str,
        *,
        stage: str | None = None,
        project_id: str | None = None,
        assigned_advisor_id: str | None = None,  # noqa: ARG001
        last_message_snippet: str | None = None,  # noqa: ARG001
        visit_scheduled_at: Any | None = None,  # noqa: ARG001
    ):
        updated = dict(ticket)
        updated["id"] = ticket_id
        if stage is not None:
            updated["stage"] = stage
        if project_id is not None:
            updated["project_id"] = project_id
        ticket.update(updated)
        return updated

    def update_ticket_requirements(conn: Any, ticket_id: str, requirements_patch: dict[str, Any]):
        summary = ticket.get("summary_jsonb")
        if not isinstance(summary, dict):
            summary = {}
        current_requirements = summary.get("requirements")
        if not isinstance(current_requirements, dict):
            current_requirements = {}
        merged_requirements = {**current_requirements, **(requirements_patch or {})}
        merged_summary = {**summary, "requirements": merged_requirements}
        ticket["summary_jsonb"] = merged_summary
        return dict(ticket)

    def touch_conversation_activity(conn: Any, conversation_id: str):  # noqa: ARG001
        return None

    def insert_message(
        conn: Any,
        *,
        conversation_id: str,
        lead_id: str,
        direction: str,
        actor: str,
        text: str,
        provider_message_id: str | None = None,
        provider_meta: dict[str, Any] | None = None,
    ):
        message_id = f"msg-{len(state['messages']) + 1}"
        row = {
            "id": message_id,
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

    def insert_event(
        conn: Any,
        *,
        correlation_id: str,
        domain: str,
        name: str,
        actor: str,
        payload: dict[str, Any] | None = None,
    ):
        event = {
            "id": "evt-1",
            "correlation_id": correlation_id,
            "domain": domain,
            "name": name,
            "actor": actor,
            "payload": payload or {},
        }
        state["events"].append(event)
        return event

    def get_ticket_detail(conn: Any, ticket_id: str):  # noqa: ARG001
        requirements = {}
        summary = ticket.get("summary_jsonb")
        if isinstance(summary, dict) and isinstance(summary.get("requirements"), dict):
            requirements = dict(summary["requirements"])
        return {
            "ticket_id": ticket_id,
            "project_id": ticket.get("project_id"),
            "project_code": inferred_project.get("code") if inferred_project else None,
            "project_name": inferred_project.get("name") if inferred_project else None,
            "stage": ticket.get("stage"),
            "summary_jsonb": summary if isinstance(summary, dict) else {},
            "req_ambientes": requirements.get("ambientes"),
            "req_presupuesto": requirements.get("presupuesto"),
            "req_moneda": requirements.get("moneda"),
        }

    monkeypatch.setattr(services.repo, "get_project_by_code", get_project_by_code)
    monkeypatch.setattr(services.repo, "list_project_codes", list_project_codes)
    monkeypatch.setattr(services.repo, "get_lead_by_phone", get_lead_by_phone)
    monkeypatch.setattr(services.repo, "create_lead", create_lead)
    monkeypatch.setattr(services.repo, "touch_lead", touch_lead)
    monkeypatch.setattr(services.repo, "get_open_conversation_for_lead", get_open_conversation_for_lead)
    monkeypatch.setattr(services.repo, "create_conversation", create_conversation)
    monkeypatch.setattr(services.repo, "get_ticket_by_conversation", get_ticket_by_conversation)
    monkeypatch.setattr(services.repo, "create_ticket", create_ticket)
    monkeypatch.setattr(services.repo, "update_ticket_activity", update_ticket_activity)
    monkeypatch.setattr(services.repo, "touch_conversation_activity", touch_conversation_activity)
    monkeypatch.setattr(services.repo, "insert_message", insert_message)
    monkeypatch.setattr(services.repo, "insert_event", insert_event)
    monkeypatch.setattr(services.repo, "get_ticket_detail", get_ticket_detail)
    monkeypatch.setattr(services.repo, "update_ticket_requirements", update_ticket_requirements)

    def run_in_transaction(callback):
        return callback(object())

    monkeypatch.setattr(services.db, "run_in_transaction", run_in_transaction)
    return state


def _assert_no_forbidden_terms(text: str) -> None:
    lowered = text.lower()
    for term in FORBIDDEN_WORDS:
        assert term not in lowered
    assert re.search(r"\b(?:ai|ia)\b", lowered) is None


def test_build_board_url_uses_digits_query(monkeypatch) -> None:
    monkeypatch.setattr(
        services.globalVar,
        "V360_DEMO_BOARD_BASE_URL",
        "http://localhost:3062/demo/vertice360-orquestador/",
        raising=False,
    )

    assert (
        services.build_board_url("+5491130946950")
        == "http://localhost:3062/demo/vertice360-orquestador/?cliente=5491130946950"
    )


def test_ingest_from_provider_first_contact_sends_onboarding_copy(monkeypatch) -> None:
    _wire_repo_stubs(monkeypatch, existing_contact=False, inferred_project=None)
    monkeypatch.setattr(
        services.globalVar,
        "V360_DEMO_BOARD_BASE_URL",
        "http://localhost:3062/demo/vertice360-orquestador/",
        raising=False,
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-001",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="hola",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-001",
            provider_meta={"app": "vertice360dev"},
        )
    )

    assert payload["vera_reply_variant"] == "onboarding"
    assert "Te dejo el tablero" in payload["vera_reply_text"]
    assert "Tenés dos opciones" in payload["vera_reply_text"]
    assert "Desde el tablero" in payload["vera_reply_text"]
    assert "Desde este chat" in payload["vera_reply_text"]
    assert "?cliente=" in payload["vera_reply_text"]
    assert "Te acompaño en la forma que prefieras" in payload["vera_reply_text"]
    _assert_no_forbidden_terms(payload["vera_reply_text"])


def test_ingest_from_provider_with_project_uses_project_copy(monkeypatch) -> None:
    inferred_project = {"id": "project-1", "code": "GDR3760", "name": "GDR 3760"}
    _wire_repo_stubs(monkeypatch, existing_contact=True, inferred_project=inferred_project)

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-002",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="Quiero info de GDR3760",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-002",
        )
    )

    assert payload["vera_reply_variant"] == "project"
    assert "Gracias por tu consulta por GDR 3760." in payload["vera_reply_text"]
    _assert_no_forbidden_terms(payload["vera_reply_text"])


def test_ingest_from_provider_without_project_uses_fallback_copy(monkeypatch) -> None:
    _wire_repo_stubs(monkeypatch, existing_contact=True, inferred_project=None)

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-003",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="hola de nuevo",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-003",
        )
    )

    assert payload["vera_reply_variant"] == "choose_project"
    assert "¿Sobre qué proyecto querés consultar" in payload["vera_reply_text"]
    _assert_no_forbidden_terms(payload["vera_reply_text"])


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("busco monoambiente", 1),
        ("quiero 2 amb", 2),
        ("necesito dos ambientes", 2),
        ("me interesan 3 ambientes", 3),
        ("quiero cuatro ambientes", 4),
        ("sin dato", None),
    ],
)
def test_parse_ambientes(text: str, expected: int | None) -> None:
    assert services.parse_ambientes(text) == expected


@pytest.mark.parametrize(
    ("text", "expected_budget", "expected_currency"),
    [
        ("120k usd", 120000, "USD"),
        ("u$s 120.000", 120000, "USD"),
        ("120000 dolares", 120000, "USD"),
        ("120 mil usd", 120000, "USD"),
        ("presupuesto 95.000 ars", 95000, "ARS"),
        ("2 ambientes", None, None),
    ],
)
def test_parse_budget_currency(text: str, expected_budget: int | None, expected_currency: str | None) -> None:
    parsed = services.parse_budget_currency(text)
    assert parsed.get("presupuesto") == expected_budget
    assert parsed.get("moneda") == expected_currency


def test_ingest_from_provider_project_requirements_complete_sets_pending_visit(monkeypatch) -> None:
    inferred_project = {
        "id": "project-1",
        "code": "BULNES_966_ALMAGRO",
        "name": "Bulnes 966 — Almagro",
    }
    state = _wire_repo_stubs(monkeypatch, existing_contact=False, inferred_project=inferred_project)

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-req",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    first = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="Hola, vengo por un anuncio. Me interesa BULNES_966_ALMAGRO (Almagro).",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-req-001",
        )
    )
    assert first["vera_reply_variant"] == "onboarding"

    second = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="quiero un 2 ambientes y tengo 120k usd",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-req-002",
        )
    )

    assert second["vera_reply_variant"] == "project"
    assert second["stage"] == "Pendiente de visita"
    assert second["requirements_complete"] is True
    assert second["requirements"] == {
        "ambientes": 2,
        "presupuesto": 120000,
        "moneda": "USD",
    }
    assert "• Proyecto: Bulnes 966 — Almagro" in second["vera_reply_text"]
    assert "• Unidad: 2 ambientes" in second["vera_reply_text"]
    assert "• Presupuesto: 120.000 USD" in second["vera_reply_text"]
    assert "asesor te va a proponer horarios" in second["vera_reply_text"]
    assert "Decime ambientes" not in second["vera_reply_text"]
    _assert_no_forbidden_terms(second["vera_reply_text"])

    event_names = [event.get("name") for event in state["events"]]
    assert "orq.requirements.captured" in event_names
    assert "orq.stage.updated" in event_names


def test_ingest_from_provider_project_then_requirements_flow(monkeypatch) -> None:
    inferred_project = {
        "id": "project-1",
        "code": "BULNES_966_ALMAGRO",
        "name": "Bulnes 966 — Almagro",
    }
    state = _wire_repo_stubs(monkeypatch, existing_contact=True, inferred_project=inferred_project)

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-flow",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    first = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="Hola, vengo por un anuncio. Me interesa BULNES_966_ALMAGRO (Almagro).",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-flow-001",
        )
    )
    assert first["vera_reply_variant"] == "project"
    assert "Contame cuántos ambientes buscás y tu presupuesto aproximado" in first["vera_reply_text"]

    second = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="quiero un 2 ambientes y tengo 120k usd",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-flow-002",
        )
    )

    assert second["stage"] == "Pendiente de visita"
    assert second["requirements_complete"] is True
    assert "asesor te va a proponer horarios" in second["vera_reply_text"]
    assert "Decime ambientes" not in second["vera_reply_text"]

    event_names = [event.get("name") for event in state["events"]]
    assert "orq.requirements.captured" in event_names
    assert "orq.stage.updated" in event_names
