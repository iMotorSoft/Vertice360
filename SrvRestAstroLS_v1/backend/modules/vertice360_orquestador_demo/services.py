from __future__ import annotations

import logging
import re
import unicodedata
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from backend import globalVar
from backend.modules.messaging.providers.gupshup.whatsapp.service import (
    GupshupWhatsAppSendError,
    send_text_message as gupshup_send_text,
)
from backend.modules.vertice360_orquestador_demo import db, repo
from backend.telemetry.context import set_correlation_id

logger = logging.getLogger(__name__)

DOMAIN = "vertice360_orquestador_demo"
STAGE_PENDING_VISIT = "Pendiente de visita"
STAGE_WAITING_CONFIRMATION = "Esperando confirmación"
STAGE_VISIT_CONFIRMED = "Visita confirmada"
REQUIREMENTS_FIELDS = ("ambientes", "presupuesto", "moneda")

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


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    without_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return " ".join(without_accents.lower().split())


def parse_ambientes(text: str) -> int | None:
    clean = _normalize_text(text)
    if not clean:
        return None

    if re.search(r"\bmono(?:ambiente)?s?\b", clean):
        return 1

    digit_match = re.search(r"\b([1-4])\s*amb(?:\.|ientes?)?\b", clean)
    if digit_match:
        return int(digit_match.group(1))

    word_map = {"un": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4}
    word_match = re.search(r"\b(un|uno|dos|tres|cuatro)\s+amb(?:\.|ientes?)?\b", clean)
    if word_match:
        return word_map.get(word_match.group(1))
    return None


def _parse_compact_number(token: str) -> Decimal | None:
    compact = str(token or "").strip().replace(" ", "")
    if not compact:
        return None

    if "." in compact and "," in compact:
        if compact.rfind(",") > compact.rfind("."):
            normalized = compact.replace(".", "").replace(",", ".")
        else:
            normalized = compact.replace(",", "")
    elif re.match(r"^\d{1,3}(?:[.,]\d{3})+$", compact):
        normalized = compact.replace(".", "").replace(",", "")
    else:
        normalized = compact.replace(",", ".")

    try:
        return Decimal(normalized)
    except Exception:  # noqa: BLE001
        return None


def parse_budget_currency(text: str) -> dict[str, Any]:
    clean = _normalize_text(text)
    if not clean:
        return {"presupuesto": None, "moneda": None}

    currency = None
    if re.search(r"(?:\bu\s*\$\s*s?\b|\busd\b|\bdolares?\b|\bdolar(?:es)?\b)", clean):
        currency = "USD"
    elif re.search(r"(?:\bars\b|\bpeso(?:s)?\b|\bargentin(?:os|as)\b)", clean):
        currency = "ARS"

    amount_candidates: list[tuple[int, str]] = []
    for match in re.finditer(
        r"(?<!\w)(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)(?:\s*(k|m|mil))?(?!\w)",
        clean,
    ):
        value = _parse_compact_number(match.group(1))
        if value is None:
            continue
        suffix = str(match.group(2) or "").lower()
        multiplier = 1
        if suffix in {"k", "mil"}:
            multiplier = 1000
        elif suffix == "m":
            multiplier = 1_000_000
        computed = int(value * multiplier)
        amount_candidates.append((computed, suffix))

    if not amount_candidates:
        return {"presupuesto": None, "moneda": currency}

    presupuesto, suffix = max(amount_candidates, key=lambda item: item[0])
    if presupuesto < 1000 and not suffix and currency is None:
        return {"presupuesto": None, "moneda": currency}
    return {"presupuesto": presupuesto, "moneda": currency}


def _extract_ticket_requirements(detail: dict[str, Any] | None) -> dict[str, Any]:
    base_summary = detail.get("summary_jsonb") if isinstance(detail, dict) else {}
    requirements = {}
    if isinstance(base_summary, dict):
        raw = base_summary.get("requirements")
        if isinstance(raw, dict):
            requirements = dict(raw)

    if detail:
        if detail.get("req_ambientes") is not None:
            requirements["ambientes"] = int(detail.get("req_ambientes"))
        if detail.get("req_presupuesto") is not None:
            requirements["presupuesto"] = int(detail.get("req_presupuesto"))
        if detail.get("req_moneda"):
            requirements["moneda"] = str(detail.get("req_moneda")).upper()

    normalized: dict[str, Any] = {}
    if requirements.get("ambientes") is not None:
        normalized["ambientes"] = int(requirements["ambientes"])
    if requirements.get("presupuesto") is not None:
        normalized["presupuesto"] = int(requirements["presupuesto"])
    if requirements.get("moneda"):
        normalized["moneda"] = str(requirements["moneda"]).upper()
    return normalized


def _missing_requirements(requirements: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in REQUIREMENTS_FIELDS:
        value = requirements.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
    return missing


def _requirements_patch_from_text(text: str) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    ambientes = parse_ambientes(text)
    if ambientes is not None:
        patch["ambientes"] = ambientes

    budget_data = parse_budget_currency(text)
    if budget_data.get("presupuesto") is not None:
        patch["presupuesto"] = int(budget_data["presupuesto"])
    if budget_data.get("moneda"):
        patch["moneda"] = str(budget_data["moneda"]).upper()
    return patch


def _format_amount(amount: Any) -> str:
    try:
        value = int(amount)
    except Exception:  # noqa: BLE001
        return str(amount or "-")
    return f"{value:,}".replace(",", ".")


def _build_vera_project_requirements_reply(project_name: str, missing_fields: list[str]) -> str:
    clean_project = str(project_name or "").strip() or "este proyecto"
    missing = set(missing_fields or [])

    if missing == {"ambientes"}:
        ask = "Contame cuántos ambientes buscás."
    elif missing == {"presupuesto"}:
        ask = "Contame tu presupuesto aproximado."
    elif missing == {"moneda"}:
        ask = "Decime si tu presupuesto es en USD o ARS."
    elif missing == {"presupuesto", "moneda"}:
        ask = "Contame tu presupuesto aproximado y la moneda (USD o ARS)."
    elif missing:
        ask = "Contame cuántos ambientes buscás y tu presupuesto aproximado (USD o ARS)."
    else:
        ask = "Contame cuántos ambientes buscás y tu presupuesto aproximado (USD o ARS)."

    return (
        f"Hola 👋 Soy Vera. Gracias por tu consulta por {clean_project}.\n"
        f"{ask}"
    )


def _build_vera_project_summary_reply(project_name: str, requirements: dict[str, Any]) -> str:
    ambientes = int(requirements.get("ambientes") or 0)
    presupuesto = _format_amount(requirements.get("presupuesto"))
    moneda = str(requirements.get("moneda") or "").upper() or "-"
    return (
        "Perfecto 🙌. Entonces:\n"
        f"• Proyecto: {project_name}\n"
        f"• Unidad: {ambientes} ambientes\n"
        f"• Presupuesto: {presupuesto} {moneda}\n"
        "Ya lo dejé listo para coordinar visita. Un asesor te va a proponer horarios por este chat en breve."
    )


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


def build_board_url(phone_e164: str) -> str:
    base = str(globalVar.V360_DEMO_BOARD_BASE_URL or "").strip()
    if not base:
        base = "http://localhost:3062/demo/vertice360-orquestador/"
    digits = "".join(ch for ch in str(phone_e164 or "") if ch.isdigit())
    if "?" in base:
        separator = "&" if not base.endswith(("?", "&")) else ""
    else:
        separator = "?" if not base.endswith("?") else ""
    return f"{base}{separator}cliente={digits}"


def build_orquestador_board_url(phone_e164: str) -> str:
    # Backward-compatible alias used by existing tests/docs.
    return build_board_url(phone_e164)


def _safe_board_url_for_log(board_url: str) -> str:
    if str(globalVar.RUN_ENV).lower() == "dev":
        return board_url
    if not board_url:
        return "-"
    return board_url.split("?")[0] + "?cliente=***"


def _build_vera_onboarding_reply(board_url: str) -> str:
    return (
        "Hola 👋 Soy Vera. Gracias por querer probar nuestra solución.\n"
        "Te dejo el tablero para ver en vivo todo el flujo de mensajes y acciones:\n"
        f"{board_url}\n\n"
        "Tenés dos opciones para seguir:\n\n"
        "1) Desde el tablero: elegí un proyecto y tocá \"Enviar WhatsApp\" para simular una consulta "
        "que llega desde una publicidad.\n"
        "2) Desde este chat: empezá a conversar y te voy a preguntar qué proyecto querés "
        "(Bulnes 966, GDR 3760 o Manzanares 3277) para avanzar.\n\n"
        "Te acompaño en la forma que prefieras 🙂.\n"
        "Si querés, empezá por el tablero… o simplemente escribime por acá y seguimos."
    )


def _build_vera_project_reply(project_name: str) -> str:
    return (
        f"Hola 👋 Soy Vera. Gracias por tu consulta por {project_name}.\n"
        "Decime ambientes (mono/2/3) y un presupuesto aproximado, y avanzamos con opciones y visita."
    )


def _build_vera_project_fallback() -> str:
    return "¿Sobre qué proyecto querés consultar: Bulnes 966, GDR 3760 o Manzanares 3277?"


async def _send_vera_whatsapp_reply(phone_e164: str, text: str) -> dict[str, Any]:
    if not globalVar.gupshup_whatsapp_enabled():
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": False,
            "error": {
                "type": "GupshupConfigError",
                "message": "Gupshup WhatsApp is not configured",
            },
        }

    try:
        ack = await gupshup_send_text(phone_e164, text)
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": True,
            "provider_message_id": str(ack.provider_message_id or ""),
            "raw": ack.raw,
        }
    except GupshupWhatsAppSendError as exc:
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": False,
            "error": {
                "type": exc.__class__.__name__,
                "message": str(exc),
                "upstream_status": exc.upstream_status,
                "upstream_body": exc.upstream_body,
                "url": exc.url,
            },
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "provider": "gupshup_whatsapp",
            "vera_send_ok": False,
            "error": {
                "type": exc.__class__.__name__,
                "message": str(exc),
            },
        }


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
                    "requirements": {
                        "ambientes": row.get("req_ambientes"),
                        "presupuesto": row.get("req_presupuesto"),
                        "moneda": row.get("req_moneda"),
                    },
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


def admin_reset_phone(*, phone: str) -> dict[str, Any]:
    normalized_phone = _normalize_phone_e164(phone)

    def _tx(conn: Any) -> dict[str, Any]:
        return {
            "ok": True,
            "phone": normalized_phone,
            "deleted": repo.reset_by_phone(conn, normalized_phone),
        }

    result = db.run_in_transaction(_tx)
    logger.warning(
        "ORQ_ADMIN_RESET_PHONE phone=%s deleted=%s",
        normalized_phone,
        result.get("deleted"),
    )
    return _jsonable(result)


def ingest_message(
    *,
    phone: str,
    text: str,
    project_code: str | None = None,
    source: str | None = None,
    provider_message_id: str | None = None,
    provider_meta: dict[str, Any] | None = None,
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

        inbound_provider_meta = {"source": source_value}
        if isinstance(provider_meta, dict):
            inbound_provider_meta.update(
                {str(k): v for k, v in provider_meta.items() if v is not None}
            )

        message = repo.insert_message(
            conn,
            conversation_id=conversation_id,
            lead_id=lead_id,
            direction="in",
            actor="client",
            text=clean_text,
            provider_message_id=str(provider_message_id or "").strip() or None,
            provider_meta=inbound_provider_meta,
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
        requirements_patch: dict[str, Any] = {}
        requirements: dict[str, Any] = {}
        requirements_missing: list[str] = []

        if detail and detail.get("project_code"):
            requirements = _extract_ticket_requirements(detail)
            requirements_patch = _requirements_patch_from_text(clean_text)

            if requirements_patch:
                repo.update_ticket_requirements(conn, ticket_id, requirements_patch)
                detail = repo.get_ticket_detail(conn, ticket_id) or detail
                requirements = _extract_ticket_requirements(detail)
                repo.insert_event(
                    conn,
                    correlation_id=ticket_id,
                    domain=DOMAIN,
                    name="orq.requirements.captured",
                    actor="system",
                    payload={
                        "ticket_id": ticket_id,
                        "project_code": detail.get("project_code"),
                        "captured": requirements_patch,
                        "requirements": requirements,
                    },
                )

            requirements_missing = _missing_requirements(requirements)
            requirements_complete = len(requirements_missing) == 0
            current_stage = str(detail.get("stage") or ticket.get("stage") or "")
            if (
                requirements_complete
                and current_stage
                not in {STAGE_PENDING_VISIT, STAGE_WAITING_CONFIRMATION, STAGE_VISIT_CONFIRMED}
            ):
                previous_stage = current_stage
                repo.update_ticket_activity(conn, ticket_id, stage=STAGE_PENDING_VISIT)
                repo.insert_event(
                    conn,
                    correlation_id=ticket_id,
                    domain=DOMAIN,
                    name="orq.stage.updated",
                    actor="system",
                    payload={
                        "ticket_id": ticket_id,
                        "from_stage": previous_stage,
                        "to_stage": STAGE_PENDING_VISIT,
                        "reason": "requirements_complete",
                    },
                )
                detail = repo.get_ticket_detail(conn, ticket_id) or detail
        else:
            requirements_complete = False

        requirements = _extract_ticket_requirements(detail)
        requirements_missing = _missing_requirements(requirements)
        requirements_complete = bool(requirements and not requirements_missing)
        return {
            "ticket_id": ticket_id,
            "conversation_id": conversation_id,
            "lead_id": lead_id,
            "project_id": detail.get("project_id") if detail else ticket.get("project_id"),
            "project_code": detail.get("project_code") if detail else None,
            "project_name": detail.get("project_name") if detail else None,
            "stage": detail.get("stage") if detail else ticket.get("stage"),
            "requirements": requirements,
            "requirements_missing": requirements_missing,
            "requirements_complete": requirements_complete,
            "requirements_patch": requirements_patch,
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
        "ORQ_INGEST_MESSAGE correlation_id=%s lead_created=%s conversation_created=%s ticket_created=%s phone=%s project_code=%s stage=%s requirements_complete=%s",
        ticket_id,
        result.get("lead_created"),
        result.get("conversation_created"),
        result.get("ticket_created"),
        normalized_phone,
        result.get("project_code") or "-",
        result.get("stage") or "-",
        bool(result.get("requirements_complete")),
    )
    return _jsonable(result)


async def ingest_from_provider(
    *,
    user_phone: str,
    text: str,
    provider: str = "gupshup_whatsapp",
    provider_message_id: str | None = None,
    provider_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_phone = _normalize_phone_e164(user_phone)
    clean_text = str(text or "").strip()
    if not clean_text:
        raise ValueError("text is required")

    provider_name = str(provider or "gupshup_whatsapp").strip().lower() or "gupshup_whatsapp"
    safe_provider_message_id = str(provider_message_id or "").strip() or None

    inbound_meta = dict(provider_meta or {})
    inbound_meta.setdefault("provider", provider_name)
    inbound_meta.setdefault("channel", "whatsapp")

    ingest_result = ingest_message(
        phone=normalized_phone,
        text=clean_text,
        source="whatsapp",
        provider_message_id=safe_provider_message_id,
        provider_meta=inbound_meta,
    )

    is_first_contact = bool(
        ingest_result.get("lead_created")
        or ingest_result.get("conversation_created")
        or ingest_result.get("ticket_created")
    )
    project_name = str(
        ingest_result.get("project_name") or ingest_result.get("project_code") or ""
    ).strip()
    requirements = ingest_result.get("requirements") if isinstance(ingest_result.get("requirements"), dict) else {}
    requirements_missing = (
        ingest_result.get("requirements_missing")
        if isinstance(ingest_result.get("requirements_missing"), list)
        else []
    )
    requirements_complete = bool(ingest_result.get("requirements_complete"))
    board_url = ""

    if is_first_contact:
        variant = "onboarding"
        board_url = build_board_url(normalized_phone)
        reply_text = _build_vera_onboarding_reply(board_url)
    elif project_name:
        variant = "project"
        if requirements_complete:
            reply_text = _build_vera_project_summary_reply(project_name, requirements)
        else:
            reply_text = _build_vera_project_requirements_reply(project_name, requirements_missing)
    else:
        variant = "choose_project"
        reply_text = _build_vera_project_fallback()

    send_result = await _send_vera_whatsapp_reply(normalized_phone, reply_text)
    vera_send_ok = bool(send_result.get("vera_send_ok"))
    ticket_id = str(ingest_result.get("ticket_id") or "")

    logger.info(
        "VERA_REPLY correlation_id=%s phone=%s provider=%s variant=%s send_ok=%s board_url=%s",
        ticket_id or "-",
        normalized_phone,
        provider_name,
        variant,
        vera_send_ok,
        _safe_board_url_for_log(board_url),
    )

    payload = {
        **ingest_result,
        "ok": True,
        "routed": "orquestador",
        "vera_send_ok": vera_send_ok,
        "vera_reply_variant": variant,
        "vera_reply_text": reply_text,
    }
    if not vera_send_ok:
        payload["error"] = send_result.get("error")
    return _jsonable(payload)


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
