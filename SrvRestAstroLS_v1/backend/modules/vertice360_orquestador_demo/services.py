from __future__ import annotations

import logging
import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from backend import globalVar
from backend.modules.vertice360_orquestador_demo import db, repo
from backend.telemetry.context import set_correlation_id

logger = logging.getLogger(__name__)

DOMAIN = "vertice360_orquestador_demo"
STAGE_WAITING_CONFIRMATION = "Esperando confirmación"
STAGE_VISIT_CONFIRMED = "Visita confirmada"

ALLOWED_SOURCES = {"whatsapp", "instagram", "web", "meta_ads", "other"}


def demo_db_ready() -> bool:
    return db.can_connect()


def _safe_demo_phone(raw_phone: str | None) -> str:
    digits = "".join(ch for ch in str(raw_phone or "") if ch.isdigit())
    if not digits:
        return ""
    if str(raw_phone or "").strip().startswith("+"):
        return f"+{digits}"
    return f"+{digits}"


def _normalize_phone_e164(raw_phone: str) -> str:
    text = str(raw_phone or "").strip()
    if not text:
        raise ValueError("phone is required")

    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        raise ValueError("phone is invalid")

    if text.startswith("+"):
        return f"+{digits}"

    if digits.startswith("549"):
        return f"+{digits}"

    if digits.startswith("54"):
        return f"+549{digits[2:]}"

    if digits.startswith("9"):
        return f"+54{digits}"

    if digits.startswith("0"):
        return f"+549{digits.lstrip('0')}"

    return f"+549{digits}"


def _normalize_source(source: str | None) -> str:
    clean = str(source or "").strip().lower().replace(" ", "_")
    if clean in ALLOWED_SOURCES:
        return clean
    if clean in {"meta", "metaads", "meta_ad"}:
        return "meta_ads"
    return "whatsapp"


def _normalize_snippet(text: str, limit: int = 160) -> str:
    compact = " ".join(str(text or "").split())
    return compact[:limit]


def _contains_project_code(text: str, code: str) -> bool:
    return bool(
        re.search(
            rf"(?<![A-Z0-9_]){re.escape(code.upper())}(?![A-Z0-9_])",
            text.upper(),
        )
    )


def _infer_project(conn: Any, project_code: str | None, text: str) -> dict[str, Any] | None:
    explicit = str(project_code or "").strip()
    if explicit:
        return repo.get_project_by_code(conn, explicit)

    codes = repo.list_project_codes(conn)
    for code in codes:
        if _contains_project_code(text, code):
            return repo.get_project_by_code(conn, code)
    return None


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    return value


def _event_payload(base: dict[str, Any], **extra: Any) -> dict[str, Any]:
    payload = dict(base)
    payload.update(extra)
    return payload


def bootstrap() -> dict[str, Any]:
    def _tx(conn: Any) -> dict[str, Any]:
        return {
            "whatsapp_demo_phone": _safe_demo_phone(
                globalVar.get_gupshup_wa_sender_e164()
            ),
            "projects": repo.list_projects(conn),
            "marketing_assets": repo.list_marketing_assets(conn),
            "users": repo.list_users(conn),
        }

    return _jsonable(db.run_in_transaction(_tx))


def dashboard(cliente: str | None = None) -> dict[str, Any]:
    def _tx(conn: Any) -> dict[str, Any]:
        rows = repo.get_dashboard_ticket_rows(conn, cliente)
        kpis = repo.get_dashboard_kpis(conn)
        active = repo.find_cliente_activo(conn, str(cliente or "")) if cliente else None

        tickets = []
        for row in rows:
            tickets.append(
                {
                    "ticket_id": row.get("ticket_id"),
                    "stage": row.get("stage"),
                    "project_id": row.get("project_id"),
                    "project_code": row.get("project_code"),
                    "project_name": row.get("project_name"),
                    "lead_id": row.get("lead_id"),
                    "lead_name": row.get("lead_name"),
                    "phone_e164": row.get("phone_e164"),
                    "conversation_id": row.get("conversation_id"),
                    "last_activity_at": row.get("last_activity_at"),
                    "last_message_snippet": _normalize_snippet(
                        str(row.get("last_message_text") or row.get("last_message_snippet") or "")
                    ),
                    "last_message_direction": row.get("last_message_direction"),
                    "last_message_actor": row.get("last_message_actor"),
                    "last_message_at": row.get("last_message_at"),
                    "visit_scheduled_at": row.get("visit_scheduled_at"),
                    "cliente_match": bool(row.get("cliente_match")),
                }
            )

        return {
            "kpis": kpis,
            "tickets": tickets,
            "cliente_activo": active,
        }

    return _jsonable(db.run_in_transaction(_tx))


def ingest_message(
    *,
    phone: str,
    text: str,
    project_code: str | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    normalized_phone = _normalize_phone_e164(phone)
    clean_text = str(text or "").strip()
    if not clean_text:
        raise ValueError("text is required")
    source_value = _normalize_source(source)

    def _tx(conn: Any) -> dict[str, Any]:
        inferred_project = _infer_project(conn, project_code, clean_text)
        inferred_project_id = (
            str(inferred_project.get("id")) if inferred_project and inferred_project.get("id") else None
        )

        lead = repo.get_lead_by_phone(conn, normalized_phone)
        lead_created = lead is None
        if lead is None:
            lead = repo.create_lead(conn, normalized_phone, source_value)
        else:
            lead = repo.touch_lead(conn, str(lead["id"]), source_value)

        lead_id = str(lead["id"])
        conversation = repo.get_open_conversation_for_lead(conn, lead_id)
        conversation_created = conversation is None
        if conversation is None:
            conversation = repo.create_conversation(conn, lead_id)

        conversation_id = str(conversation["id"])
        ticket = repo.get_ticket_by_conversation(conn, conversation_id)
        ticket_created = ticket is None

        snippet = _normalize_snippet(clean_text)
        if ticket is None:
            ticket = repo.create_ticket(
                conn,
                conversation_id=conversation_id,
                lead_id=lead_id,
                project_id=inferred_project_id,
                last_message_snippet=snippet,
            )
        else:
            ticket_project = ticket.get("project_id")
            project_to_set = inferred_project_id if ticket_project is None else None
            ticket = repo.update_ticket_activity(
                conn,
                str(ticket["id"]),
                project_id=project_to_set,
                last_message_snippet=snippet,
            )

        ticket_id = str(ticket["id"])
        repo.touch_conversation_activity(conn, conversation_id)

        message = repo.insert_message(
            conn,
            conversation_id=conversation_id,
            lead_id=lead_id,
            direction="in",
            actor="client",
            text=clean_text,
            provider_meta={"source": source_value},
        )

        if ticket_created:
            repo.insert_event(
                conn,
                correlation_id=ticket_id,
                domain=DOMAIN,
                name="ticket.created",
                actor="system",
                payload=_event_payload(
                    {
                        "ticket_id": ticket_id,
                        "conversation_id": conversation_id,
                        "lead_id": lead_id,
                        "project_id": ticket.get("project_id"),
                        "stage": ticket.get("stage"),
                    }
                ),
            )

        repo.insert_event(
            conn,
            correlation_id=ticket_id,
            domain=DOMAIN,
            name="message.ingested",
            actor="client",
            payload=_event_payload(
                {
                    "ticket_id": ticket_id,
                    "conversation_id": conversation_id,
                    "lead_id": lead_id,
                    "message_id": message.get("id"),
                    "direction": "in",
                    "actor": "client",
                    "text": clean_text,
                }
            ),
        )

        detail = repo.get_ticket_detail(conn, ticket_id)
        return {
            "ticket_id": ticket_id,
            "conversation_id": conversation_id,
            "lead_id": lead_id,
            "project_id": detail.get("project_id") if detail else ticket.get("project_id"),
            "project_code": detail.get("project_code") if detail else None,
            "stage": detail.get("stage") if detail else ticket.get("stage"),
            "message_id": message.get("id"),
            "normalized_phone": normalized_phone,
            "lead_created": lead_created,
            "conversation_created": conversation_created,
            "ticket_created": ticket_created,
        }

    result = db.run_in_transaction(_tx)
    ticket_id = str(result.get("ticket_id"))
    set_correlation_id(ticket_id)
    logger.info(
        "ORQ_INGEST_MESSAGE correlation_id=%s lead_created=%s conversation_created=%s ticket_created=%s phone=%s",
        ticket_id,
        result.get("lead_created"),
        result.get("conversation_created"),
        result.get("ticket_created"),
        normalized_phone,
    )
    return _jsonable(result)


def propose_visit(
    *,
    ticket_id: str,
    advisor_name: str | None,
    option1: datetime | None,
    option2: datetime | None,
    option3: datetime | None,
    message_out: str,
    mode: str,
) -> dict[str, Any]:
    clean_ticket_id = str(ticket_id or "").strip()
    if not clean_ticket_id:
        raise ValueError("ticket_id is required")

    clean_mode = str(mode or "propose").strip().lower()
    if clean_mode not in {"propose", "reschedule"}:
        raise ValueError("mode must be propose or reschedule")

    clean_message_out = str(message_out or "").strip()
    if not clean_message_out:
        raise ValueError("message_out is required")

    def _tx(conn: Any) -> dict[str, Any]:
        context = repo.get_ticket_context(conn, clean_ticket_id)
        if context is None:
            raise KeyError("ticket not found")

        advisor = repo.find_advisor_by_name(conn, advisor_name)
        if advisor_name and advisor is None:
            raise ValueError("advisor_name not found")

        proposal = repo.create_visit_proposal(
            conn,
            ticket_id=clean_ticket_id,
            conversation_id=str(context["conversation_id"]),
            lead_id=str(context["lead_id"]),
            advisor_id=str(advisor["id"]) if advisor else None,
            mode=clean_mode,
            option1=option1,
            option2=option2,
            option3=option3,
            message_out=clean_message_out,
        )

        message = repo.insert_message(
            conn,
            conversation_id=str(context["conversation_id"]),
            lead_id=str(context["lead_id"]),
            direction="out",
            actor="advisor",
            text=clean_message_out,
            provider_meta={
                "mode": clean_mode,
                "proposal_id": str(proposal.get("id")),
                "advisor_name": advisor.get("full_name") if advisor else advisor_name,
            },
        )

        ticket = repo.update_ticket_activity(
            conn,
            clean_ticket_id,
            stage=STAGE_WAITING_CONFIRMATION,
            assigned_advisor_id=str(advisor["id"]) if advisor else None,
            last_message_snippet=_normalize_snippet(clean_message_out),
        )

        event_name = "visit.proposed" if clean_mode == "propose" else "visit.rescheduled"
        repo.insert_event(
            conn,
            correlation_id=clean_ticket_id,
            domain=DOMAIN,
            name=event_name,
            actor="advisor",
            payload={
                "ticket_id": clean_ticket_id,
                "proposal_id": proposal.get("id"),
                "mode": clean_mode,
                "advisor_id": advisor.get("id") if advisor else None,
                "advisor_name": advisor.get("full_name") if advisor else advisor_name,
                "message_id": message.get("id"),
                "option1": proposal.get("option1"),
                "option2": proposal.get("option2"),
                "option3": proposal.get("option3"),
            },
        )

        return {
            "ticket_id": clean_ticket_id,
            "proposal_id": proposal.get("id"),
            "mode": clean_mode,
            "stage": ticket.get("stage"),
            "advisor": advisor,
            "message_id": message.get("id"),
            "option1": proposal.get("option1"),
            "option2": proposal.get("option2"),
            "option3": proposal.get("option3"),
            "visit_scheduled_at": ticket.get("visit_scheduled_at"),
        }

    result = db.run_in_transaction(_tx)
    set_correlation_id(clean_ticket_id)
    logger.info(
        "ORQ_PROPOSE_VISIT correlation_id=%s proposal_id=%s mode=%s",
        clean_ticket_id,
        result.get("proposal_id"),
        clean_mode,
    )
    return _jsonable(result)


def confirm_visit(
    *,
    proposal_id: str,
    confirmed_option: int,
    confirmed_by: str,
) -> dict[str, Any]:
    clean_proposal_id = str(proposal_id or "").strip()
    if not clean_proposal_id:
        raise ValueError("proposal_id is required")

    if confirmed_option not in {1, 2, 3}:
        raise ValueError("confirmed_option must be 1, 2 or 3")

    actor = str(confirmed_by or "").strip().lower()
    if actor not in {"client", "advisor", "supervisor"}:
        raise ValueError("confirmed_by must be client, advisor or supervisor")

    def _tx(conn: Any) -> dict[str, Any]:
        proposal = repo.get_visit_proposal(conn, clean_proposal_id)
        if proposal is None:
            raise KeyError("proposal not found")

        if str(proposal.get("status") or "") == "accepted":
            raise ValueError("proposal already accepted")

        option_key = f"option{confirmed_option}"
        confirmed_at = proposal.get(option_key)
        if confirmed_at is None:
            raise ValueError(f"proposal does not have {option_key}")

        ticket_id = str(proposal["ticket_id"])

        confirmation = repo.insert_visit_confirmation(
            conn,
            proposal_id=clean_proposal_id,
            ticket_id=ticket_id,
            confirmed_option=confirmed_option,
            confirmed_at=confirmed_at,
            confirmed_by=actor,
        )
        repo.mark_visit_proposal_accepted(conn, clean_proposal_id)
        repo.supersede_active_proposals(conn, ticket_id)

        ticket = repo.update_ticket_activity(
            conn,
            ticket_id,
            stage=STAGE_VISIT_CONFIRMED,
            visit_scheduled_at=confirmed_at,
            last_message_snippet=_normalize_snippet(
                f"Visita confirmada (opción {confirmed_option})"
            ),
        )

        repo.insert_event(
            conn,
            correlation_id=ticket_id,
            domain=DOMAIN,
            name="visit.confirmed",
            actor=actor,
            payload={
                "ticket_id": ticket_id,
                "proposal_id": clean_proposal_id,
                "confirmation_id": confirmation.get("id"),
                "confirmed_option": confirmed_option,
                "confirmed_by": actor,
                "confirmed_at": confirmed_at,
            },
        )

        return {
            "ticket_id": ticket_id,
            "proposal_id": clean_proposal_id,
            "confirmation_id": confirmation.get("id"),
            "confirmed_option": confirmed_option,
            "confirmed_by": actor,
            "visit_scheduled_at": confirmed_at,
            "stage": ticket.get("stage"),
        }

    result = db.run_in_transaction(_tx)
    ticket_id = str(result.get("ticket_id"))
    set_correlation_id(ticket_id)
    logger.info(
        "ORQ_CONFIRM_VISIT correlation_id=%s proposal_id=%s confirmation_id=%s option=%s by=%s",
        ticket_id,
        clean_proposal_id,
        result.get("confirmation_id"),
        confirmed_option,
        actor,
    )
    return _jsonable(result)


def reschedule_visit(
    *,
    ticket_id: str,
    advisor_name: str | None,
    option1: datetime | None,
    option2: datetime | None,
    option3: datetime | None,
    message_out: str,
) -> dict[str, Any]:
    clean_ticket_id = str(ticket_id or "").strip()
    if not clean_ticket_id:
        raise ValueError("ticket_id is required")

    clean_message_out = str(message_out or "").strip()
    if not clean_message_out:
        raise ValueError("message_out is required")

    def _tx(conn: Any) -> dict[str, Any]:
        context = repo.get_ticket_context(conn, clean_ticket_id)
        if context is None:
            raise KeyError("ticket not found")

        advisor = repo.find_advisor_by_name(conn, advisor_name)
        if advisor_name and advisor is None:
            raise ValueError("advisor_name not found")

        superseded_count = repo.supersede_active_proposals(conn, clean_ticket_id)

        proposal = repo.create_visit_proposal(
            conn,
            ticket_id=clean_ticket_id,
            conversation_id=str(context["conversation_id"]),
            lead_id=str(context["lead_id"]),
            advisor_id=str(advisor["id"]) if advisor else None,
            mode="reschedule",
            option1=option1,
            option2=option2,
            option3=option3,
            message_out=clean_message_out,
        )

        message = repo.insert_message(
            conn,
            conversation_id=str(context["conversation_id"]),
            lead_id=str(context["lead_id"]),
            direction="out",
            actor="advisor",
            text=clean_message_out,
            provider_meta={
                "mode": "reschedule",
                "proposal_id": str(proposal.get("id")),
                "advisor_name": advisor.get("full_name") if advisor else advisor_name,
            },
        )

        ticket = repo.update_ticket_activity(
            conn,
            clean_ticket_id,
            stage=STAGE_WAITING_CONFIRMATION,
            assigned_advisor_id=str(advisor["id"]) if advisor else None,
            last_message_snippet=_normalize_snippet(clean_message_out),
        )

        repo.insert_event(
            conn,
            correlation_id=clean_ticket_id,
            domain=DOMAIN,
            name="visit.rescheduled",
            actor="advisor",
            payload={
                "ticket_id": clean_ticket_id,
                "proposal_id": proposal.get("id"),
                "mode": "reschedule",
                "superseded_count": superseded_count,
                "advisor_id": advisor.get("id") if advisor else None,
                "advisor_name": advisor.get("full_name") if advisor else advisor_name,
                "message_id": message.get("id"),
                "option1": proposal.get("option1"),
                "option2": proposal.get("option2"),
                "option3": proposal.get("option3"),
            },
        )

        return {
            "ticket_id": clean_ticket_id,
            "proposal_id": proposal.get("id"),
            "mode": "reschedule",
            "stage": ticket.get("stage"),
            "superseded_count": superseded_count,
            "advisor": advisor,
            "message_id": message.get("id"),
            "option1": proposal.get("option1"),
            "option2": proposal.get("option2"),
            "option3": proposal.get("option3"),
        }

    result = db.run_in_transaction(_tx)
    set_correlation_id(clean_ticket_id)
    logger.info(
        "ORQ_RESCHEDULE_VISIT correlation_id=%s proposal_id=%s superseded_count=%s",
        clean_ticket_id,
        result.get("proposal_id"),
        result.get("superseded_count"),
    )
    return _jsonable(result)


def supervisor_send(*, ticket_id: str, target: str, text: str) -> dict[str, Any]:
    clean_ticket_id = str(ticket_id or "").strip()
    if not clean_ticket_id:
        raise ValueError("ticket_id is required")

    clean_target = str(target or "").strip().lower()
    if clean_target not in {"client", "advisor"}:
        raise ValueError("target must be client or advisor")

    clean_text = str(text or "").strip()
    if not clean_text:
        raise ValueError("text is required")

    def _tx(conn: Any) -> dict[str, Any]:
        context = repo.get_ticket_context(conn, clean_ticket_id)
        if context is None:
            raise KeyError("ticket not found")

        message = repo.insert_message(
            conn,
            conversation_id=str(context["conversation_id"]),
            lead_id=str(context["lead_id"]),
            direction="out",
            actor="supervisor",
            text=clean_text,
            provider_meta={"target": clean_target},
        )

        ticket = repo.update_ticket_activity(
            conn,
            clean_ticket_id,
            last_message_snippet=_normalize_snippet(clean_text),
        )

        repo.insert_event(
            conn,
            correlation_id=clean_ticket_id,
            domain=DOMAIN,
            name="supervisor.message.sent",
            actor="supervisor",
            payload={
                "ticket_id": clean_ticket_id,
                "target": clean_target,
                "message_id": message.get("id"),
                "text": clean_text,
            },
        )

        return {
            "ticket_id": clean_ticket_id,
            "target": clean_target,
            "message_id": message.get("id"),
            "stage": ticket.get("stage"),
            "last_activity_at": ticket.get("last_activity_at"),
        }

    result = db.run_in_transaction(_tx)
    set_correlation_id(clean_ticket_id)
    logger.info(
        "ORQ_SUPERVISOR_SEND correlation_id=%s target=%s message_id=%s",
        clean_ticket_id,
        clean_target,
        result.get("message_id"),
    )
    return _jsonable(result)


def ticket_detail(*, ticket_id: str) -> dict[str, Any]:
    clean_ticket_id = str(ticket_id or "").strip()
    if not clean_ticket_id:
        raise ValueError("ticket_id is required")

    def _tx(conn: Any) -> dict[str, Any]:
        context = repo.get_ticket_context(conn, clean_ticket_id)
        if context is None:
            raise KeyError("ticket not found")

        ticket = repo.get_ticket_detail(conn, clean_ticket_id)
        messages = repo.list_conversation_messages(conn, str(context["conversation_id"]), limit=200)
        active_proposal = repo.get_active_visit_proposal_for_ticket(conn, clean_ticket_id)

        return {
            "ticket": ticket or context,
            "context": context,
            "active_proposal": active_proposal,
            "messages": messages,
        }

    result = db.run_in_transaction(_tx)
    set_correlation_id(clean_ticket_id)
    logger.info(
        "ORQ_TICKET_DETAIL correlation_id=%s messages=%s has_active_proposal=%s",
        clean_ticket_id,
        len(result.get("messages") or []),
        bool(result.get("active_proposal")),
    )
    return _jsonable(result)
