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
    initial_project_code: str | None,
) -> dict[str, Any]:
    projects = {
        "BULNES_966_ALMAGRO": {
            "id": "project-bulnes",
            "code": "BULNES_966_ALMAGRO",
            "name": "Bulnes 966 — Almagro",
            "description": "Monoambientes y 2 ambientes con solarium y bicicletero en Almagro.",
            "tags": ["Inversion", "Almagro", "Solarium", "Bicicletero"],
            "asset_short_copy": "Ideal inversion o primera vivienda en Almagro.",
            "asset_chips": ["Inversion", "Almagro", "Solarium"],
        },
        "GDR_3760_SAAVEDRA": {
            "id": "project-gdr",
            "code": "GDR_3760_SAAVEDRA",
            "name": "GDR 3760 — Saavedra",
            "description": "3 ambientes adaptable a 4 con balcones aterrazados y parrilla.",
            "tags": ["Saavedra", "Parrilla", "Terraza", "Familia"],
            "asset_short_copy": "Vivi como en una casa con terraza privada.",
            "asset_chips": ["Saavedra", "Parrilla", "Terraza"],
        },
        "MANZANARES_3277": {
            "id": "project-manzanares",
            "code": "MANZANARES_3277",
            "name": "Manzanares 3277 — Nunez",
            "description": "Espacios inteligentes con seguridad y domotica.",
            "tags": ["Domotica", "Seguridad", "Premium"],
            "asset_short_copy": "Confort moderno y detalles premium.",
            "asset_chips": ["Domotica", "Seguridad", "Premium"],
        },
    }

    state: dict[str, Any] = {
        "messages": [],
        "events": [],
        "lead_exists": bool(existing_contact),
        "conversation_exists": bool(existing_contact),
        "ticket_exists": bool(existing_contact),
    }

    lead = {"id": "lead-1", "phone_e164": "+5491130946950"}
    conversation = {"id": "conv-1"}
    initial_project = projects.get(str(initial_project_code or "").upper())
    ticket = {
        "id": "ticket-1",
        "conversation_id": "conv-1",
        "lead_id": "lead-1",
        "project_id": initial_project.get("id") if initial_project else None,
        "stage": "Nuevo",
        "summary_jsonb": {},
        "last_message_snippet": "",
        "inbound_line_key": "gupshup:5491111111111",
        "inbound_line_phone": "+5491111111111",
    }

    def _project_by_id(project_id: str | None) -> dict[str, Any] | None:
        for project in projects.values():
            if str(project.get("id")) == str(project_id or ""):
                return project
        return None

    def get_project_by_code(conn: Any, project_code: str):  # noqa: ARG001
        return projects.get(str(project_code or "").strip().upper())

    def get_project_by_id(conn: Any, project_id: str):  # noqa: ARG001
        for project in projects.values():
            if str(project.get("id")) == str(project_id or ""):
                return {
                    "id": project["id"],
                    "code": project["code"],
                    "name": project["name"],
                }
        return None

    def list_project_codes(conn: Any):  # noqa: ARG001
        return sorted(projects.keys())

    def get_project_context(conn: Any, project_code: str):  # noqa: ARG001
        project = projects.get(str(project_code or "").strip().upper())
        if not project:
            return None
        return {
            "id": project["id"],
            "code": project["code"],
            "name": project["name"],
            "description": project["description"],
            "tags": project["tags"],
            "asset_short_copy": project["asset_short_copy"],
            "asset_chips": project["asset_chips"],
        }

    def get_project_capabilities(conn: Any, force_refresh: bool = False):  # noqa: ARG001
        return {
            "project_overview": True,
            "location": True,
            "amenities": True,
            "marketing_assets": True,
            "unit_types": True,
            "prices_by_rooms": True,
            "availability_by_rooms": True,
            "financing": True,
            "delivery_date": True,
        }

    def get_project_overview(conn: Any, project_code: str):  # noqa: ARG001
        project = projects.get(str(project_code or "").strip().upper())
        if not project:
            return None
        return {
            "code": project["code"],
            "name": project["name"],
            "description": project["description"],
            "tags": project["tags"],
            "_source_table": "projects",
            "location_jsonb": {"neighborhood": "Saavedra" if "GDR" in project["code"] else "Almagro"},
        }

    def get_project_marketing_assets(conn: Any, project_code: str):  # noqa: ARG001
        project = projects.get(str(project_code or "").strip().upper())
        if not project:
            return []
        return [
            {
                "title": project["name"],
                "short_copy": project["asset_short_copy"],
                "chips": project["asset_chips"],
                "_source_table": "marketing_assets",
            }
        ]

    def get_unit_types(conn: Any, project_code: str):  # noqa: ARG001
        if str(project_code or "").strip().upper() != "MANZANARES_3277":
            return []
        return [
            {"rooms": "1", "label": "1 ambiente", "_source_table": "units"},
            {"rooms": "2", "label": "2 ambientes", "_source_table": "units"},
        ]

    def get_prices_by_rooms(
        conn: Any,  # noqa: ARG001
        project_code: str,
        rooms: int | None = None,
        currency: str | None = None,
    ):
        project_upper = str(project_code or "").strip().upper()
        if project_upper not in {"MANZANARES_3277", "BULNES_966_ALMAGRO"}:
            return []
        if project_upper == "BULNES_966_ALMAGRO":
            rows = [
                {"rooms": "1", "price": 79000, "currency": "USD", "status": "active", "_source_table": "units"},
                {"rooms": "2", "price": 101000, "currency": "USD", "status": "active", "_source_table": "units"},
                {"rooms": "2", "price": 108000, "currency": "USD", "status": "active", "_source_table": "units"},
            ]
        else:
            rows = [
                {"rooms": "2", "price": 130000, "currency": "USD", "status": "active", "_source_table": "units"},
                {"rooms": "2", "price": 145000, "currency": "USD", "status": "active", "_source_table": "units"},
                {"rooms": "3", "price": 210000, "currency": "USD", "status": "active", "_source_table": "units"},
                {"rooms": "3", "price": 220000, "currency": "USD", "status": "active", "_source_table": "units"},
            ]
        if rooms is not None:
            rows = [row for row in rows if str(row.get("rooms")) == str(rooms)]
        if currency:
            rows = [row for row in rows if str(row.get("currency")).upper() == str(currency).upper()]
        return rows

    def get_availability_by_rooms(conn: Any, project_code: str, rooms: int | None = None):  # noqa: ARG001
        project_upper = str(project_code or "").strip().upper()
        if project_upper not in {"MANZANARES_3277", "BULNES_966_ALMAGRO"}:
            return []
        if project_upper == "BULNES_966_ALMAGRO":
            if rooms is not None:
                return [{"status": "disponible", "units_count": 2 if int(rooms) == 2 else 1, "_source_table": "units"}]
            return [
                {"status": "disponible", "units_count": 3, "_source_table": "units"},
            ]
        rows = [
            {"status": "disponible", "units_count": 3, "_source_table": "units"},
            {"status": "reservada", "units_count": 1, "_source_table": "units"},
        ]
        if rooms is not None:
            return [{"status": "disponible", "units_count": 2 if int(rooms) == 2 else 1, "_source_table": "units"}]
        return rows

    def get_financing_terms(conn: Any, project_code: str):  # noqa: ARG001
        if str(project_code or "").strip().upper() != "MANZANARES_3277":
            return None
        return {
            "source_table": "payment_plans",
            "items": [{"financing_data": "Anticipo 40% + 24 cuotas en USD"}],
        }

    def get_delivery_info(conn: Any, project_code: str):  # noqa: ARG001
        if str(project_code or "").strip().upper() != "MANZANARES_3277":
            return None
        return {
            "source_table": "projects",
            "items": [{"delivery_date": "2027-06-30", "status": "en obra"}],
        }

    def list_demo_units(
        conn: Any,  # noqa: ARG001
        project_code: str,
        *,
        rooms: int | None = None,
        currency: str | None = None,
    ):
        project_upper = str(project_code or "").strip().upper()
        if project_upper not in {"MANZANARES_3277", "BULNES_966_ALMAGRO"}:
            return []
        if project_upper == "BULNES_966_ALMAGRO":
            rows = [
                {"rooms_count": 1, "availability_status": "available", "currency": "USD", "list_price": 79000, "_source_table": "demo_units"},
                {"rooms_count": 2, "availability_status": "available", "currency": "USD", "list_price": 101000, "_source_table": "demo_units"},
                {"rooms_count": 2, "availability_status": "available", "currency": "USD", "list_price": 108000, "_source_table": "demo_units"},
            ]
        else:
            rows = [
                {"rooms_count": 2, "availability_status": "available", "currency": "USD", "list_price": 130000, "_source_table": "demo_units"},
                {"rooms_count": 2, "availability_status": "available", "currency": "USD", "list_price": 145000, "_source_table": "demo_units"},
                {"rooms_count": 3, "availability_status": "available", "currency": "USD", "list_price": 210000, "_source_table": "demo_units"},
                {"rooms_count": 3, "availability_status": "available", "currency": "USD", "list_price": 220000, "_source_table": "demo_units"},
            ]
        if rooms is not None:
            rows = [row for row in rows if int(row.get("rooms_count") or 0) == int(rooms)]
        if currency:
            rows = [row for row in rows if str(row.get("currency")).upper() == str(currency).upper()]
        return rows

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
        return dict(ticket) if state["ticket_exists"] else None

    def create_ticket(
        conn: Any,
        conversation_id: str,
        lead_id: str,
        project_id: str | None,
        last_message_snippet: str,
    ):
        state["ticket_exists"] = True
        ticket["conversation_id"] = conversation_id
        ticket["lead_id"] = lead_id
        ticket["project_id"] = project_id
        ticket["last_message_snippet"] = last_message_snippet
        return dict(ticket)

    def update_ticket_activity(
        conn: Any,
        ticket_id: str,
        *,
        stage: str | None = None,
        project_id: str | None = None,
        assigned_advisor_id: str | None = None,  # noqa: ARG001
        last_message_snippet: str | None = None,
        visit_scheduled_at: Any | None = None,  # noqa: ARG001
    ):
        ticket["id"] = ticket_id
        if stage is not None:
            ticket["stage"] = stage
        if project_id is not None:
            ticket["project_id"] = project_id
        if last_message_snippet is not None:
            ticket["last_message_snippet"] = last_message_snippet
        return dict(ticket)

    def update_ticket_requirements(conn: Any, ticket_id: str, requirements_patch: dict[str, Any]):
        summary = ticket.get("summary_jsonb")
        if not isinstance(summary, dict):
            summary = {}
        current_requirements = summary.get("requirements")
        if not isinstance(current_requirements, dict):
            current_requirements = {}
        merged_requirements = {**current_requirements, **(requirements_patch or {})}
        ticket["summary_jsonb"] = {**summary, "requirements": merged_requirements}
        return dict(ticket)

    def merge_ticket_summary(conn: Any, ticket_id: str, summary_patch: dict[str, Any]):
        summary = ticket.get("summary_jsonb")
        if not isinstance(summary, dict):
            summary = {}
        ticket["summary_jsonb"] = {**summary, **(summary_patch or {})}
        return dict(ticket)

    def touch_conversation_activity(conn: Any, conversation_id: str):  # noqa: ARG001
        return None

    def set_ticket_inbound_line(
        conn: Any,
        *,
        ticket_id: str,
        inbound_line_key: str | None,
        inbound_line_phone: str | None = None,
    ):
        if inbound_line_key:
            ticket["inbound_line_key"] = inbound_line_key
        if inbound_line_phone:
            ticket["inbound_line_phone"] = inbound_line_phone
        return {
            "id": ticket_id,
            "inbound_line_key": ticket.get("inbound_line_key"),
            "inbound_line_phone": ticket.get("inbound_line_phone"),
        }

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

    def list_conversation_messages(conn: Any, conversation_id: str, *, limit: int = 200):  # noqa: ARG001
        return list(state["messages"])[-int(limit) :]

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
            "id": f"evt-{len(state['events']) + 1}",
            "correlation_id": correlation_id,
            "domain": domain,
            "name": name,
            "actor": actor,
            "payload": payload or {},
        }
        state["events"].append(event)
        return event

    def get_ticket_detail(conn: Any, ticket_id: str):  # noqa: ARG001
        summary = ticket.get("summary_jsonb")
        if not isinstance(summary, dict):
            summary = {}
        requirements = summary.get("requirements")
        if not isinstance(requirements, dict):
            requirements = {}
        project = _project_by_id(ticket.get("project_id"))
        return {
            "ticket_id": ticket_id,
            "project_id": ticket.get("project_id"),
            "project_code": project.get("code") if project else None,
            "project_name": project.get("name") if project else None,
            "stage": ticket.get("stage"),
            "summary_jsonb": summary,
            "req_ambientes": requirements.get("ambientes"),
            "req_presupuesto": requirements.get("presupuesto"),
            "req_moneda": requirements.get("moneda"),
            "inbound_line_key": ticket.get("inbound_line_key"),
            "inbound_line_phone": ticket.get("inbound_line_phone"),
        }

    def ensure_messages_provider_columns(conn: Any):  # noqa: ARG001
        return None

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
        return {
            "id": message_id,
            "provider_name": provider_name,
            "provider_status": provider_status,
            "provider_message_id": provider_message_id,
            "provider_response_jsonb": provider_response or {},
            "provider_error": provider_error,
            "sent_at": sent_at,
        }

    monkeypatch.setattr(services.repo, "get_project_by_code", get_project_by_code)
    monkeypatch.setattr(services.repo, "get_project_by_id", get_project_by_id)
    monkeypatch.setattr(services.repo, "list_project_codes", list_project_codes)
    monkeypatch.setattr(services.repo, "get_project_context", get_project_context)
    monkeypatch.setattr(services.repo, "get_project_capabilities", get_project_capabilities)
    monkeypatch.setattr(services.repo, "get_project_overview", get_project_overview)
    monkeypatch.setattr(services.repo, "get_project_marketing_assets", get_project_marketing_assets)
    monkeypatch.setattr(services.repo, "get_unit_types", get_unit_types)
    monkeypatch.setattr(services.repo, "get_prices_by_rooms", get_prices_by_rooms)
    monkeypatch.setattr(services.repo, "get_availability_by_rooms", get_availability_by_rooms)
    monkeypatch.setattr(services.repo, "get_financing_terms", get_financing_terms)
    monkeypatch.setattr(services.repo, "get_delivery_info", get_delivery_info)
    monkeypatch.setattr(services.repo, "list_demo_units", list_demo_units)
    monkeypatch.setattr(services.repo, "get_lead_by_phone", get_lead_by_phone)
    monkeypatch.setattr(services.repo, "create_lead", create_lead)
    monkeypatch.setattr(services.repo, "touch_lead", touch_lead)
    monkeypatch.setattr(services.repo, "get_open_conversation_for_lead", get_open_conversation_for_lead)
    monkeypatch.setattr(services.repo, "create_conversation", create_conversation)
    monkeypatch.setattr(services.repo, "get_ticket_by_conversation", get_ticket_by_conversation)
    monkeypatch.setattr(services.repo, "create_ticket", create_ticket)
    monkeypatch.setattr(services.repo, "update_ticket_activity", update_ticket_activity)
    monkeypatch.setattr(services.repo, "update_ticket_requirements", update_ticket_requirements)
    monkeypatch.setattr(services.repo, "merge_ticket_summary", merge_ticket_summary)
    monkeypatch.setattr(services.repo, "touch_conversation_activity", touch_conversation_activity)
    monkeypatch.setattr(services.repo, "set_ticket_inbound_line", set_ticket_inbound_line)
    monkeypatch.setattr(services.repo, "insert_message", insert_message)
    monkeypatch.setattr(services.repo, "list_conversation_messages", list_conversation_messages)
    monkeypatch.setattr(services.repo, "insert_event", insert_event)
    monkeypatch.setattr(services.repo, "get_ticket_detail", get_ticket_detail)
    monkeypatch.setattr(services.repo, "ensure_messages_provider_columns", ensure_messages_provider_columns)
    monkeypatch.setattr(services.repo, "update_message_provider_result", update_message_provider_result)

    def run_in_transaction(callback):
        return callback(object())

    monkeypatch.setattr(services.db, "run_in_transaction", run_in_transaction)
    state["ticket"] = ticket
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
    _wire_repo_stubs(monkeypatch, existing_contact=False, initial_project_code=None)
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
    _assert_no_forbidden_terms(payload["vera_reply_text"])


def test_project_alias_matching_selects_gdr_and_emits_event(monkeypatch) -> None:
    state = _wire_repo_stubs(monkeypatch, existing_contact=True, initial_project_code=None)

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
            text="me interesa gdr 3760 en saavedra",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-002",
        )
    )

    assert payload["project_code"] == "GDR_3760_SAAVEDRA"
    assert payload["project_selected"] is True
    assert payload["vera_reply_variant"] == "project_selected"
    assert "GDR 3760" in payload["vera_reply_text"]

    event_names = [event.get("name") for event in state["events"]]
    assert "orq.project.selected" in event_names


def test_project_qa_amenities_uses_project_context(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="GDR_3760_SAAVEDRA",
    )

    monkeypatch.setattr(services.globalVar, "OpenAI_Key", None, raising=False)

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
            text="que amenities tiene?",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-003",
        )
    )

    assert payload["vera_reply_variant"] == "project_qa"
    assert "parrilla" in payload["vera_reply_text"].lower() or "terraza" in payload["vera_reply_text"].lower()
    _assert_no_forbidden_terms(payload["vera_reply_text"])


def test_project_price_query_uses_db_rows(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="MANZANARES_3277",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-price-001",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="dame precio de 2 ambientes",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-price-001",
        )
    )

    assert payload["vera_reply_variant"] == "project_qa"
    assert "2 ambientes" in payload["vera_reply_text"].lower()
    assert "usd" in payload["vera_reply_text"].lower()

    event_names = [event.get("name") for event in state["events"]]
    assert "orq.qa.requested" in event_names
    assert "orq.qa.responded" in event_names


def test_project_financing_query_uses_db_terms(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="MANZANARES_3277",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-fin-001",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="hay financiacion?",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-fin-001",
        )
    )

    assert payload["vera_reply_variant"] == "project_qa"
    assert "financiaci" in payload["vera_reply_text"].lower()
    assert "24 cuotas" in payload["vera_reply_text"].lower()


def test_project_delivery_query_uses_db_date(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="MANZANARES_3277",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-del-001",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="cuando entregan?",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-del-001",
        )
    )

    assert payload["vera_reply_variant"] == "project_qa"
    assert "entrega" in payload["vera_reply_text"].lower()
    assert "30/06/2027" in payload["vera_reply_text"]


def test_project_unit_types_query_routes_to_unit_types(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="MANZANARES_3277",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-types-001",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="que tipologias hay?",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-types-001",
        )
    )

    assert payload["vera_reply_variant"] == "project_qa"
    reply = payload["vera_reply_text"].lower()
    assert ("tipolog" in reply) or ("disponibles en" in reply)
    assert "amb" in reply


def test_missing_project_asks_once_then_handoff(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code=None,
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-missing-001",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    first = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="cuanto sale?",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-missing-001",
        )
    )
    assert first["vera_reply_variant"] == "choose_project_once"
    assert "sobre qué proyecto" in first["vera_reply_text"].lower()

    second = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="precio?",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-missing-002",
        )
    )
    assert second["vera_reply_variant"] == "project_handoff"
    assert "necesito el proyecto" in second["vera_reply_text"].lower()
    assert "bulnes 966" not in second["vera_reply_text"].lower()


def test_followup_price_and_types_flow_with_project_override(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=False,
        initial_project_code=None,
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": f"gs-out-followup-{len(state['messages'])}",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    step1 = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="hola",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-followup-1",
        )
    )
    assert step1["vera_reply_variant"] in {"onboarding", "choose_project", "project_qa"}

    step2 = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="me das los precios",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-followup-2",
        )
    )
    assert step2["vera_reply_variant"] in {"choose_project_once", "project_handoff", "project_qa"}
    assert "sobre qué proyecto" in step2["vera_reply_text"].lower() or "necesito el proyecto" in step2["vera_reply_text"].lower()

    step3 = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="Sobre Manzanares 3277 cuantas unidades son disponible",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-followup-3",
        )
    )
    assert step3["project_code"] == "MANZANARES_3277"
    assert "dispon" in step3["vera_reply_text"].lower()

    step4 = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="de que tipo",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-followup-4",
        )
    )
    assert "amb" in step4["vera_reply_text"].lower()
    assert "disponibles" in step4["vera_reply_text"].lower() or "tipolog" in step4["vera_reply_text"].lower()

    step5 = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="sus precios",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-followup-5",
        )
    )
    assert step5["vera_reply_variant"] == "project_qa"
    assert "2 amb" in step5["vera_reply_text"].lower()
    assert "3 amb" in step5["vera_reply_text"].lower()
    assert "usd" in step5["vera_reply_text"].lower()
    assert "desarroll" not in step5["vera_reply_text"].lower()  # avoid generic overview fallback


def test_explicit_project_override_emits_overridden_event(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="GDR_3760_SAAVEDRA",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-override-1",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="sobre manzanares 3277, dame precio de 2 ambientes",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-override-1",
        )
    )

    assert payload["project_code"] == "MANZANARES_3277"
    assert payload.get("project_overridden") is True
    assert "usd" in payload["vera_reply_text"].lower()

    event_names = [event.get("name") for event in state["events"]]
    assert "orq.project.overridden" in event_names

def test_visit_requested_updates_stage_and_events_without_auto_schedule(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="MANZANARES_3277",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-004",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="coordinamos una visita?",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-004",
        )
    )

    assert payload["vera_reply_variant"] == "visit_requested"
    assert payload["stage"] == "Pendiente de visita"
    assert "pendiente de visita" in payload["vera_reply_text"].lower()
    assert "asesor" in payload["vera_reply_text"].lower()
    assert re.search(r"\b(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b", payload["vera_reply_text"].lower()) is None
    assert re.search(r"\b\d{1,2}(:\d{2})?\s?(hs|h)\b", payload["vera_reply_text"].lower()) is None

    event_names = [event.get("name") for event in state["events"]]
    assert "orq.stage.updated" in event_names
    assert "orq.visit.requested" in event_names


@pytest.mark.parametrize("text", ["se puede visitar?", "lo puedo ver?"])
def test_visit_intent_variants_trigger_handoff(monkeypatch, text: str) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="MANZANARES_3277",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-visit-var",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text=text,
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-visit-var",
        )
    )

    assert payload["vera_reply_variant"] == "visit_requested"
    assert payload["stage"] == "Pendiente de visita"
    assert "pendiente de visita" in payload["vera_reply_text"].lower()
    assert "mañana" in payload["vera_reply_text"].lower() or "tarde" in payload["vera_reply_text"].lower()
    assert "domotica" not in payload["vera_reply_text"].lower()

    event_names = [event.get("name") for event in state["events"]]
    assert "orq.stage.updated" in event_names
    assert "orq.visit.requested" in event_names


def test_visit_request_after_price_does_not_fallback_to_overview(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="BULNES_966_ALMAGRO",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-visit-flow",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    first = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="dame precio de 2 ambientes",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-visit-flow-1",
        )
    )
    assert first["vera_reply_variant"] == "project_qa"
    assert "precio" in first["vera_reply_text"].lower() or "usd" in first["vera_reply_text"].lower()

    second = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="puedo visitarlo",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-visit-flow-2",
        )
    )

    assert second["vera_reply_variant"] == "visit_requested"
    assert second["stage"] == "Pendiente de visita"
    assert "pendiente de visita" in second["vera_reply_text"].lower()
    assert "solarium" not in second["vera_reply_text"].lower()
    assert "bicicletero" not in second["vera_reply_text"].lower()

    event_names = [event.get("name") for event in state["events"]]
    assert "orq.stage.updated" in event_names
    assert "orq.visit.requested" in event_names
    summary = state["ticket"].get("summary_jsonb") or {}
    assert summary.get("last_intent") == "visit_request"


def test_after_human_schedule_vera_can_follow_up(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="BULNES_966_ALMAGRO",
    )

    state["messages"].append(
        {
            "id": "msg-seed-1",
            "conversation_id": "conv-1",
            "lead_id": "lead-1",
            "direction": "out",
            "actor": "advisor",
            "text": "Te propongo martes 11 hs para la visita.",
            "provider_message_id": None,
            "provider_meta_jsonb": {},
        }
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-005",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="perfecto, confirmado",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-005",
        )
    )

    assert payload["vera_reply_variant"] == "post_human_followup"
    assert "dirección" in payload["vera_reply_text"].lower()


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
        ("gdr 3760", None, None),
        ("presupuesto 95.000 ars", 95000, "ARS"),
        ("2 ambientes", None, None),
    ],
)
def test_parse_budget_currency(text: str, expected_budget: int | None, expected_currency: str | None) -> None:
    parsed = services.parse_budget_currency(text)
    assert parsed.get("presupuesto") == expected_budget
    assert parsed.get("moneda") == expected_currency
