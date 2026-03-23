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

    def list_projects(conn: Any):  # noqa: ARG001
        return [
            {
                "id": project["id"],
                "code": project["code"],
                "name": project["name"],
                "description": project["description"],
            }
            for project in projects.values()
        ]

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
        project_upper = str(project_code or "").strip().upper()
        if project_upper == "BULNES_966_ALMAGRO":
            return {
                "source_table": "projects",
                "items": [{"delivery_date": "2026-12-15", "status": "en terminaciones"}],
            }
        if project_upper != "MANZANARES_3277":
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
        if project_upper not in {"MANZANARES_3277", "BULNES_966_ALMAGRO", "GDR_3760_SAAVEDRA"}:
            return []
        if project_upper == "BULNES_966_ALMAGRO":
            rows = [
                {
                    "project_code": project_upper,
                    "unit_id": "bulnes-1a",
                    "unit_code": "B-1A",
                    "typology": "1 ambiente",
                    "rooms_label": "1 ambiente",
                    "rooms_count": 1,
                    "surface_total_m2": 34.5,
                    "currency": "USD",
                    "list_price": 79000,
                    "availability_status": "available",
                    "features_jsonb": ["patio"],
                    "_source_table": "demo_units",
                },
                {
                    "project_code": project_upper,
                    "unit_id": "bulnes-a7c",
                    "unit_code": "A-7C",
                    "typology": "2 ambientes",
                    "rooms_label": "2 ambientes",
                    "rooms_count": 2,
                    "surface_total_m2": 59.2,
                    "currency": "USD",
                    "list_price": 148000,
                    "availability_status": "available",
                    "features_jsonb": ["balcon", "lavadero"],
                    "_source_table": "demo_units",
                },
                {
                    "project_code": project_upper,
                    "unit_id": "bulnes-2b",
                    "unit_code": "B-2B",
                    "typology": "2 ambientes",
                    "rooms_label": "2 ambientes",
                    "rooms_count": 2,
                    "surface_total_m2": 57.1,
                    "currency": "USD",
                    "list_price": 108000,
                    "availability_status": "available",
                    "features_jsonb": ["cochera"],
                    "_source_table": "demo_units",
                },
            ]
        elif project_upper == "GDR_3760_SAAVEDRA":
            rows = [
                {
                    "project_code": project_upper,
                    "unit_id": "gdr-8a",
                    "unit_code": "G-8A",
                    "typology": "3 ambientes",
                    "rooms_label": "3 ambientes",
                    "rooms_count": 3,
                    "surface_total_m2": 88.0,
                    "currency": "USD",
                    "list_price": 310000,
                    "availability_status": "available",
                    "features_jsonb": ["balcon", "parrilla"],
                    "_source_table": "demo_units",
                },
                {
                    "project_code": project_upper,
                    "unit_id": "gdr-p2",
                    "unit_code": "P-2",
                    "typology": "2 ambientes",
                    "rooms_label": "2 ambientes",
                    "rooms_count": 2,
                    "surface_total_m2": 61.4,
                    "currency": "USD",
                    "list_price": 275700,
                    "availability_status": "available",
                    "features_jsonb": ["cochera"],
                    "_source_table": "demo_units",
                },
            ]
        else:
            rows = [
                {
                    "project_code": project_upper,
                    "unit_id": "manz-2a",
                    "unit_code": "M-2A",
                    "typology": "2 ambientes",
                    "rooms_label": "2 ambientes",
                    "rooms_count": 2,
                    "surface_total_m2": 56.0,
                    "currency": "USD",
                    "list_price": 130000,
                    "availability_status": "available",
                    "features_jsonb": ["en suite"],
                    "_source_table": "demo_units",
                },
                {
                    "project_code": project_upper,
                    "unit_id": "manz-2b",
                    "unit_code": "M-2B",
                    "typology": "2 ambientes",
                    "rooms_label": "2 ambientes",
                    "rooms_count": 2,
                    "surface_total_m2": 58.0,
                    "currency": "USD",
                    "list_price": 145000,
                    "availability_status": "available",
                    "features_jsonb": ["lavadero"],
                    "_source_table": "demo_units",
                },
                {
                    "project_code": project_upper,
                    "unit_id": "manz-3a",
                    "unit_code": "M-3A",
                    "typology": "3 ambientes",
                    "rooms_label": "3 ambientes",
                    "rooms_count": 3,
                    "surface_total_m2": 84.0,
                    "currency": "USD",
                    "list_price": 210000,
                    "availability_status": "available",
                    "features_jsonb": ["jardin"],
                    "_source_table": "demo_units",
                },
                {
                    "project_code": project_upper,
                    "unit_id": "manz-3b",
                    "unit_code": "M-3B",
                    "typology": "3 ambientes",
                    "rooms_label": "3 ambientes",
                    "rooms_count": 3,
                    "surface_total_m2": 86.5,
                    "currency": "USD",
                    "list_price": 220000,
                    "availability_status": "available",
                    "features_jsonb": ["walk in closet"],
                    "_source_table": "demo_units",
                },
            ]
        if rooms is not None:
            rows = [row for row in rows if int(row.get("rooms_count") or 0) == int(rooms)]
        if currency:
            rows = [row for row in rows if str(row.get("currency")).upper() == str(currency).upper()]
        return rows

    def list_all_demo_units(conn: Any, *, rooms: int | None = None, currency: str | None = None):  # noqa: ARG001
        rows: list[dict[str, Any]] = []
        for code, project in projects.items():
            for unit in list_demo_units(conn, code, rooms=rooms, currency=currency):
                row = dict(unit)
                row["project_code"] = code
                row["project_name"] = project["name"]
                rows.append(row)
        return rows

    def find_demo_unit_by_code(conn: Any, unit_code: str):  # noqa: ARG001
        target = str(unit_code or "").strip().upper()
        for row in list_all_demo_units(conn):
            if str(row.get("unit_code") or "").strip().upper() == target:
                return row
        return None

    def get_units_global_filtered(  # noqa: PLR0913
        conn: Any,  # noqa: ARG001
        *,
        min_surface_total_m2: float | None = None,
        max_surface_total_m2: float | None = None,
        rooms_count: int | None = None,
        feature_key: str | None = None,
        has_garden: bool | None = None,
        has_patio: bool | None = None,
        has_garage: bool | None = None,
        has_storage: bool | None = None,
        availability: str | None = None,
    ):
        rows = list_all_demo_units(conn, rooms=rooms_count, currency=None)
        filtered: list[dict[str, Any]] = []
        for row in rows:
            surface_total = row.get("surface_total_m2")
            if min_surface_total_m2 is not None and float(surface_total or 0) < float(min_surface_total_m2):
                continue
            if max_surface_total_m2 is not None and float(surface_total or 0) > float(max_surface_total_m2):
                continue
            if availability and str(row.get("availability_status") or "").strip().lower() != str(availability).strip().lower():
                continue
            features = [str(item).strip().lower() for item in row.get("features_jsonb") or []]
            if feature_key == "jardin" and "jardin" not in features:
                continue
            if feature_key == "balcon" and "balcon" not in features:
                continue
            if feature_key == "patio" and "patio" not in features:
                continue
            if isinstance(has_garden, bool) and ("jardin" in features) is not has_garden:
                continue
            if isinstance(has_patio, bool) and ("patio" in features) is not has_patio:
                continue
            if isinstance(has_garage, bool) and ("cochera" in features) is not has_garage:
                continue
            if isinstance(has_storage, bool) and ("baulera" in features) is not has_storage:
                continue
            filtered.append(dict(row))
        return filtered

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
    monkeypatch.setattr(services.repo, "list_projects", list_projects)
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
    monkeypatch.setattr(services.repo, "list_all_demo_units", list_all_demo_units)
    monkeypatch.setattr(services.repo, "find_demo_unit_by_code", find_demo_unit_by_code)
    monkeypatch.setattr(services.repo, "get_units_global_filtered", get_units_global_filtered)
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


def test_selected_project_typo_cracteristicas_resolves_to_features(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code=None,
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": f"gs-out-typo-{text}",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    first = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="h",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-typo-0",
        )
    )
    second = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="3760",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-typo-1",
        )
    )
    third = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="cracteristicas",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-typo-2",
        )
    )

    assert first["vera_reply_variant"] in {"choose_project", "choose_project_once", "project_handoff", "onboarding", "project_qa"}
    assert second["project_code"] == "GDR_3760_SAAVEDRA"
    assert second["vera_reply_variant"] == "project_selected"
    assert third["vera_reply_variant"] == "project_qa"
    assert "sobre qué proyecto" not in third["vera_reply_text"].lower()
    assert "parrilla" in third["vera_reply_text"].lower() or "terraza" in third["vera_reply_text"].lower()


def test_selected_project_typo_presio_resolves_to_price(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="BULNES_966_ALMAGRO",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-typo-price",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="presio",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-typo-price",
        )
    )

    assert payload["vera_reply_variant"] == "project_qa"
    assert "sobre qué proyecto" not in payload["vera_reply_text"].lower()
    assert "usd" in payload["vera_reply_text"].lower() or "precio" in payload["vera_reply_text"].lower()


def test_selected_project_typo_entrga_resolves_to_delivery(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="BULNES_966_ALMAGRO",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-typo-delivery",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="entrga",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-typo-delivery",
        )
    )

    assert payload["vera_reply_variant"] == "project_qa"
    assert "sobre qué proyecto" not in payload["vera_reply_text"].lower()
    assert "entrega" in payload["vera_reply_text"].lower()


def test_typo_without_project_selected_keeps_safe_behavior(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code=None,
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-typo-safe",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="cracteristicas",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-typo-safe",
        )
    )

    assert payload["vera_reply_variant"] in {"choose_project", "choose_project_once", "project_handoff"}
    assert "proyecto" in payload["vera_reply_text"].lower()


def test_choose_project_not_triggered_for_high_similarity_known_intent(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="GDR_3760_SAAVEDRA",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-typo-no-choose",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="cracteristicas",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-typo-no-choose",
        )
    )

    assert payload["vera_reply_variant"] == "project_qa"
    assert "sobre qué proyecto" not in payload["vera_reply_text"].lower()


def test_single_output_with_typo_input(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="BULNES_966_ALMAGRO",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-typo-single",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="finanacion",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-typo-single",
        )
    )

    assert payload["vera_reply_variant"] == "project_qa"
    assert "sobre qué proyecto" not in payload["vera_reply_text"].lower()


def test_greeting_hola_returns_natural_greeting_not_hard_choose_project(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code=None,
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-greeting-hola",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="hola",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-greeting-hola",
        )
    )

    assert payload["vera_reply_variant"] == "social_greeting"
    assert "hola" in payload["vera_reply_text"].lower()
    assert "bulnes 966" in payload["vera_reply_text"].lower()


def test_greeting_hi_returns_natural_response(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code=None,
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-greeting-hi",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="hi",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-greeting-hi",
        )
    )

    assert payload["vera_reply_variant"] == "social_greeting"
    assert "hola" in payload["vera_reply_text"].lower()


def test_ack_gracias_without_context_does_not_fall_to_choose_project_hard(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code=None,
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-ack-gracias",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="gracias",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-ack-gracias",
        )
    )

    assert payload["vera_reply_variant"] == "social_ack"
    assert "gracias" in payload["vera_reply_text"].lower()
    assert "sobre qué proyecto" not in payload["vera_reply_text"].lower()


def test_ack_ok_with_selected_project_does_not_reset_context(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="GDR_3760_SAAVEDRA",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-ack-ok",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="ok",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-ack-ok",
        )
    )

    assert payload["vera_reply_variant"] == "social_ack"
    assert "gdr 3760" in payload["vera_reply_text"].lower()
    assert "sobre qué proyecto" not in payload["vera_reply_text"].lower()


def test_thumbs_up_does_not_trigger_overview_or_choose_project(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="GDR_3760_SAAVEDRA",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-ack-thumb",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="👍",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-ack-thumb",
        )
    )

    assert payload["vera_reply_variant"] == "social_ack"
    assert "sobre qué proyecto" not in payload["vera_reply_text"].lower()
    assert "desarrollo" not in payload["vera_reply_text"].lower()


def test_ack_with_pending_offer_still_uses_affirm_flow(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="BULNES_966_ALMAGRO",
    )
    state["ticket"]["summary_jsonb"] = {
        "pending_offer_type": "PRICE_BREAKDOWN_BY_ROOMS",
        "pending_offer_project": "BULNES_966_ALMAGRO",
        "pending_offer_payload": {"currency": "USD"},
    }

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-ack-pending",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="dale",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-ack-pending",
        )
    )

    assert payload["vera_reply_variant"] == "pending_offer_price_breakdown"
    assert "bulnes 966" in payload["vera_reply_text"].lower()


def test_social_messages_single_output(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code=None,
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-social-single",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="perfecto",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-social-single",
        )
    )

    assert payload["vera_reply_variant"] == "social_ack"
    assert payload["vera_reply_text"].count("?") <= 1


def test_global_scope_override_surface_filter_does_not_require_project(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="BULNES_966_ALMAGRO",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-global-surface",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="No importa el proyecto listado departamento más grandes que 50mts cuadrados",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-global-surface",
        )
    )

    assert payload["vera_reply_variant"] == "global_unit_filter_search"
    assert "varios proyectos" in payload["vera_reply_text"].lower()
    assert "sobre qué proyecto" not in payload["vera_reply_text"].lower()


def test_global_scope_override_persists_for_immediate_followup(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="BULNES_966_ALMAGRO",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-global-followup",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    first = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="No importa el proyecto listado departamento más grandes que 50mts cuadrados",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-global-followup-1",
        )
    )
    second = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="Los que tengan departamentos más grandes que 50 mts cuadrados",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-global-followup-2",
        )
    )

    summary = state["ticket"].get("summary_jsonb") or {}
    assert first["vera_reply_variant"] == "global_unit_filter_search"
    assert second["vera_reply_variant"] == "global_unit_filter_search"
    assert summary.get("last_search_scope") == "global"


def test_single_output_for_rooms_count_and_global_override(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="MANZANARES_3277",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": f"gs-out-rooms-{len(state['messages'])}",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    first = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="Cantidad de unidades 2 ambientes",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-rooms-1",
        )
    )
    second = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="Quiero todas las unidades de 2 ambientes",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-rooms-2",
        )
    )
    third = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="En todos los proyectos",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-rooms-3",
        )
    )
    fourth = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="En todos",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-rooms-4",
        )
    )

    outbound = [row for row in state["messages"] if row.get("direction") == "out"]
    summary = state["ticket"].get("summary_jsonb") or {}

    assert len(outbound) == 4
    assert first["vera_reply_variant"] == "project_units_by_rooms_count"
    assert "2 unidades de 2 ambientes" in first["vera_reply_text"].lower()
    assert second["vera_reply_variant"] == "project_units_by_rooms_list"
    assert "m-2a" in second["vera_reply_text"].lower()
    assert "m-3a" not in second["vera_reply_text"].lower()
    assert third["vera_reply_variant"] == "global_units_by_rooms_list"
    assert "tomando todos los proyectos" in third["vera_reply_text"].lower()
    assert "sobre qué proyecto" not in third["vera_reply_text"].lower()
    assert fourth["vera_reply_variant"] == "global_units_by_rooms_list"
    assert "tomando todos los proyectos" in fourth["vera_reply_text"].lower()
    assert "sobre qué proyecto" not in fourth["vera_reply_text"].lower()
    assert summary.get("last_search_scope") == "global"
    assert (summary.get("last_rooms_query") or {}).get("rooms_count") == 2


def test_active_rooms_filter_projects_question_returns_matching_projects(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="MANZANARES_3277",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": f"gs-out-projects-active-{len(state['messages'])}",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="Cantidad de unidades 2 ambientes",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-projects-active-1",
        )
    )
    asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="En todos los proyectos",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-projects-active-2",
        )
    )
    third = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="cuáles son los proyectos",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-projects-active-3",
        )
    )

    reply = third["vera_reply_text"].lower()
    assert third["vera_reply_variant"] == "projects_matching_active_filter"
    assert "unidades de 2 ambientes" in reply
    assert "bulnes 966" in reply
    assert "manzanares 3277" in reply
    assert "sobre qué proyecto" not in reply


def test_projects_question_without_active_filter_returns_general_list(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code=None,
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-projects-general",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="cuáles son los proyectos",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-projects-general",
        )
    )

    assert payload["vera_reply_variant"] == "project_catalog"
    assert "hoy tengo estos proyectos" in payload["vera_reply_text"].lower()


def test_single_output_for_projects_matching_active_filter(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="MANZANARES_3277",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": f"gs-out-projects-single-{len(state['messages'])}",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="Cantidad de unidades 2 ambientes",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-projects-single-1",
        )
    )
    asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="En todos los proyectos",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-projects-single-2",
        )
    )
    third = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="en cuáles",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-projects-single-3",
        )
    )

    outbound = [row for row in state["messages"] if row.get("direction") == "out"]
    assert len(outbound) == 3
    assert third["vera_reply_variant"] == "projects_matching_active_filter"
    assert "sobre qué proyecto" not in third["vera_reply_text"].lower()


def test_feature_filter_global_override_projects_question_uses_active_filter(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="MANZANARES_3277",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": f"gs-out-projects-feature-{len(state['messages'])}",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="unidades con balcón",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-projects-feature-1",
        )
    )
    asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="en todos",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-projects-feature-2",
        )
    )
    third = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="cuáles son los proyectos",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-projects-feature-3",
        )
    )

    reply = third["vera_reply_text"].lower()
    assert third["vera_reply_variant"] == "projects_matching_active_filter"
    assert "balcón" in third["vera_reply_text"].lower() or "balcon" in reply
    assert "bulnes 966" in reply
    assert "gdr 3760" in reply


def test_single_output_for_feature_filter_chains(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="MANZANARES_3277",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": f"gs-out-feature-chain-{len(state['messages'])}",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    first = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="Cantidad de unidades 2 ambientes",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-feature-chain-1",
        )
    )
    second = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="En todos los proyectos",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-feature-chain-2",
        )
    )
    third = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="de estos departamentos cuáles tiene balcón",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-feature-chain-3",
        )
    )
    fourth = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="dame el departamento más grande con balcón, su precio y proyecto",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-feature-chain-4",
        )
    )

    outbound = [row for row in state["messages"] if row.get("direction") == "out"]
    summary = state["ticket"].get("summary_jsonb") or {}
    assert len(outbound) == 4
    assert first["vera_reply_variant"] == "project_units_by_rooms_count"
    assert second["vera_reply_variant"] == "global_units_by_rooms_count"
    assert third["vera_reply_variant"] == "active_set_feature_filter"
    assert "a-7c" in third["vera_reply_text"].lower()
    assert fourth["vera_reply_variant"] == "active_set_feature_extreme"
    assert "a-7c" in fourth["vera_reply_text"].lower()
    assert summary.get("last_subject_unit_code") == "A-7C"


def test_single_output_for_result_set_ranking_queries(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code=None,
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": f"gs-out-ranking-{len(state['messages'])}",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    first = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="departamentos con balcon",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-ranking-1",
        )
    )
    second = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="de estos cual es el mas grande",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-ranking-2",
        )
    )
    third = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="me das los tres mas grandes en forma descendiente por mt cuadrado",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-ranking-3",
        )
    )

    outbound = [row for row in state["messages"] if row.get("direction") == "out"]
    summary = state["ticket"].get("summary_jsonb") or {}
    assert len(outbound) == 3
    assert first["vera_reply_variant"] == "global_unit_feature_search"
    assert second["vera_reply_variant"] == "unit_list_followup"
    assert third["vera_reply_variant"] == "unit_list_followup"
    reply = third["vera_reply_text"].lower()
    assert "las 2 más grandes" in reply
    assert "1. g-8a" in reply
    assert "2. a-7c" in reply
    assert "sobre qué proyecto" not in reply
    assert [row.get("unit_code") for row in summary.get("last_result_units") or []][:2] == ["G-8A", "A-7C"]



def test_single_output_for_project_comparison_after_unit_result_set(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code=None,
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": f"gs-out-project-compare-{len(state['messages'])}",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    first = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="departamentos con balcon",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-project-compare-1",
        )
    )
    second = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="de estos cual es el mas grande",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-project-compare-2",
        )
    )
    third = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="de todos los proyectos cual es el proyecto con mas metros cuadrados construido",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-project-compare-3",
        )
    )

    outbound = [row for row in state["messages"] if row.get("direction") == "out"]
    summary = state["ticket"].get("summary_jsonb") or {}
    reply = third["vera_reply_text"].lower()

    assert len(outbound) == 3
    assert first["vera_reply_variant"] == "global_unit_feature_search"
    assert second["vera_reply_variant"] == "unit_list_followup"
    assert third["vera_reply_variant"] == "project_comparison_surface"
    assert "tomando solo las unidades demo" in reply or "no tengo cargado el total de metros cuadrados construidos" in reply
    assert "ultimo listado" not in reply
    assert "balcon" not in reply
    assert third["vera_reply_text"].count("?") <= 1
    assert summary.get("last_result_units") == []
    assert summary.get("active_filter") is None



def test_global_surface_filter_returns_units_over_threshold(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="BULNES_966_ALMAGRO",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-global-threshold",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="cualquiera con más de 50 m2",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-global-threshold",
        )
    )

    reply = payload["vera_reply_text"].lower()
    assert "88" in reply
    assert "61,4" in reply or "61" in reply
    assert "50" in reply
    assert "varios proyectos" in reply


def test_global_scope_phrase_any_project_forces_global_search(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="BULNES_966_ALMAGRO",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-global-any-project",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="no importa el proyecto, mostrame los que tienen balcón",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-global-any-project",
        )
    )

    assert payload["vera_reply_variant"] == "global_unit_feature_search"
    assert "sobre qué proyecto" not in payload["vera_reply_text"].lower()


def test_selected_project_not_used_when_user_says_no_importa_el_proyecto(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="BULNES_966_ALMAGRO",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-global-selected-override",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="No importa el proyecto listado departamento más grandes que 50mts cuadrados",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-global-selected-override",
        )
    )

    assert payload["vera_reply_variant"] == "global_unit_filter_search"
    assert payload["project_code"] == "BULNES_966_ALMAGRO"
    assert state["ticket"].get("project_id") == "project-bulnes"


def test_single_output_for_global_surface_query(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="BULNES_966_ALMAGRO",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-global-single",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="cualquiera con más de 50 m2",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-global-single",
        )
    )

    assert payload["vera_reply_variant"] == "global_unit_filter_search"
    assert payload["vera_reply_text"].count("?") <= 1


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


def test_semantic_conversation_flow_prioritizes_catalog_and_visit_without_residual_reply(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="GDR_3760_SAAVEDRA",
    )
    send_calls: list[str] = []

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        send_calls.append(text)
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": f"gs-out-semantic-{len(send_calls)}",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    step1 = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="Cuales son las otras obras",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-semantic-1",
        )
    )
    assert step1["vera_reply_variant"] == "project_catalog"
    assert "bulnes 966" in step1["vera_reply_text"].lower()
    assert "manzanares 3277" in step1["vera_reply_text"].lower()
    assert "saavedra" not in step1["vera_reply_text"].lower()

    step2 = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="Que proyecto tenés no Saavedra",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-semantic-2",
        )
    )
    assert step2["vera_reply_variant"] == "project_catalog"
    assert "bulnes 966" in step2["vera_reply_text"].lower()
    assert "manzanares 3277" in step2["vera_reply_text"].lower()
    assert "saavedra" not in step2["vera_reply_text"].lower()

    step3 = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="Bulnes 966",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-semantic-3",
        )
    )
    assert step3["vera_reply_variant"] == "project_selected"
    assert step3["project_code"] == "BULNES_966_ALMAGRO"

    step4 = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="Entrega",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-semantic-4",
        )
    )
    assert step4["vera_reply_variant"] == "project_qa"
    assert "2026" in step4["vera_reply_text"]
    assert "entrega" in step4["vera_reply_text"].lower()

    step5 = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="Puedo tener reunion",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-semantic-5",
        )
    )
    assert step5["vera_reply_variant"] == "intent_clarify"
    assert "visita al proyecto" in step5["vera_reply_text"].lower()
    assert "asesor" in step5["vera_reply_text"].lower()
    assert "monoambientes" not in step5["vera_reply_text"].lower()
    assert "solarium" not in step5["vera_reply_text"].lower()

    step6 = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="Cita",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-semantic-6",
        )
    )
    assert step6["vera_reply_variant"] == "visit_requested"
    assert step6["stage"] == "Pendiente de visita"
    assert "pendiente de visita" in step6["vera_reply_text"].lower()
    assert "solarium" not in step6["vera_reply_text"].lower()
    assert "bicicletero" not in step6["vera_reply_text"].lower()

    outbound = [row for row in state["messages"] if row.get("direction") == "out"]
    assert len(send_calls) == 6
    assert len(outbound) == 6
    assert state["ticket"].get("summary_jsonb", {}).get("last_intent") == "visit_request"


@pytest.mark.parametrize("text", ["reunion", "cita", "entrevista", "coordinar"])
def test_ambiguous_meeting_synonyms_ask_short_clarification(monkeypatch, text: str) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="MANZANARES_3277",
    )

    async def fake_send(phone_e164: str, message: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-clarify",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text=text,
            provider="gupshup_whatsapp",
            provider_message_id=f"gs-in-clarify-{text}",
        )
    )

    assert payload["vera_reply_variant"] == "intent_clarify"
    assert payload["vera_reply_text"].count("?") == 1
    assert "visita al proyecto" in payload["vera_reply_text"].lower()
    assert "asesor" in payload["vera_reply_text"].lower()


@pytest.mark.parametrize("text", ["hablar con un asesor", "asesor"])
def test_human_contact_synonyms_skip_overview(monkeypatch, text: str) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="MANZANARES_3277",
    )

    async def fake_send(phone_e164: str, message: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-human-contact",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text=text,
            provider="gupshup_whatsapp",
            provider_message_id=f"gs-in-human-{text}",
        )
    )

    assert payload["vera_reply_variant"] == "human_contact_requested"
    assert "asesor" in payload["vera_reply_text"].lower()
    assert "domotica" not in payload["vera_reply_text"].lower()
    assert len([row for row in state["messages"] if row.get("direction") == "out"]) == 1


@pytest.mark.parametrize("text", ["llamada", "videollamada"])
def test_call_terms_route_to_human_contact_without_overview(monkeypatch, text: str) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="BULNES_966_ALMAGRO",
    )

    async def fake_send(phone_e164: str, message: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-call-contact",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text=text,
            provider="gupshup_whatsapp",
            provider_message_id=f"gs-in-call-{text}",
        )
    )

    assert payload["vera_reply_variant"] == "human_contact_requested"
    assert "asesor" in payload["vera_reply_text"].lower()
    assert "solarium" not in payload["vera_reply_text"].lower()


@pytest.mark.parametrize("text", ["hay?", "cuántos?"])
def test_short_followups_after_availability_keep_intent_and_avoid_overview(monkeypatch, text: str) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="MANZANARES_3277",
    )

    async def fake_send(phone_e164: str, message: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": f"gs-out-short-followup-{len(state['messages'])}",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    first = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="Sobre Manzanares 3277 cuántas unidades son disponible",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-short-followup-1",
        )
    )
    assert "dispon" in first["vera_reply_text"].lower()

    second = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text=text,
            provider="gupshup_whatsapp",
            provider_message_id=f"gs-in-short-followup-{text}",
        )
    )

    assert second["vera_reply_variant"] == "project_qa"
    reply = second["vera_reply_text"].lower()
    assert "dispon" in reply or "hay" in reply
    assert "domotica" not in reply
    assert "premium" not in reply


@pytest.mark.parametrize(
    ("text", "expected_token"),
    [
        ("hay?", "dispon"),
        ("cuántos?", "dispon"),
        ("cuáles?", "amb"),
    ],
)
def test_short_followups_after_price_keep_context_and_avoid_overview(
    monkeypatch,
    text: str,
    expected_token: str,
) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="MANZANARES_3277",
    )

    async def fake_send(phone_e164: str, message: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": f"gs-out-short-price-followup-{len(state['messages'])}",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    first = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="sus precios",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-short-price-followup-1",
        )
    )
    assert "usd" in first["vera_reply_text"].lower()

    second = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text=text,
            provider="gupshup_whatsapp",
            provider_message_id=f"gs-in-short-price-followup-{text}",
        )
    )

    assert second["vera_reply_variant"] == "project_qa"
    reply = second["vera_reply_text"].lower()
    assert expected_token in reply
    assert "domotica" not in reply
    assert "premium" not in reply


def test_partial_project_override_updates_selected_project_for_followup_price(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="GDR_3760_SAAVEDRA",
    )

    async def fake_send(phone_e164: str, message: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": f"gs-out-override-followup-{len(state['messages'])}",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="Bulnes 966",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-override-followup-1",
        )
    )
    asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="precio de 2 ambientes",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-override-followup-2",
        )
    )
    step3 = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="y en Manzanares?",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-override-followup-3",
        )
    )
    step4 = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="sus precios",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-override-followup-4",
        )
    )

    summary = state["ticket"].get("summary_jsonb") or {}
    selected_project = summary.get("selected_project") or {}

    assert step3["vera_reply_variant"] == "project_selected"
    assert step3["project_code"] == "MANZANARES_3277"
    assert step4["vera_reply_variant"] == "project_qa"
    assert "130.000" in step4["vera_reply_text"]
    assert "210.000" in step4["vera_reply_text"]
    assert selected_project.get("code") == "MANZANARES_3277"
    assert summary.get("last_intent") == "PRICE"


def test_mixed_price_and_visit_returns_single_visit_reply_without_overview(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="BULNES_966_ALMAGRO",
    )

    async def fake_send(phone_e164: str, message: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-mixed-visit",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="qué precio tiene y si puedo visitarlo",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-mixed-visit",
        )
    )

    outbound = [row for row in state["messages"] if row.get("direction") == "out"]
    assert payload["vera_reply_variant"] == "visit_requested"
    assert payload["stage"] == "Pendiente de visita"
    assert "pendiente de visita" in payload["vera_reply_text"].lower()
    assert "solarium" not in payload["vera_reply_text"].lower()
    assert len(outbound) == 1


@pytest.mark.parametrize("text", ["ok", "dale", "gracias", "perfecto", "👍"])
def test_ack_messages_do_not_trigger_project_overview(monkeypatch, text: str) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="MANZANARES_3277",
    )

    async def fake_send(phone_e164: str, message: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-ack",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text=text,
            provider="gupshup_whatsapp",
            provider_message_id=f"gs-in-ack-{text}",
        )
    )

    assert payload["vera_reply_variant"] != "project_qa"
    reply = payload["vera_reply_text"].lower()
    assert "domotica" not in reply
    assert "premium" not in reply


def test_clarification_updates_summary_without_fake_visit_intent(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="BULNES_966_ALMAGRO",
    )

    async def fake_send(phone_e164: str, message: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-summary-clarify",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="reunión",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-summary-clarify",
        )
    )

    summary = state["ticket"].get("summary_jsonb") or {}
    assert payload["vera_reply_variant"] == "intent_clarify"
    assert summary.get("last_intent") == "CLARIFY"
    assert "visita al proyecto" in str(summary.get("last_answer_brief") or "").lower()
    assert "asesor" in str(summary.get("last_answer_brief") or "").lower()


def test_global_highest_price_query_returns_exact_project_and_price(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="BULNES_966_ALMAGRO",
    )

    async def fake_send(phone_e164: str, message: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-global-highest",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="me das el precio mas alto de una unidad y de que proyecto",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-global-highest",
        )
    )

    summary = state["ticket"].get("summary_jsonb") or {}
    assert payload["vera_reply_variant"] == "global_price_extreme"
    assert "manzanares 3277" in payload["vera_reply_text"].lower()
    assert "usd 220.000" in payload["vera_reply_text"].lower()
    assert "desde usd" not in payload["vera_reply_text"].lower()
    assert summary.get("last_intent") == "GLOBAL_PRICE_EXTREME"
    assert summary.get("pending_offer_type") == "PRICE_BREAKDOWN_BY_ROOMS"
    assert summary.get("pending_project") == "MANZANARES_3277"


def test_global_highest_price_query_does_not_answer_with_only_range(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="GDR_3760_SAAVEDRA",
    )

    async def fake_send(phone_e164: str, message: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-global-highest-range",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="cuál es la unidad más cara",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-global-highest-range",
        )
    )

    reply = payload["vera_reply_text"].lower()
    assert payload["vera_reply_variant"] == "global_price_extreme"
    assert "unidad con precio más alto" in reply
    assert "desde usd" not in reply


@pytest.mark.parametrize("text", ["sí", "si", "dale", "ok"])
def test_affirm_uses_pending_offer_price_breakdown(monkeypatch, text: str) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="BULNES_966_ALMAGRO",
    )

    async def fake_send(phone_e164: str, message: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": f"gs-out-affirm-{len(state['messages'])}",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    first = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="me das el precio mas alto de una unidad y de que proyecto",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-affirm-1",
        )
    )
    second = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text=text,
            provider="gupshup_whatsapp",
            provider_message_id=f"gs-in-affirm-{text}",
        )
    )

    summary = state["ticket"].get("summary_jsonb") or {}
    assert first["vera_reply_variant"] == "global_price_extreme"
    assert second["vera_reply_variant"] == "pending_offer_price_breakdown"
    assert "manzanares 3277" in second["vera_reply_text"].lower()
    assert "2 ambientes" in second["vera_reply_text"].lower()
    assert "3 ambientes" in second["vera_reply_text"].lower()
    assert "sobre qué proyecto" not in second["vera_reply_text"].lower()
    assert summary.get("pending_offer_type") is None


def test_affirm_without_pending_offer_does_not_fall_to_choose_project_hard(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="BULNES_966_ALMAGRO",
    )

    async def fake_send(phone_e164: str, message: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-affirm-no-pending",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="si",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-affirm-no-pending",
        )
    )

    assert payload["vera_reply_variant"] == "affirm_ack"
    assert "sobre qué proyecto" not in payload["vera_reply_text"].lower()


def test_pending_offer_is_cleared_after_use(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="BULNES_966_ALMAGRO",
    )

    async def fake_send(phone_e164: str, message: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": f"gs-out-pending-clear-{len(state['messages'])}",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="me das el precio mas alto de una unidad y de que proyecto",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-pending-clear-1",
        )
    )
    asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="si",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-pending-clear-2",
        )
    )

    summary = state["ticket"].get("summary_jsonb") or {}
    assert summary.get("pending_offer_type") is None
    assert summary.get("pending_project") is None
    assert summary.get("pending_payload") is None


def test_global_unit_search_by_balcony_does_not_require_project(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code=None,
    )

    async def fake_send(phone_e164: str, message: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-feature-global",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="me listas las unidades con balcón",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-feature-global",
        )
    )

    assert payload["vera_reply_variant"] == "global_unit_feature_search"
    reply = payload["vera_reply_text"].lower()
    assert "bulnes 966" in reply
    assert "gdr 3760" in reply
    assert "sobre qué proyecto" not in reply
    assert len([row for row in state["messages"] if row.get("direction") == "out"]) == 1


def test_any_project_keyword_forces_global_search(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="BULNES_966_ALMAGRO",
    )

    async def fake_send(phone_e164: str, message: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-feature-any",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="cualquiera que las unidades tengan balcon",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-feature-any",
        )
    )

    assert payload["vera_reply_variant"] == "global_unit_feature_search"
    assert "sobre qué proyecto" not in payload["vera_reply_text"].lower()


def test_project_specific_feature_query_returns_yes_no(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code=None,
    )

    async def fake_send(phone_e164: str, message: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-feature-project",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="Bulnes 966 tiene unidades con balcón?",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-feature-project",
        )
    )

    assert payload["vera_reply_variant"] == "project_unit_feature_search"
    assert payload["vera_reply_text"].lower().startswith("sí")
    assert "a-7c" in payload["vera_reply_text"].lower()


def test_unit_specific_feature_query_returns_yes_no(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code=None,
    )

    async def fake_send(phone_e164: str, message: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-feature-unit",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="la unidad A-7C tiene balcón?",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-feature-unit",
        )
    )

    assert payload["vera_reply_variant"] == "unit_feature_check"
    assert payload["vera_reply_text"].lower().startswith("sí")
    assert "lavadero" in payload["vera_reply_text"].lower()


def test_project_typology_feature_query(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code=None,
    )

    async def fake_send(phone_e164: str, message: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-feature-typology",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="en Manzanares hay 2 ambientes con balcón?",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-feature-typology",
        )
    )

    assert payload["vera_reply_variant"] == "project_unit_feature_search"
    assert payload["vera_reply_text"].lower().startswith("no")
    assert "2 ambientes" in payload["vera_reply_text"].lower()


def test_no_choose_project_for_global_feature_search(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="GDR_3760_SAAVEDRA",
    )

    async def fake_send(phone_e164: str, message: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-feature-no-choose",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="qué unidades tienen balcón",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-feature-no-choose",
        )
    )

    assert payload["vera_reply_variant"] == "global_unit_feature_search"
    assert "sobre qué proyecto" not in payload["vera_reply_text"].lower()


def test_feature_search_single_output_no_fallback(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="BULNES_966_ALMAGRO",
    )
    send_calls: list[str] = []

    async def fake_send(phone_e164: str, message: str):  # noqa: ARG001
        send_calls.append(message)
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-feature-single",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="me listás las unidades con cochera",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-feature-single",
        )
    )

    assert payload["vera_reply_variant"] == "global_unit_feature_search"
    assert len(send_calls) == 1
    assert len([row for row in state["messages"] if row.get("direction") == "out"]) == 1
    assert "solarium" not in payload["vera_reply_text"].lower()


def test_surface_query_without_data_returns_specific_no_info_message(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="MANZANARES_3277",
    )
    original_list_demo_units = services.repo.list_demo_units

    def list_demo_units_without_surface(conn: Any, project_code: str, *, rooms: int | None = None, currency: str | None = None):
        rows = original_list_demo_units(conn, project_code, rooms=rooms, currency=currency)
        if str(project_code or "").strip().upper() != "MANZANARES_3277":
            return rows
        return [{**row, "surface_total_m2": None} for row in rows]

    monkeypatch.setattr(services.repo, "list_demo_units", list_demo_units_without_surface)

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-surface-no-info",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="Los metros cuadrados del departamento más grande",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-surface-no-info",
        )
    )

    summary = state["ticket"].get("summary_jsonb") or {}
    reply = payload["vera_reply_text"].lower()
    assert payload["vera_reply_variant"] == "project_qa"
    assert "no tengo información sobre los metros cuadrados de las unidades en manzanares 3277" in reply
    assert "domotica" not in reply
    assert "seguridad" not in reply
    assert summary.get("unresolved_topic") == "surface"


def test_specific_unknown_topic_does_not_fallback_to_project_overview(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="MANZANARES_3277",
    )
    original_list_demo_units = services.repo.list_demo_units

    def list_demo_units_without_surface(conn: Any, project_code: str, *, rooms: int | None = None, currency: str | None = None):
        rows = original_list_demo_units(conn, project_code, rooms=rooms, currency=currency)
        if str(project_code or "").strip().upper() != "MANZANARES_3277":
            return rows
        return [{**row, "surface_total_m2": None} for row in rows]

    monkeypatch.setattr(services.repo, "list_demo_units", list_demo_units_without_surface)

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-surface-no-overview",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="Tenés metros cuadrados de las unidades",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-surface-no-overview",
        )
    )

    reply = payload["vera_reply_text"].lower()
    assert payload["vera_reply_variant"] == "project_qa"
    assert "no tengo información" in reply
    assert "confort moderno" not in reply
    assert "premium" not in reply
    assert "sobre qué proyecto" not in reply


def test_surface_query_with_project_selected_mentions_project_name(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="MANZANARES_3277",
    )
    original_list_demo_units = services.repo.list_demo_units

    def list_demo_units_without_surface(conn: Any, project_code: str, *, rooms: int | None = None, currency: str | None = None):
        rows = original_list_demo_units(conn, project_code, rooms=rooms, currency=currency)
        if str(project_code or "").strip().upper() != "MANZANARES_3277":
            return rows
        return [{**row, "surface_total_m2": None} for row in rows]

    monkeypatch.setattr(services.repo, "list_demo_units", list_demo_units_without_surface)

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-surface-project",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="Tenés metros cuadrados de las unidades",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-surface-project",
        )
    )

    assert "Manzanares 3277" in payload["vera_reply_text"]


def test_surface_query_without_project_selected_returns_generic_no_info(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code=None,
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-surface-generic",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="Tenés metros cuadrados de las unidades",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-surface-generic",
        )
    )

    reply = payload["vera_reply_text"].lower()
    assert payload["vera_reply_variant"] == "project_qa"
    assert "no tengo información sobre los metros cuadrados de las unidades en este momento" in reply
    assert "decime el proyecto" in reply
    assert "sobre qué proyecto" not in reply


def test_known_topic_with_data_still_answers_normally(monkeypatch) -> None:
    _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="GDR_3760_SAAVEDRA",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-surface-known",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="Los metros cuadrados del departamento más grande",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-surface-known",
        )
    )

    reply = payload["vera_reply_text"].lower()
    assert payload["vera_reply_variant"] == "project_qa"
    assert "la unidad más grande" in reply
    assert "88,0 m²" in payload["vera_reply_text"] or "88,0 m2" in reply
    assert "gdr 3760" in reply
    assert "no tengo información" not in reply


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


def test_time_preference_pending_question_morning(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="MANZANARES_3277",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": f"gs-out-time-morning-{len(state['messages'])}",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    first = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="quiero coordinar una visita",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-time-morning-1",
        )
    )
    second = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="mañana",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-time-morning-2",
        )
    )

    summary = state["ticket"].get("summary_jsonb") or {}
    assert first["vera_reply_variant"] == "visit_requested"
    assert second["vera_reply_variant"] == "visit_time_preference"
    assert "por la mañana" in second["vera_reply_text"].lower()
    assert "sobre qué proyecto" not in second["vera_reply_text"].lower()
    assert summary.get("time_preference") == "morning"
    assert summary.get("pending_question_type") is None


def test_time_preference_pending_question_afternoon(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="MANZANARES_3277",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": f"gs-out-time-afternoon-{len(state['messages'])}",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="quiero visitar el proyecto",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-time-afternoon-1",
        )
    )
    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="tarde",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-time-afternoon-2",
        )
    )

    summary = state["ticket"].get("summary_jsonb") or {}
    assert payload["vera_reply_variant"] == "visit_time_preference"
    assert "por la tarde" in payload["vera_reply_text"].lower()
    assert summary.get("time_preference") == "afternoon"


@pytest.mark.parametrize("text", ["es igual", "cualquiera", "me da igual", "indistinto"])
def test_time_preference_pending_question_any_variants(monkeypatch, text: str) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="BULNES_966_ALMAGRO",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": f"gs-out-time-any-{len(state['messages'])}",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="quiero visitar el proyecto",
            provider="gupshup_whatsapp",
            provider_message_id=f"gs-in-time-any-{text}-1",
        )
    )
    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text=text,
            provider="gupshup_whatsapp",
            provider_message_id=f"gs-in-time-any-{text}-2",
        )
    )

    summary = state["ticket"].get("summary_jsonb") or {}
    assert payload["vera_reply_variant"] == "visit_time_preference"
    assert "cualquier franja" in payload["vera_reply_text"].lower()
    assert summary.get("time_preference") == "any"
    assert summary.get("pending_question_type") is None


def test_time_preference_without_pending_question_does_not_trigger_visit_preference(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="MANZANARES_3277",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": "gs-out-time-no-pending",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="mañana",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-time-no-pending",
        )
    )

    summary = state["ticket"].get("summary_jsonb") or {}
    assert payload["vera_reply_variant"] != "visit_time_preference"
    assert summary.get("time_preference") is None
    assert summary.get("pending_question_type") is None


def test_time_preference_clears_pending_question(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="MANZANARES_3277",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": f"gs-out-time-clear-{len(state['messages'])}",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    first = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="coordinamos una visita?",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-time-clear-1",
        )
    )

    summary_after_first = state["ticket"].get("summary_jsonb") or {}
    assert first["vera_reply_variant"] == "visit_requested"
    assert summary_after_first.get("pending_question_type") == "TIME_PREFERENCE"

    asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="tarde",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-time-clear-2",
        )
    )

    summary_after_second = state["ticket"].get("summary_jsonb") or {}
    assert summary_after_second.get("pending_question_type") is None
    assert summary_after_second.get("time_preference") == "afternoon"


def test_time_preference_no_double_output(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="BULNES_966_ALMAGRO",
    )
    send_calls: list[str] = []

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        send_calls.append(text)
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": f"gs-out-time-single-{len(send_calls)}",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="quiero visitarlo",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-time-single-1",
        )
    )
    payload = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="cualquiera",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-time-single-2",
        )
    )

    assert payload["vera_reply_variant"] == "visit_time_preference"
    assert len(send_calls) == 2
    assert len([row for row in state["messages"] if row.get("direction") == "out"]) == 2
    assert "solarium" not in payload["vera_reply_text"].lower()
    assert "sobre qué proyecto" not in payload["vera_reply_text"].lower()


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


def test_surface_filter_plural_then_result_set_followups_work(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="GDR_3760_SAAVEDRA",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": f"gs-out-surface-followup-{len(state['messages'])}",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    first = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="me das departamentos mas grande que 60 mts cuadrados",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-surface-followup-1",
        )
    )
    summary_after_first = dict(state["ticket"].get("summary_jsonb") or {})
    second = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="por precio",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-surface-followup-2",
        )
    )
    third = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="y por metros cual es la mas grande",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-surface-followup-3",
        )
    )
    fourth = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="cuantos metros",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-surface-followup-4",
        )
    )

    assert first["vera_reply_variant"] == "project_qa"
    assert "hoy veo estas unidades" in first["vera_reply_text"].lower()
    assert "unidad más grande" not in first["vera_reply_text"].lower()
    assert summary_after_first.get("last_subject_type") == "unit_list"
    assert len(summary_after_first.get("last_result_units") or []) >= 2

    assert second["vera_reply_variant"] == "unit_list_followup"
    assert "ordenadas por precio" in second["vera_reply_text"].lower()
    assert second["vera_reply_text"].index("P-2") < second["vera_reply_text"].index("G-8A")

    assert third["vera_reply_variant"] == "unit_list_followup"
    assert "la más grande del último listado es la g-8a" in third["vera_reply_text"].lower()

    assert fourth["vera_reply_variant"] == "unit_detail_answer"
    assert "la unidad g-8a tiene 88,0 m² totales" in fourth["vera_reply_text"].lower()
    assert (state["ticket"].get("summary_jsonb") or {}).get("last_subject_unit_code") == "G-8A"


def test_single_output_for_result_set_and_unit_followups(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="GDR_3760_SAAVEDRA",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": f"gs-out-surface-single-{len(state['messages'])}",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="me das departamentos mas grande que 60 mts cuadrados",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-surface-single-1",
        )
    )
    asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="por precio",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-surface-single-2",
        )
    )
    asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="y por metros cual es la mas grande",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-surface-single-3",
        )
    )
    asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="cuantos metros",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-surface-single-4",
        )
    )

    outbound = [row for row in state["messages"] if row.get("direction") == "out"]
    assert len(outbound) == 4


def test_global_scope_ack_and_out_of_scope_selected_project_behave_honestly(monkeypatch) -> None:
    state = _wire_repo_stubs(
        monkeypatch,
        existing_contact=True,
        initial_project_code="MANZANARES_3277",
    )

    async def fake_send(phone_e164: str, text: str):  # noqa: ARG001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": f"gs-out-honest-{len(state['messages'])}",
        }

    monkeypatch.setattr(services, "_send_vera_whatsapp_reply", fake_send)

    first = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="me listás las unidades con balcón",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-honest-1",
        )
    )
    second = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="cualquiera",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-honest-2",
        )
    )
    third = asyncio.run(
        services.ingest_from_provider(
            user_phone="+5491130946950",
            text="expensas",
            provider="gupshup_whatsapp",
            provider_message_id="gs-in-honest-3",
        )
    )

    assert first["vera_reply_variant"] == "global_unit_feature_search"
    assert second["vera_reply_variant"] == "social_ack"
    assert "todos los proyectos" in second["vera_reply_text"].lower()
    assert third["vera_reply_variant"] == "project_sensitive"
    assert "prefiero confirmártelo" in third["vera_reply_text"].lower()


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
