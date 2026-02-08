from __future__ import annotations

import datetime as dt
import re
import unicodedata
from typing import Any

import logging
from backend import globalVar
from backend.modules.messaging.providers.meta.whatsapp import MetaWhatsAppSendError, send_text_message as meta_send_text
from backend.modules.messaging.providers.gupshup.whatsapp.service import send_text_message as gupshup_send_text, GupshupWhatsAppSendError
from backend.modules.vertice360_ai_workflow_demo import langgraph_flow as ai_flow
from backend.modules.vertice360_ai_workflow_demo import services as ai_workflow_services
from backend.modules.vertice360_ai_workflow_demo import llm_state_reducer
from backend.modules.vertice360_workflow_demo import events, store, commercial_memory

ASSIGNMENT_SLA_MS = 30 * 60 * 1000
DOC_VALIDATION_SLA_MS = 24 * 60 * 60 * 1000

logger = logging.getLogger(__name__)


def _epoch_ms() -> int:
    return int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in normalized if not unicodedata.combining(char))
    return stripped.lower()


def _extract_commercial_slots(text: str) -> dict[str, Any]:
    slots: dict[str, Any] = {}

    zona = commercial_memory.parse_zona(text)
    if zona:
        slots["zona"] = zona

    tipologia = commercial_memory.parse_tipologia(text)
    if tipologia:
        slots["tipologia"] = tipologia

    presupuesto, moneda = commercial_memory.parse_budget_currency(text)
    if presupuesto is not None:
        slots["presupuesto"] = presupuesto
    if moneda:
        slots["moneda"] = moneda

    fecha_mudanza = commercial_memory.parse_fecha_mudanza(text)
    if fecha_mudanza:
        slots["fecha_mudanza"] = fecha_mudanza

    return slots


def _build_contextual_input(commercial: dict[str, Any], message: str) -> str:
    if not isinstance(commercial, dict):
        return message
    parts = []
    # Use the priority list from the memory module for consistent ordering
    for key in commercial_memory.COMMERCIAL_SLOT_PRIORITY:
        value = commercial.get(key)
        if value is None or value == "" or value == "UNKNOWN":
            continue
        parts.append(f"{key}={value}")
    
    safe_message = str(message or "")
    if not parts:
        return safe_message
        
    known = ", ".join(parts)
    return f"Contexto del ticket: {known}. Mensaje: {safe_message}"


def _format_ai_slot_value(value: Any) -> str:
    if value is None or value == "" or value == "UNKNOWN":
        return "?"
    return str(value)


def _build_property_search_context(slots: dict[str, Any], message: str) -> str:
    safe_message = str(message or "")
    slot_parts = []
    for key in commercial_memory.COMMERCIAL_SLOT_PRIORITY:
        slot_parts.append(f"{key}={_format_ai_slot_value(slots.get(key))}")
    slots_text = ", ".join(slot_parts)
    return f"Contexto: intent=property_search; slots actuales: {slots_text}. Mensaje: {safe_message}"


def _build_contextual_input_from_slot_memory(slot_memory: dict[str, Any], message: str, intent: str | None) -> str:
    slot_parts = []
    for key in ("zona", "tipologia", "presupuesto_amount", "moneda", "fecha_mudanza"):
        slot_parts.append(f"{key}={_format_ai_slot_value(slot_memory.get(key))}")
    slot_parts.append(f"budget_confirmed={bool(slot_memory.get('budget_confirmed'))}")
    slot_parts.append(f"budget_ambiguous={bool(slot_memory.get('budget_ambiguous'))}")
    last_question = _format_ai_slot_value(slot_memory.get("last_question"))
    last_key = _format_ai_slot_value(
        slot_memory.get("last_question_key") or slot_memory.get("last_asked_slot")
    )
    pending = slot_memory.get("pending_ambiguity")
    if isinstance(pending, dict) and pending:
        pending_text = f"{pending.get('key') or '?'}:{pending.get('question') or '?'}"
    else:
        pending_text = "-"
    intent_text = intent or "general"
    slots_text = ", ".join(slot_parts)
    safe_message = str(message or "")
    return (
        f"Contexto comercial: intent={intent_text}; {slots_text}; "
        f"last_question={last_question}; last_question_key={last_key}; "
        f"pending_ambiguity={pending_text}. Mensaje usuario: {safe_message}"
    )


def _ensure_ai_context(ticket: dict[str, Any]) -> dict[str, Any]:
    ai_context = ticket.get("ai_context")
    if not isinstance(ai_context, dict):
        ai_context = {"primaryIntentLocked": None, "commercialSlots": {}}
        ticket["ai_context"] = ai_context
    if "primaryIntentLocked" not in ai_context:
        ai_context["primaryIntentLocked"] = None
    slots = ai_context.get("commercialSlots")
    if not isinstance(slots, dict):
        slots = {}
        ai_context["commercialSlots"] = slots
    for key in commercial_memory.COMMERCIAL_SLOT_PRIORITY:
        slots.setdefault(key, None)
    return ai_context


def _sync_ai_commercial_slots(ai_context: dict[str, Any], commercial: dict[str, Any]) -> None:
    slots = ai_context.get("commercialSlots")
    if not isinstance(slots, dict):
        slots = {}
        ai_context["commercialSlots"] = slots
    for key in commercial_memory.COMMERCIAL_SLOT_PRIORITY:
        slots[key] = commercial.get(key)


def _ensure_slot_memory(ticket: dict[str, Any]) -> dict[str, Any]:
    slot_memory = ticket.get("slot_memory")
    if not isinstance(slot_memory, dict):
        slot_memory = {}
        ticket["slot_memory"] = slot_memory
    slot_memory.setdefault("zona", None)
    slot_memory.setdefault("tipologia", None)
    slot_memory.setdefault("presupuesto_amount", None)
    slot_memory.setdefault("presupuesto_raw", None)
    slot_memory.setdefault("moneda", None)
    slot_memory.setdefault("fecha_mudanza", None)
    slot_memory.setdefault("budget_ambiguous", False)
    slot_memory.setdefault("budget_confirmed", False)
    slot_memory.setdefault("confirmed_budget", False)
    slot_memory.setdefault("confirmed_currency", False)
    slot_memory.setdefault("last_question", None)
    slot_memory.setdefault("last_question_key", None)
    slot_memory.setdefault("last_asked_slot", None)
    slot_memory.setdefault("asked_count", 0)
    slot_memory.setdefault("pending_ambiguity", None)
    return slot_memory


def _normalize_question(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(str(text).split()).strip()


def _extract_budget_raw(text: str) -> str | None:
    if not text:
        return None
    match = commercial_memory.BUDGET_RE.search(str(text))
    if not match:
        return None
    prefix = match.group("prefix") or ""
    amount = match.group("amount") or ""
    magnitude = match.group("magnitude") or ""
    suffix = match.group("suffix") or ""
    parts = []
    if prefix:
        parts.append(prefix)
    if amount:
        parts.append(amount)
    if magnitude:
        parts.append(magnitude)
    if suffix:
        parts.append(suffix)
    raw = " ".join(part.strip() for part in parts if part)
    return raw or None


def _budget_has_magnitude(text: str) -> bool:
    if not text:
        return False
    match = commercial_memory.BUDGET_RE.search(str(text))
    if not match:
        return False
    return bool(match.group("magnitude"))


def _detect_budget_ambiguity(text: str, amount: int | None, currency: str | None) -> bool:
    if amount is None or currency is None:
        return False
    if amount >= 5000:
        return False
    if _budget_has_magnitude(text):
        return False
    return True


def _format_amount(value: Any) -> str:
    if value is None:
        return "?"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _build_budget_ambiguity_question(currency: str | None, amount: int | None) -> str | None:
    if not currency or amount is None:
        return None
    amount_text = _format_amount(amount)
    return f"¿Confirmás si es {currency} {amount_text} o {currency} {amount_text} mil aprox.?"


def _merge_slot_memory(
    slot_memory: dict[str, Any],
    updates: dict[str, Any] | None,
    confirmed: dict[str, Any] | None = None,
    *,
    allow_override: bool = True,
) -> None:
    if not updates:
        updates = {}
    for key, value in updates.items():
        if value is None or value == "":
            continue
        if key == "presupuesto_amount":
            if slot_memory.get("confirmed_budget") and slot_memory.get("presupuesto_amount") not in (
                None,
                "",
                "UNKNOWN",
            ):
                if slot_memory.get("presupuesto_amount") != value:
                    continue
        if key == "moneda":
            if slot_memory.get("confirmed_currency") and slot_memory.get("moneda") not in (
                None,
                "",
                "UNKNOWN",
            ):
                if slot_memory.get("moneda") != value:
                    continue
        current = slot_memory.get(key)
        if not allow_override and current not in (None, "", "UNKNOWN"):
            if current != value:
                continue
        slot_memory[key] = value

    if confirmed:
        if confirmed.get("budget") and slot_memory.get("presupuesto_amount") not in (None, "", "UNKNOWN"):
            slot_memory["confirmed_budget"] = True
        if confirmed.get("currency") and slot_memory.get("moneda") not in (None, "", "UNKNOWN"):
            slot_memory["confirmed_currency"] = True
        if (
            slot_memory.get("confirmed_budget")
            and slot_memory.get("confirmed_currency")
            and slot_memory.get("presupuesto_amount") not in (None, "", "UNKNOWN")
            and slot_memory.get("moneda") not in (None, "", "UNKNOWN")
        ):
            slot_memory["budget_confirmed"] = True


def _missing_slots_from_memory(slot_memory: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not slot_memory.get("zona"):
        missing.append("zona")
    if not slot_memory.get("tipologia"):
        missing.append("tipologia")

    budget_confirmed = bool(
        slot_memory.get("budget_confirmed")
        or (
            slot_memory.get("confirmed_budget")
            and slot_memory.get("confirmed_currency")
        )
    )
    budget_ambiguous = bool(slot_memory.get("budget_ambiguous"))
    amount_missing = slot_memory.get("presupuesto_amount") in (None, "", "UNKNOWN")
    currency_missing = slot_memory.get("moneda") in (None, "", "UNKNOWN")
    if budget_ambiguous:
        missing.append("presupuesto")
    elif not budget_confirmed:
        if amount_missing:
            missing.append("presupuesto")
        if currency_missing:
            missing.append("moneda")
    else:
        if amount_missing:
            missing.append("presupuesto")
        if currency_missing:
            missing.append("moneda")
    if not slot_memory.get("fecha_mudanza"):
        missing.append("fecha_mudanza")
    return missing


def _question_for_slot(slot: str, slot_memory: dict[str, Any], missing: set[str]) -> str | None:
    if slot == "zona":
        if "tipologia" in missing:
            return "¿Por qué zona buscás y qué tipología (ambientes)?"
        return "¿En qué zona o barrio estás buscando?"
    if slot == "tipologia":
        return "¿Qué tipología buscás? (Ej: 2 ambientes, monoambiente)"
    if slot in ("presupuesto", "moneda"):
        amount = slot_memory.get("presupuesto_amount")
        currency = slot_memory.get("moneda")
        if amount not in (None, "", "UNKNOWN") and not currency:
            return "¿En qué moneda está ese presupuesto?"
        if currency and amount in (None, "", "UNKNOWN"):
            return "¿Cuál es tu presupuesto aproximado?"
        return "¿Cuál es tu presupuesto aproximado y moneda?"
    if slot == "fecha_mudanza":
        return "¿Para cuándo necesitás mudarte?"
    return None


def _pick_next_question(
    slot_memory: dict[str, Any],
    missing_slots: list[str],
    ambiguity_question: str | None,
) -> tuple[str | None, str | None]:
    if ambiguity_question:
        return ambiguity_question, "presupuesto"

    missing_set = set(missing_slots)
    primary_slot = None
    if "zona" in missing_set:
        primary_slot = "zona"
    elif "tipologia" in missing_set:
        primary_slot = "tipologia"
    elif "presupuesto" in missing_set or "moneda" in missing_set:
        primary_slot = "presupuesto" if "presupuesto" in missing_set else "moneda"
    elif "fecha_mudanza" in missing_set:
        primary_slot = "fecha_mudanza"

    if not primary_slot:
        return None, None
    return _question_for_slot(primary_slot, slot_memory, missing_set), primary_slot


def _avoid_repeating_question(
    slot_memory: dict[str, Any],
    question: str | None,
    asked_slot: str | None,
    missing_slots: list[str],
) -> tuple[str | None, str | None]:
    if not question:
        return question, asked_slot
    last_question = _normalize_question(slot_memory.get("last_question"))
    current = _normalize_question(question)
    if not last_question or current != last_question:
        return question, asked_slot

    missing_set = set(missing_slots)
    priority = ["zona", "tipologia", "presupuesto", "moneda", "fecha_mudanza"]
    for slot in priority:
        if slot in missing_set and slot != asked_slot:
            alt = _question_for_slot(slot, slot_memory, missing_set)
            if alt:
                return alt, slot

    # Fallback to a variant for the same slot
    if asked_slot:
        alt = _question_for_slot(asked_slot, slot_memory, missing_set)
        if alt and _normalize_question(alt) != last_question:
            return alt, asked_slot
        if asked_slot == "zona":
            return "¿Qué barrio o zona preferís?", asked_slot
        if asked_slot == "tipologia":
            return "¿Cuántos ambientes buscás?", asked_slot
        if asked_slot == "presupuesto":
            return "¿Me confirmás el presupuesto y la moneda?", asked_slot
        if asked_slot == "moneda":
            return "¿Con qué moneda contamos para el presupuesto?", asked_slot
        if asked_slot == "fecha_mudanza":
            return "¿En qué fecha te gustaría mudarte?", asked_slot
    if current == last_question:
        return "¿Podés confirmarlo para avanzar?", asked_slot
    return question, asked_slot


def _build_summary_close(slot_memory: dict[str, Any]) -> str:
    zona = slot_memory.get("zona") or "?"
    tipologia = slot_memory.get("tipologia") or "?"
    presupuesto = _format_amount(
        slot_memory.get("presupuesto_amount")
        if slot_memory.get("presupuesto_amount") not in (None, "", "UNKNOWN")
        else slot_memory.get("presupuesto")
    )
    moneda = slot_memory.get("moneda") or "?"
    fecha = slot_memory.get("fecha_mudanza") or "?"
    return (
        f"Gracias. Tengo: zona {zona}, {tipologia}, presupuesto {presupuesto} {moneda}, "
        f"mudanza {fecha}. ¿Querés coordinar visita? Decime día y franja horaria."
    )


def _recent_message_texts(ticket: dict[str, Any], limit: int = 3) -> list[str]:
    messages = ticket.get("messages") or []
    texts = [msg.get("text") for msg in messages if msg.get("text")]
    return texts[-limit:]

def _is_property_search_text(text: str) -> bool:
    normalized = _normalize_text(text or "")
    tokens = (
        "busco depto",
        "busco departamento",
        "depto",
        "departamento",
        "monoambiente",
        "ambientes",
        "ambiente",
    )
    return any(token in normalized for token in tokens)


def _select_ai_reply(ai_output: dict[str, Any] | None) -> str | None:
    if not isinstance(ai_output, dict):
        return None
    question = ai_output.get("recommendedQuestion")
    if isinstance(question, str) and question.strip():
        return question.strip()
    response = ai_output.get("responseText")
    if isinstance(response, str) and response.strip():
        return response.strip()
    return None



def _pick_whatsapp_reply_text(ai_text: str | None, fallback_text: str) -> str:
    ai_value = ai_text if isinstance(ai_text, str) else ""
    ai_present = bool(ai_value and ai_value.strip())
    if not globalVar.VERTICE360_AI_WORKFLOW_REPLY or not ai_present:
        outbound_text = fallback_text
        chosen = "fallback"
    else:
        outbound_text = ai_value.strip()
        max_len = int(globalVar.VERTICE360_AI_WORKFLOW_REPLY_PREVIEW_MAX)
        if max_len > 0 and len(outbound_text) > max_len:
            outbound_text = outbound_text[: max_len - 1].rstrip() + "…"
        chosen = "ai"
    logger.debug(
        "[vertice360_workflow_demo] ai_reply=%s ai_present=%s chosen=%s len=%s preview=%s",
        globalVar.VERTICE360_AI_WORKFLOW_REPLY,
        ai_present,
        chosen,
        len(outbound_text),
        outbound_text[:80].replace("\n", " "),
    )
    return outbound_text


async def _run_ai_workflow_reply(
    text: str,
    message_id: str,
    ticket_id: str,
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not globalVar.VERTICE360_AI_WORKFLOW_REPLY:
        return None
    if not text or not str(text).strip():
        return None
    metadata = {"inboundMessageId": message_id, "ticketId": ticket_id}
    workflow_input: Any = text
    if isinstance(text, str):
        marker = "Mensaje usuario:"
        if marker in text:
            workflow_input = text.split(marker, 1)[1].strip()
    try:
        result = await ai_workflow_services.run_workflow(
            "vertice360-ai-workflow",
            workflow_input,
            metadata=metadata,
            context=context,
        )
    except Exception as exc:
        logger.warning(
            "[vertice360_workflow_demo] ai_workflow_failed=%s",
            type(exc).__name__,
        )
        return None
    if isinstance(result, dict):
        output = result.get("output")
        if isinstance(output, dict):
            return output
    return None


def classify_intent(text: str) -> str:
    normalized = _normalize_text(text or "")
    if any(token in normalized for token in ("document", "dni", "pasaporte", "comprobante", "adjunto", "foto")):
        return "DOCS"
    if any(token in normalized for token in ("reserv", "unidad", "2b", "febrero")):
        return "RESERVATION"
    if any(token in normalized for token in ("hola", "buenas", "buen dia", "buenas tardes")):
        return "GREETING"
    return "GENERAL"


def _normalize_inbound(inbound: dict[str, Any]) -> dict[str, Any]:
    now = _epoch_ms()
    text = inbound.get("text") or ""
    timestamp = inbound.get("timestamp")
    try:
        normalized_timestamp = int(timestamp) if timestamp is not None else now
    except (TypeError, ValueError):
        normalized_timestamp = now
    message_id = inbound.get("messageId") or inbound.get("message_id") or inbound.get("id")
    if not message_id:
        message_id = f"local-{normalized_timestamp}"

    media_count = inbound.get("mediaCount", 0)
    try:
        media_count = int(media_count)
    except (TypeError, ValueError):
        media_count = 0

    ai_response_text = inbound.get("aiResponseText") or inbound.get("ai_response_text")

    return {
        "provider": inbound.get("provider") or "meta_whatsapp",
        "channel": inbound.get("channel") or "whatsapp",
        "from": inbound.get("from") or "",
        "to": inbound.get("to") or "",
        "messageId": message_id,
        "text": text,
        "timestamp": normalized_timestamp,
        "ticketId": inbound.get("ticketId"),
        "mediaCount": media_count,
        "name": inbound.get("name"),
        "aiResponseText": ai_response_text,
    }


def _build_ticket_seed(normalized: dict[str, Any]) -> dict[str, Any]:
    subject = normalized["text"].strip() if normalized["text"] else "Inbound message"
    if len(subject) > 120:
        subject = f"{subject[:117]}..."
    return {
        "ticketId": normalized.get("ticketId"),
        "provider": normalized["provider"],
        "channel": normalized["channel"],
        "customer": {
            "from": normalized["from"],
            "to": normalized["to"],
            "provider": normalized["provider"],
            "channel": normalized["channel"],
            "name": normalized.get("name"),
        },
        "subject": subject,
    }


def _build_onboarding_template(name: str | None) -> str:
    greeting = f"¡Hola {name}!" if name else "¡Hola!"
    return (
        f"{greeting} Soy el asistente de Vértice360 👋\n"
        "Para iniciar tu reserva, te pido:\n"
        "1) Nombre y apellido\n"
        "2) DNI / Pasaporte\n"
        "3) Email\n"
        "4) Forma de pago (contado / cuotas)\n"
        "Si querés, también podés enviar la documentación por este chat."
    )


def _build_commercial_fallback() -> str:
    return "Soy el asistente de Vértice360 👋. ¿Por qué zona buscás y cuántos ambientes necesitás?"


def _has_unit_selection(text: str) -> bool:
    norm = _normalize_text(text or "")
    match = re.search(r"\b(unidad|dpto|depto|opcion|opción)\s+[\w\d]+", norm)
    return bool(match)


def _build_docs_reply() -> str:
    return (
        "Perfecto. Ya derivé tu caso a Administración para validar documentación ✅\n"
        "Podés enviar por aquí: foto DNI (frente/dorso) + comprobante.\n"
        "También, si preferís: docs@vertice360.com"
    )


def _extract_message_id(result: dict[str, Any]) -> str | None:
    messages = result.get("messages")
    if isinstance(messages, list) and messages:
        message_id = messages[0].get("id")
        if message_id:
            return message_id
    return result.get("message_id") or result.get("id")


def _is_send_error(result: dict[str, Any]) -> bool:
    return bool(result.get("error") or result.get("status") == "error")


async def _send_whatsapp_text(provider: str, to: str, text: str) -> dict[str, Any]:
    if provider == "gupshup_whatsapp":
        ack = await gupshup_send_text(to, text)
        return {"id": ack.provider_message_id, "raw": ack.raw}
    return await meta_send_text(to, text)


async def send_demo_reply(ticket_id: str, to: str, text: str) -> dict[str, Any]:
    if not ticket_id or not to or not text:
        raise ValueError("ticketId, to and text are required")

    ticket_seed = {
        "ticketId": ticket_id,
        "provider": "meta_whatsapp",
        "channel": "whatsapp",
        "customer": {
            "from": to,
            "to": "",
            "provider": "meta_whatsapp",
            "channel": "whatsapp",
        },
        "subject": "Manual reply",
    }
    ticket = await store.create_or_get_ticket_from_inbound(ticket_seed)
    provider = ticket.get("provider") or "meta_whatsapp"
    channel = ticket.get("channel") or "whatsapp"
    now_ms = _epoch_ms()

    try:
        result = await _send_whatsapp_text(provider, to, text)
    except (MetaWhatsAppSendError, GupshupWhatsAppSendError) as exc:
        status_code = getattr(exc, "upstream_status", None) or getattr(exc, "status_code", 500)
        err_body = getattr(exc, "upstream_body", None) or getattr(exc, "err", str(exc))
        error_payload = {"status_code": status_code, "err": err_body}
        await _emit_outbound_failed(ticket_id, provider, channel, to, text, error_payload)
        return {"ok": False, "error": error_payload, "ticketId": ticket_id}

    if _is_send_error(result):
        await store.add_timeline_event(
            ticket_id,
            "outbound.failed",
            {"provider": provider, "error": result},
        )
        return {"ok": False, "error": result, "ticketId": ticket_id}

    message_id = _extract_message_id(result)
    if not message_id:
        await store.add_timeline_event(
            ticket_id,
            "outbound.failed",
            {"provider": provider, "error": "missing_message_id", "response": result},
        )
        return {"ok": False, "error": "missing_message_id", "ticketId": ticket_id}

    await events.emit_messaging_outbound(
        ticket_id,
        provider=provider,
        channel=channel,
        messageId=message_id,
        to=to,
        text=text,
        sentAt=now_ms,
    )
    store.add_message(
        ticket_id,
        {
            "direction": "outbound",
            "provider": provider,
            "channel": channel,
            "messageId": message_id,
            "text": text,
            "at": now_ms,
            "mediaCount": 0,
        },
    )
    return {"ok": True, "ticketId": ticket_id, "messageId": message_id}

async def _emit_outbound_failed(
    ticket_id: str,
    provider: str,
    channel: str,
    to: str,
    text: str,
    error: dict[str, Any],
) -> None:
    payload = {
        "provider": provider,
        "channel": channel,
        "to": to,
        "text": text,
        "status": "failed",
        "error": error,
    }
    await events.emit_event(events.MESSAGING_OUTBOUND, ticket_id, dict(payload))
    await store.add_timeline_event(ticket_id, "outbound.failed", payload)



def _is_affirmative(text: str) -> bool:
    norm = _normalize_text(text)
    return any(w in norm for w in ("si", "ok", "correcto", "dale", "perfecto", "bueno", "confirmado", "esta bien"))


def _build_commercial_summary(slots: dict[str, Any]) -> str:
    lines = []
    lines.append(f"• Zona: {slots.get('zona') or '?'}")
    lines.append(f"• Tipología: {slots.get('tipologia') or '?'}")
    val_presup = slots.get('presupuesto')
    mon = slots.get('moneda') or ""
    if val_presup:
        lines.append(f"• Presupuesto: {mon} {val_presup}")
    else:
        lines.append(f"• Presupuesto: ?")
    lines.append(f"• Mudanza: {slots.get('fecha_mudanza') or '?'}")
    return "\n".join(lines)


async def process_inbound_message(inbound: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_inbound(inbound)
    actions: list[str] = []
    ai_response_text = normalized.get("aiResponseText")

    ticket_seed = _build_ticket_seed(normalized)
    ticket = await store.create_or_get_ticket_from_inbound(ticket_seed)
    ticket_id = ticket["ticketId"]
    actions.append("TICKET_READY")

    await events.emit_messaging_inbound(
        ticket_id,
        provider=normalized["provider"],
        channel=normalized["channel"],
        messageId=normalized["messageId"],
        from_=normalized["from"],
        to=normalized["to"],
        text=normalized["text"],
        mediaCount=normalized["mediaCount"],
        receivedAt=normalized["timestamp"],
    )
    store.add_message(
        ticket_id,
        {
            "direction": "inbound",
            "provider": normalized["provider"],
            "channel": normalized["channel"],
            "messageId": normalized["messageId"],
            "text": normalized["text"],
            "at": normalized["timestamp"],
            "mediaCount": normalized["mediaCount"],
        },
    )
    actions.append("INBOUND_EMITTED")

    # Manual extraction (ensures state update even if AI is disabled)
    extracted_this_turn = _extract_commercial_slots(normalized["text"])
    slot_memory = _ensure_slot_memory(ticket)

    # Avoid overriding a confirmed budget with a later ambiguous short number ("usd 120")
    if slot_memory.get("budget_confirmed"):
        maybe_amount = extracted_this_turn.get("presupuesto")
        maybe_currency = extracted_this_turn.get("moneda") or slot_memory.get("moneda")
        if _detect_budget_ambiguity(normalized["text"], maybe_amount, maybe_currency):
            extracted_this_turn.pop("presupuesto", None)
            extracted_this_turn.pop("moneda", None)

    if extracted_this_turn:
        store.update_ticket_commercial(ticket_id, extracted_this_turn)

    # --- AI WORKFLOW ORCHESTRATION ---
    ai_context = _ensure_ai_context(ticket)
    current_commercial = ticket.get("commercial") or {}

    # Sync slot memory from persisted commercial state.
    slot_memory["zona"] = current_commercial.get("zona")
    slot_memory["tipologia"] = current_commercial.get("tipologia")
    slot_memory["fecha_mudanza"] = current_commercial.get("fecha_mudanza")
    if current_commercial.get("presupuesto") not in (None, "", "UNKNOWN"):
        slot_memory["presupuesto_amount"] = current_commercial.get("presupuesto")
    if current_commercial.get("moneda") not in (None, "", "UNKNOWN"):
        slot_memory["moneda"] = current_commercial.get("moneda")
    budget_is_ambiguous_now = _detect_budget_ambiguity(
        normalized["text"],
        current_commercial.get("presupuesto"),
        current_commercial.get("moneda"),
    )
    if (
        slot_memory.get("presupuesto_amount") not in (None, "", "UNKNOWN")
        and slot_memory.get("moneda")
        and not budget_is_ambiguous_now
    ):
        slot_memory["confirmed_budget"] = True
        slot_memory["confirmed_currency"] = True
        slot_memory["budget_confirmed"] = True
        slot_memory["budget_ambiguous"] = False
        slot_memory["pending_ambiguity"] = None

    # Ambiguity handling for current message.
    amount_now = extracted_this_turn.get("presupuesto")
    currency_now = extracted_this_turn.get("moneda") or slot_memory.get("moneda")
    if _detect_budget_ambiguity(normalized["text"], amount_now, currency_now) and not slot_memory.get("budget_confirmed"):
        slot_memory["budget_ambiguous"] = True
        slot_memory["pending_ambiguity"] = {
            "key": "presupuesto",
            "question": _build_budget_ambiguity_question(currency_now, amount_now),
            "amount": amount_now,
            "currency": currency_now,
        }
    elif amount_now is not None and currency_now:
        slot_memory["budget_ambiguous"] = False
        slot_memory["pending_ambiguity"] = None

    pending_ambiguity = slot_memory.get("pending_ambiguity")
    if isinstance(pending_ambiguity, dict) and pending_ambiguity and _is_affirmative(normalized["text"]):
        pending_amount = pending_ambiguity.get("amount")
        pending_currency = pending_ambiguity.get("currency")
        resolved_amount = None
        if isinstance(pending_amount, (int, float)):
            resolved_amount = int(pending_amount) * 1000
        if resolved_amount is not None:
            slot_memory["presupuesto_amount"] = resolved_amount
            current_commercial["presupuesto"] = resolved_amount
            extracted_this_turn["presupuesto"] = resolved_amount
        if pending_currency:
            slot_memory["moneda"] = pending_currency
            current_commercial["moneda"] = pending_currency
            extracted_this_turn["moneda"] = pending_currency
        slot_memory["budget_ambiguous"] = False
        slot_memory["pending_ambiguity"] = None
        slot_memory["confirmed_budget"] = True
        slot_memory["confirmed_currency"] = True
        slot_memory["budget_confirmed"] = True
        store.update_ticket_commercial(
            ticket_id,
            {
                "presupuesto": current_commercial.get("presupuesto"),
                "moneda": current_commercial.get("moneda"),
            },
        )

    # Determine intent lock status based on history or signals.
    if ai_context.get("primaryIntentLocked") != "property_search":
        has_commercial_signal = any(
            value not in (None, "", "UNKNOWN")
            for value in current_commercial.values()
        )
        if has_commercial_signal or _is_property_search_text(normalized["text"]):
            ai_context["primaryIntentLocked"] = "property_search"

    property_search_locked = ai_context.get("primaryIntentLocked") == "property_search"
    contextual_input = _build_contextual_input_from_slot_memory(
        slot_memory,
        normalized["text"],
        "property_search" if property_search_locked else None,
    )

    # 2. Run AI workflow (for reasoning + run trace/indexing).
    ai_output = None
    if not ai_response_text:
        ai_output = await _run_ai_workflow_reply(
            contextual_input,
            normalized["messageId"],
            ticket_id,
            context={
                "intentHint": "property_search" if property_search_locked else None,
                "commercialSlots": current_commercial,
            },
        )

    # 3. Keep canonical commercial state from deterministic parser.
    # AI output is used for decisioning text, but slot values come from parser/memory.
    current_commercial = ticket.get("commercial") or current_commercial

    current_update_keys = set(extracted_this_turn.keys())

    # Emit telemetry
    commercial_missing_slots = commercial_memory.calculate_missing_slots(current_commercial)
    memory_payload = {
        "missingSlotsCount": len(commercial_missing_slots),
        "missing": commercial_missing_slots,
        "known": [k for k, v in current_commercial.items() if v and v != "UNKNOWN"]
    }
    if current_commercial.get("presupuesto"):
        memory_payload["budget"] = {
            "amount": current_commercial.get("presupuesto"),
            "currency": current_commercial.get("moneda")
        }
    await events.emit_event("commercial.memory", ticket_id, memory_payload)

    # 4. Determine Reply

    reply_text: str | None = None
    decision: str | None = None
    recommended_question: str | None = None
    is_ambiguous = False
    
    if ai_output:
        decision = ai_output.get("decision")
        is_ambiguous = ai_output.get("entities", {}).get("budget_ambiguous")
        if is_ambiguous:
            recommended_question = ai_output.get("recommendedQuestion")

    pending_ambiguity = slot_memory.get("pending_ambiguity")
    if isinstance(pending_ambiguity, dict) and pending_ambiguity.get("question"):
        decision = "ask_next_best_question"
        recommended_question = str(pending_ambiguity.get("question"))

    # If we are in property search, we enforce our commercial logic unless there's a specific ambiguity to resolve
    if (
        property_search_locked
        and not is_ambiguous
        and not (isinstance(pending_ambiguity, dict) and pending_ambiguity.get("question"))
    ):
        should_run_deterministic = False
        if not decision: 
            should_run_deterministic = True
        elif decision == "ask_next_best_question":
            should_run_deterministic = True
            
        if should_run_deterministic:
            last_key = ticket.get("slot_memory", {}).get("last_question_key")
            rec_q, rec_key = commercial_memory.get_next_question_with_anti_repetition(
                current_commercial, last_key, current_update_keys
            )
            still_missing = commercial_memory.calculate_missing_slots(current_commercial)
            if rec_key == "summary_close" and still_missing:
                rec_q, rec_key = commercial_memory.build_next_best_question(still_missing)
                if rec_key == last_key:
                    if rec_key == "fecha_mudanza":
                        rec_q = "¿En qué fecha te gustaría mudarte?"
                    elif rec_key == "presupuesto":
                        rec_q = "¿Me confirmás el presupuesto y la moneda?"

            if rec_key == "summary_close" and last_key == "summary" and _is_affirmative(normalized["text"]):
                decision = "confirm_visit_request"
                rec_q = "Perfecto. ¿Qué día y franja horaria te queda mejor para coordinar visita?"
                rec_key = "visit_window"
            
            if rec_key == "summary_close":
                decision = "summary_close"
                rec_q = _build_summary_close(current_commercial)
            elif rec_q:
                decision = "ask_next_best_question"
            
            if rec_q:
                recommended_question = rec_q
                
                # Update slot memory
                slot_mem = _ensure_slot_memory(ticket)
                if rec_key == "summary_close":
                    slot_mem["last_question"] = rec_q
                    slot_mem["last_question_key"] = "summary"
                else:
                    slot_mem["last_question"] = rec_q
                    slot_mem["last_question_key"] = rec_key
                    slot_mem["last_asked_slot"] = rec_key

    # Select final text
    ai_response_text = _select_ai_reply(ai_output)
    
    if decision == "ask_next_best_question" and recommended_question:
        reply_text = recommended_question
    elif decision == "summary_close" and recommended_question:
        reply_text = recommended_question
    elif decision == "confirm_visit_request" and recommended_question:
        reply_text = recommended_question
    elif decision == "handoff_to_sales" and ai_response_text:
        reply_text = ai_response_text
    else:
        # Fallback to AI response or Auto Reply
        fallback_text = _build_commercial_fallback()
        if ticket.get("status") in ("WAITING_DOCS", "RESERVA", "KYC"):
             fallback_text = _build_onboarding_template(normalized.get("name"))

        reply_text = _pick_whatsapp_reply_text(
            ai_response_text, fallback_text
        )
    
    # Anti-repeat guard
    last_outbound = None
    messages = ticket.get("messages") or []
    for m in reversed(messages):
        if m.get("direction") == "outbound":
            last_outbound = m.get("text")
            break
    
    if reply_text and last_outbound and _normalize_text(reply_text) == _normalize_text(last_outbound):
        logger.warning(f"[Anti-Repeat] Prevented duplicate outbound for ticket {ticket_id}")
        lowered = _normalize_text(reply_text)
        if "mud" in lowered or "cuando" in lowered or "cuándo" in lowered:
            reply_text = "¿Para qué fecha estimás la mudanza?"
        elif "presupuesto" in lowered:
            reply_text = "¿Me confirmás el presupuesto y la moneda?"
        else:
            reply_text = "Entendido. ¿Necesitás algo más?"

    # ... Dispatch Reply ...
    intent = classify_intent(normalized["text"]) # Keep intent classification for legacy/telemetry
    
    # Downgrade intent if locked to property_search and no explicit unit selected
    ai_context = ticket.get("ai_context") or {}
    if ai_context.get("primaryIntentLocked") == "property_search" and intent == "RESERVATION":
         if not _has_unit_selection(normalized["text"]):
             intent = "GENERAL"

    actions.append(f"INTENT_{intent}")

    if intent in ("GREETING", "GENERAL") or (decision and intent not in ("RESERVATION", "DOCS")):
        if (ticket.get("status") or "").lower() == "open":
            await store.set_status(ticket_id, "IN_PROGRESS")
            actions.append("STATUS_IN_PROGRESS")

        try:
            result = await _send_whatsapp_text(normalized["provider"], normalized["from"], reply_text)
        except (MetaWhatsAppSendError, GupshupWhatsAppSendError) as exc:
            actions.append("OUTBOUND_FAILED")
            status_code = getattr(exc, "upstream_status", None) or getattr(exc, "status_code", 500)
            err_body = getattr(exc, "upstream_body", None) or getattr(exc, "err", str(exc))
            error_payload = {"status_code": status_code, "err": err_body}
            await _emit_outbound_failed(
                ticket_id,
                normalized["provider"],
                normalized["channel"],
                normalized["from"],
                reply_text,
                error_payload,
            )

            return {
                "ticketId": ticket_id,
                "actions": actions,
                "replyText": reply_text,
                "status": ticket.get("status"),
            }
        if _is_send_error(result):
            actions.append("OUTBOUND_FAILED")
            await store.add_timeline_event(
                ticket_id,
                "outbound.failed",
                {"provider": normalized["provider"], "error": result},
            )
            return {
                "ticketId": ticket_id,
                "actions": actions,
                "replyText": reply_text,
                "status": ticket.get("status"),
            }

        message_id = _extract_message_id(result)
        if not message_id:
            actions.append("OUTBOUND_FAILED")
            await store.add_timeline_event(
                ticket_id,
                "outbound.failed",
                {"provider": normalized["provider"], "error": "missing_message_id", "response": result},
            )
            return {
                "ticketId": ticket_id,
                "actions": actions,
                "replyText": reply_text,
                "status": ticket.get("status"),
            }

        await events.emit_messaging_outbound(
            ticket_id,
            provider=normalized["provider"],
            channel=normalized["channel"],
            messageId=message_id,
            to=normalized["from"],
            text=reply_text,
            sentAt=_epoch_ms(),
        )
        store.add_message(
            ticket_id,
            {
                "direction": "outbound",
                "provider": normalized["provider"],
                "channel": normalized["channel"],
                "messageId": message_id,
                "text": reply_text,
                "at": _epoch_ms(),
                "mediaCount": 0,
            },
        )
        actions.append("OUTBOUND_SENT")
        return {
            "ticketId": ticket_id,
            "actions": actions,
            "replyText": reply_text,
            "status": ticket.get("status"),
        }
    
    # Handle RESERVATION / DOCS as before (legacy flow fallback)
    if intent in ("RESERVATION", "DOCS"):
        # ... (keep existing logic for reservation/docs)
        assignment_due_at = _epoch_ms() + ASSIGNMENT_SLA_MS
        doc_validation_due_at = _epoch_ms() + DOC_VALIDATION_SLA_MS
        ticket["sla"] = {
            "assignmentStartedAt": _epoch_ms(),
            "assignmentDueAt": assignment_due_at,
            "docValidationStartedAt": _epoch_ms(),
            "docValidationDueAt": doc_validation_due_at,
        }
        store.touch_ticket(ticket_id)

        await events.emit_ticket_updated(
            ticket_id,
            ticket.get("status"),
            ticket.get("status"),
            {"sla": ticket["sla"]},
            actor="system",
        )

        await store.assign_ticket(
            ticket_id,
            {"team": "ADMIN", "name": "Admin - Lucía"},
        )
        actions.append("ASSIGNED_ADMIN")

        if (ticket.get("status") or "").upper() != "WAITING_DOCS":
            prev_status = ticket.get("status")
            await store.set_status(ticket_id, "WAITING_DOCS")
            if (ticket.get("status") or "").upper() == "WAITING_DOCS" and ticket.get("status") != prev_status:
                actions.append("STATUS_WAITING_DOCS")

        await events.emit_ticket_sla_started(ticket_id, "ASSIGNMENT", assignment_due_at)
        await events.emit_ticket_sla_started(ticket_id, "DOC_VALIDATION", doc_validation_due_at)
        actions.append("SLA_STARTED")

        reply_text = _pick_whatsapp_reply_text(ai_response_text, _build_docs_reply())
        try:
            result = await _send_whatsapp_text(normalized["provider"], normalized["from"], reply_text)
        except (MetaWhatsAppSendError, GupshupWhatsAppSendError) as exc:
            actions.append("OUTBOUND_FAILED")
            status_code = getattr(exc, "upstream_status", None) or getattr(exc, "status_code", 500)
            err_body = getattr(exc, "upstream_body", None) or getattr(exc, "err", str(exc))
            error_payload = {"status_code": status_code, "err": err_body}
            await _emit_outbound_failed(
                ticket_id,
                normalized["provider"],
                normalized["channel"],
                normalized["from"],
                reply_text,
                error_payload,
            )

            return {
                "ticketId": ticket_id,
                "actions": actions,
                "replyText": reply_text,
                "status": ticket.get("status"),
            }
        if _is_send_error(result):
            actions.append("OUTBOUND_FAILED")
            await store.add_timeline_event(
                ticket_id,
                "outbound.failed",
                {"provider": normalized["provider"], "error": result},
            )
            return {
                "ticketId": ticket_id,
                "actions": actions,
                "replyText": reply_text,
                "status": ticket.get("status"),
            }

        message_id = _extract_message_id(result)
        if not message_id:
            actions.append("OUTBOUND_FAILED")
            await store.add_timeline_event(
                ticket_id,
                "outbound.failed",
                {"provider": normalized["provider"], "error": "missing_message_id", "response": result},
            )
            return {
                "ticketId": ticket_id,
                "actions": actions,
                "replyText": reply_text,
                "status": ticket.get("status"),
            }

        await events.emit_messaging_outbound(
            ticket_id,
            provider=normalized["provider"],
            channel=normalized["channel"],
            messageId=message_id,
            to=normalized["from"],
            text=reply_text,
            sentAt=_epoch_ms(),
        )
        store.add_message(
            ticket_id,
            {
                "direction": "outbound",
                "provider": normalized["provider"],
                "channel": normalized["channel"],
                "messageId": message_id,
                "text": reply_text,
                "at": _epoch_ms(),
                "mediaCount": 0,
            },
        )
        actions.append("OUTBOUND_SENT")
        return {
            "ticketId": ticket_id,
            "actions": actions,
            "replyText": reply_text,
            "status": ticket.get("status"),
        }

    return {
        "ticketId": ticket_id,
        "actions": actions,
        "status": ticket.get("status"),
    }
