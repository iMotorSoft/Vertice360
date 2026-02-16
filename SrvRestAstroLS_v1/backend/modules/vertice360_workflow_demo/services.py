from __future__ import annotations

import datetime as dt
import asyncio
import hashlib
import json
import logging
import re
import time
import unicodedata
from collections import deque, OrderedDict
from threading import Lock
from typing import Any

from backend import globalVar
from backend.modules.messaging.providers.gupshup.whatsapp.service import (
    GupshupWhatsAppSendError,
    send_text_message as gupshup_send_text,
)
from backend.modules.messaging.providers.meta.whatsapp.service import (
    MetaWhatsAppSendError,
    send_text_message as meta_send_text,
)
from backend.modules.vertice360_ai_workflow_demo import services as ai_workflow_services
from backend.modules.vertice360_workflow_demo import commercial_memory, events, store

# Shared lock to protect the user_locks dictionary itself
_user_locks_registry_lock = Lock()
_user_locks: dict[str, asyncio.Lock] = {}


def _get_user_lock(user_id: str) -> asyncio.Lock:
    with _user_locks_registry_lock:
        if user_id not in _user_locks:
            _user_locks[user_id] = asyncio.Lock()
        return _user_locks[user_id]


ASSIGNMENT_SLA_MS = 30 * 60 * 1000
DOC_VALIDATION_SLA_MS = 24 * 60 * 60 * 1000
INBOUND_DEDUPE_TTL_SECONDS = 600
INBOUND_DEDUPE_MAX_KEYS = 5000
WORKFLOW_INTRO_PREFIX = "Soy el asistente de Vértice360 👋. "
VISIT_SLOT_PROMPT = "Para coordinar visita, decime día y franja horaria."
SHORT_ACK_TOKENS = {
    "hi",
    "hola",
    "hello",
    "buenas",
    "ok",
    "oka",
    "dale",
    "?",
}
INVALID_ZONA_REPLY = (
    "¿Buscás en CABA/GBA? Decime un barrio (ej: Palermo, Almagro...)"
)
ZONA_CANDIDATE_STOPWORDS = {
    "hola",
    "hi",
    "hello",
    "busco",
    "buscar",
    "quiero",
    "necesito",
    "depto",
    "departamento",
    "propiedad",
    "alquiler",
    "comprar",
    "compra",
    "venta",
    "por",
    "en",
    "zona",
    "barrio",
    "caba",
    "gba",
    "capital",
    "federal",
}

logger = logging.getLogger(__name__)
_inbound_seen_cache: OrderedDict[str, float] = OrderedDict()
_inbound_seen_lock = Lock()


def _is_slot_value_present(value: Any) -> bool:
    return value not in (None, "", "UNKNOWN")


def _extract_provider_message_id(
    inbound: dict[str, Any], normalized: dict[str, Any]
) -> str | None:
    for key in ("messageId", "message_id", "wamid", "id", "external_message_id"):
        value = inbound.get(key)
        if value:
            return str(value)
    raw = inbound.get("raw")
    if isinstance(raw, dict):
        for key in ("messageId", "message_id", "wamid", "id"):
            value = raw.get(key)
            if value:
                return str(value)
    normalized_id = str(normalized.get("messageId") or "").strip()
    if normalized_id and not normalized_id.startswith("local-"):
        return normalized_id
    return None


def _build_inbound_key(inbound: dict[str, Any], normalized: dict[str, Any]) -> str:
    provider = str(normalized.get("provider") or inbound.get("provider") or "unknown")
    provider_message_id = _extract_provider_message_id(inbound, normalized)
    if provider_message_id:
        return f"provider:{provider}:id:{provider_message_id}"

    basis = "|".join(
        [
            provider,
            str(normalized.get("from") or ""),
            str(normalized.get("timestamp") or ""),
            str(normalized.get("text") or ""),
        ]
    )
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]
    return f"provider:{provider}:hash:{digest}"


def _mark_inbound_processed(inbound_key: str) -> bool:
    now = time.monotonic()
    cutoff = now - INBOUND_DEDUPE_TTL_SECONDS
    with _inbound_seen_lock:
        stale_keys = [
            key for key, seen_at in _inbound_seen_cache.items() if seen_at < cutoff
        ]
        for key in stale_keys:
            _inbound_seen_cache.pop(key, None)
        while len(_inbound_seen_cache) > INBOUND_DEDUPE_MAX_KEYS:
            _inbound_seen_cache.popitem(last=False)

        if inbound_key in _inbound_seen_cache:
            _inbound_seen_cache.move_to_end(inbound_key)
            return False

        _inbound_seen_cache[inbound_key] = now
        _inbound_seen_cache.move_to_end(inbound_key)
        return True


def reset_inbound_dedupe_cache() -> None:
    with _inbound_seen_lock:
        _inbound_seen_cache.clear()


async def send_text_message(to: str, text: str) -> dict[str, Any]:
    """Backward-compatible alias used by tests and demo hooks."""
    return await meta_send_text(to, text)


def _epoch_ms() -> int:
    return int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in normalized if not unicodedata.combining(char))
    return stripped.lower()


def _preview_text(text: Any, limit: int = 30) -> str:
    compact = " ".join(str(text or "").split())
    return compact[:limit]


def _phone_last4(phone: Any) -> str:
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if not digits:
        return "----"
    return digits[-4:]


def _duration_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _build_correlation_id(normalized: dict[str, Any]) -> str:
    provider = str(normalized.get("provider") or "unknown")
    message_id = str(normalized.get("messageId") or "no-message-id")
    return f"{provider}:{message_id}"


def _looks_like_invalid_zona_input(text: str) -> bool:
    norm = " ".join(_normalize_text(text or "").split())
    if not norm:
        return False
    if _is_short_ack_or_greeting(norm):
        return False
    if any(ch.isdigit() for ch in norm):
        return False
    if commercial_memory.parse_tipologia(norm):
        return False
    amount, _currency = commercial_memory.parse_budget_currency(norm)
    if amount is not None:
        return False
    tokens = re.findall(r"[a-z]+", norm)
    meaningful = [token for token in tokens if token not in ZONA_CANDIDATE_STOPWORDS]
    if not meaningful:
        return False
    return len(meaningful) <= 4


def _extract_commercial_slots(text: str) -> dict[str, Any]:
    """Extract commercial slots - mudanza removed (flujo simplificado)."""
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

    # Note: fecha_mudanza removed - flow goes directly to handoff after presupuesto

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


def _build_contextual_input_from_slot_memory(
    slot_memory: dict[str, Any], message: str, intent: str | None
) -> str:
    slot_parts = []
    # Note: fecha_mudanza removed from context (flujo simplificado)
    for key in ("zona", "tipologia", "presupuesto_amount", "moneda"):
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


def _sync_ai_commercial_slots(
    ai_context: dict[str, Any], commercial: dict[str, Any]
) -> None:
    slots = ai_context.get("commercialSlots")
    if not isinstance(slots, dict):
        slots = {}
        ai_context["commercialSlots"] = slots
    for key in commercial_memory.COMMERCIAL_SLOT_PRIORITY:
        slots[key] = commercial.get(key)


def _ensure_slot_memory(ticket: dict[str, Any]) -> dict[str, Any]:
    """Ensure slot memory exists - fecha_mudanza removed (flujo simplificado)."""
    slot_memory = ticket.get("slot_memory")
    if not isinstance(slot_memory, dict):
        slot_memory = {}
        ticket["slot_memory"] = slot_memory
    slot_memory.setdefault("zona", None)
    slot_memory.setdefault("tipologia", None)
    slot_memory.setdefault("presupuesto_amount", None)
    slot_memory.setdefault("presupuesto_raw", None)
    slot_memory.setdefault("moneda", None)
    # Note: fecha_mudanza removed - flow goes directly to handoff after presupuesto
    slot_memory.setdefault("budget_ambiguous", False)
    slot_memory.setdefault("budget_confirmed", False)
    slot_memory.setdefault("confirmed_budget", False)
    slot_memory.setdefault("confirmed_currency", False)
    slot_memory.setdefault("last_question", None)
    slot_memory.setdefault("last_question_key", None)
    slot_memory.setdefault("last_asked_slot", None)
    slot_memory.setdefault("asked_count", 0)
    slot_memory.setdefault("pending_ambiguity", None)
    slot_memory.setdefault("answered_fields", [])
    slot_memory.setdefault("summarySent", False)
    slot_memory.setdefault("intro_sent", False)
    slot_memory.setdefault("visit_slot", None)
    slot_memory.setdefault("handoff_completed", False)  # New flag to track handoff
    return slot_memory


def _normalize_answered_fields(raw: Any) -> set[str]:
    if isinstance(raw, list):
        return {str(item).strip().lower() for item in raw if str(item).strip()}
    return set()


def _update_answered_fields(
    slot_memory: dict[str, Any],
    commercial: dict[str, Any],
) -> list[str]:
    """Update answered fields - mudanza removed (flujo simplificado)."""
    answered = _normalize_answered_fields(slot_memory.get("answered_fields"))
    if _is_slot_value_present(commercial.get("zona")):
        answered.add("zona")
    if _is_slot_value_present(commercial.get("tipologia")):
        answered.add("ambientes")
    if _is_slot_value_present(commercial.get("presupuesto")):
        answered.add("presupuesto")
    # Note: fecha_mudanza/mudanza removed - flow goes directly to handoff after presupuesto
    ordered = sorted(answered)
    slot_memory["answered_fields"] = ordered
    return ordered


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


def _detect_budget_ambiguity(
    text: str, amount: int | None, currency: str | None
) -> bool:
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


def _build_budget_ambiguity_question(
    currency: str | None, amount: int | None
) -> str | None:
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
            if slot_memory.get("confirmed_budget") and slot_memory.get(
                "presupuesto_amount"
            ) not in (
                None,
                "",
                "UNKNOWN",
            ):
                if slot_memory.get("presupuesto_amount") != value:
                    continue
        if key == "moneda":
            if slot_memory.get("confirmed_currency") and slot_memory.get(
                "moneda"
            ) not in (
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
        if confirmed.get("budget") and slot_memory.get("presupuesto_amount") not in (
            None,
            "",
            "UNKNOWN",
        ):
            slot_memory["confirmed_budget"] = True
        if confirmed.get("currency") and slot_memory.get("moneda") not in (
            None,
            "",
            "UNKNOWN",
        ):
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
    # Note: fecha_mudanza removed - flow goes directly to handoff after presupuesto
    return missing


def _question_for_slot(
    slot: str, slot_memory: dict[str, Any], missing: set[str]
) -> str | None:
    """Build question for a specific slot with human-like partial acknowledgment.

    This function is used as a fallback when anti-repetition logic triggers.
    For primary question logic, see commercial_memory.build_next_best_question().
    """
    zona_value = slot_memory.get("zona")
    tipologia_value = slot_memory.get("tipologia")

    if slot == "zona":
        # Check if we have ambientes to acknowledge
        if tipologia_value and _is_slot_value_present(tipologia_value):
            # Extract ambientes count for natural language
            match = re.search(r"(\d+)", str(tipologia_value))
            if match:
                ambientes_count = match.group(1)
                return f"Perfecto, {ambientes_count} ambientes. ¿Por qué zona buscás?"
            elif "monoambiente" in str(tipologia_value).lower():
                return "Perfecto, monoambiente. ¿Por qué zona buscás?"
            else:
                return f"Perfecto, {tipologia_value}. ¿Por qué zona buscás?"
        if "tipologia" in missing:
            return "¿Por qué zona buscás y qué tipología (ambientes)?"
        return "¿En qué zona o barrio estás buscando?"

    if slot == "tipologia":
        # Check if we have zona to acknowledge
        if zona_value and _is_slot_value_present(zona_value):
            return f"Perfecto, zona {zona_value}. ¿Cuántos ambientes necesitás?"
        return "¿Qué tipología buscás? (Ej: 2 ambientes, monoambiente)"

    if slot in ("presupuesto", "moneda"):
        amount = slot_memory.get("presupuesto_amount")
        currency = slot_memory.get("moneda")
        if amount not in (None, "", "UNKNOWN") and not currency:
            return "¿En qué moneda está ese presupuesto?"
        if currency and amount in (None, "", "UNKNOWN"):
            return "¿Cuál es tu presupuesto aproximado?"
        return "¿Cuál es tu presupuesto aproximado y moneda?"

    # Note: fecha_mudanza question removed (flujo simplificado)
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
    # Note: fecha_mudanza removed - flow goes directly to handoff after presupuesto

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
    priority = ["zona", "tipologia", "presupuesto", "moneda"]  # fecha_mudanza removed
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
        # Note: fecha_mudanza fallback removed (flujo simplificado)
    if current == last_question:
        return "¿Podés confirmarlo para avanzar?", asked_slot
    return question, asked_slot


def _build_summary_close(slot_memory: dict[str, Any]) -> str:
    """Build final summary message after presupuesto is captured (flujo simplificado - no mudanza)."""
    zona = slot_memory.get("zona") or "?"
    tipologia = slot_memory.get("tipologia") or "?"
    presupuesto = _format_amount(
        slot_memory.get("presupuesto_amount")
        if slot_memory.get("presupuesto_amount") not in (None, "", "UNKNOWN")
        else slot_memory.get("presupuesto")
    )
    moneda = slot_memory.get("moneda") or "?"
    # Note: fecha_mudanza removed - new message format per requirements
    return (
        f"Gracias. Tengo: zona {zona}, {tipologia}, presupuesto {presupuesto} {moneda}.\n"
        f"Un asesor te va a enviar días y horarios disponibles para generar una visita."
    )


def _extract_ambientes(value: Any) -> int | None:
    if value is None:
        return None
    match = re.search(r"\b(\d{1,2})\b", str(value))
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


async def _emit_handoff_action_required(
    ticket_id: str,
    provider: str | None,
    commercial: dict[str, Any] | None,
    source_payload: dict[str, Any] | None = None,
) -> None:
    commercial = commercial or {}
    source_payload = source_payload or {}
    source_summary = (
        source_payload.get("summary")
        if isinstance(source_payload.get("summary"), dict)
        else {}
    )
    budget = source_summary.get("presupuesto_usd")
    if budget is None:
        budget = commercial.get("presupuesto")
    try:
        budget = int(budget) if budget is not None else None
    except (TypeError, ValueError):
        budget = None
    if budget is None:
        budget = 120000

    # Note: mudanza/fecha_mudanza removed from summary (flujo simplificado)
    summary = {
        "zona": source_summary.get("zona") or commercial.get("zona") or "Palermo",
        "ambientes": source_summary.get("ambientes")
        or _extract_ambientes(commercial.get("tipologia"))
        or 3,
        "presupuesto_usd": budget,
    }
    payload = {
        "reason": source_payload.get("reason") or "schedule_visit",
        "summary": summary,
        "suggested_next_message": (
            source_payload.get("suggested_next_message")
            or "Hola, soy {OPERATOR_NAME}... (slots...)"
        ),
        "ticket_id": ticket_id,
        "provider": provider,
    }
    await events.emit_event("human.action_required", ticket_id, payload)


def _is_handoff_paused(ticket: dict[str, Any]) -> bool:
    stage = str(ticket.get("handoffStage") or "").strip().lower()
    if stage in {"required", "operator_engaged"}:
        return True
    return bool(ticket.get("handoffRequired"))


def _build_visit_slot_prompt() -> str:
    return VISIT_SLOT_PROMPT


def _is_short_ack_or_greeting(text: str) -> bool:
    normalized = " ".join(_normalize_text(text or "").split())
    if not normalized:
        return True
    compact = normalized.strip()
    if compact in SHORT_ACK_TOKENS:
        return True
    alnum = "".join(ch for ch in compact if ch.isalnum() or ch.isspace()).strip()
    if not alnum:
        return True
    return len(alnum.split()) <= 2 and alnum in SHORT_ACK_TOKENS


def _all_required_commercial_fields(commercial: dict[str, Any]) -> bool:
    """Check if all required fields are present - fecha_mudanza removed (flujo simplificado)."""
    return all(
        _is_slot_value_present(commercial.get(key))
        for key in ("zona", "tipologia", "presupuesto", "moneda")
    )


def _resolve_flow_stage(
    ticket: dict[str, Any], commercial: dict[str, Any], slot_memory: dict[str, Any]
) -> str:
    handoff_stage = str(ticket.get("handoffStage") or "").strip().lower()
    if handoff_stage == "operator_engaged":
        return "operator_engaged"
    if _all_required_commercial_fields(commercial) and not slot_memory.get(
        "visit_slot"
    ):
        return "handoff_scheduling"
    return "collecting_profile"


def _set_flow_stage(
    ticket: dict[str, Any],
    ticket_id: str,
    from_phone: str | None,
    new_stage: str,
    answered_fields: list[str] | None,
) -> str:
    stage_before = str(ticket.get("flowStage") or "collecting_profile")
    stage_after = str(new_stage or "collecting_profile")
    ticket["flowStage"] = stage_after
    if stage_before != stage_after:
        store.touch_ticket(ticket_id)
        logger.info(
            "STAGE_TRANSITION ticket=%s from=%s stage_before=%s stage_after=%s answered_fields=%s",
            ticket_id,
            _phone_last4(from_phone),
            stage_before,
            stage_after,
            answered_fields or [],
        )
    return stage_after


def _recent_message_texts(ticket: dict[str, Any], limit: int = 3) -> list[str]:
    messages = ticket.get("messages") or []
    texts = [msg.get("text") for msg in messages if msg.get("text")]
    return texts[-limit:]


def _canonical_outbound_text(text: str | None) -> str:
    clean = _normalize_question(text)
    if clean.startswith(WORKFLOW_INTRO_PREFIX):
        clean = clean[len(WORKFLOW_INTRO_PREFIX) :].strip()
    return clean


def _is_duplicate_outbound_text(ticket: dict[str, Any], text: str | None) -> bool:
    current = _canonical_outbound_text(text)
    if not current:
        return False
    messages = ticket.get("messages") or []
    for message in reversed(messages):
        if message.get("direction") != "outbound":
            continue
        previous = _canonical_outbound_text(message.get("text"))
        return bool(previous and previous == current)
    return False


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
    started_at = time.perf_counter()
    try:
        result = await ai_workflow_services.run_workflow(
            "vertice360-ai-workflow",
            workflow_input,
            metadata=metadata,
            context=context,
        )
    except Exception as exc:
        logger.warning(
            "LLM_CALL failed ticket=%s message_id=%s duration_ms=%s error=%s",
            ticket_id,
            message_id,
            _duration_ms(started_at),
            type(exc).__name__,
        )
        return None
    logger.info(
        "LLM_CALL completed ticket=%s message_id=%s duration_ms=%s",
        ticket_id,
        message_id,
        _duration_ms(started_at),
    )
    if isinstance(result, dict):
        output = result.get("output")
        if isinstance(output, dict):
            return output
    return None


def classify_intent(text: str) -> str:
    normalized = _normalize_text(text or "")
    if any(
        token in normalized
        for token in ("document", "dni", "pasaporte", "comprobante", "adjunto", "foto")
    ):
        return "DOCS"
    if any(token in normalized for token in ("reserv", "unidad", "2b", "febrero")):
        return "RESERVATION"
    if any(
        token in normalized for token in ("hola", "buenas", "buen dia", "buenas tardes")
    ):
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
    message_id = (
        inbound.get("messageId") or inbound.get("message_id") or inbound.get("id")
    )
    if not message_id:
        message_id = f"local-{normalized_timestamp}"

    media_count = inbound.get("mediaCount", 0)
    try:
        media_count = int(media_count)
    except (TypeError, ValueError):
        media_count = 0

    ai_response_text = inbound.get("aiResponseText") or inbound.get("ai_response_text")
    ai_decision = inbound.get("aiDecision") or inbound.get("ai_decision")
    ai_handoff_required = inbound.get("aiHandoffRequired")
    human_action_required = inbound.get("humanActionRequired")

    return {
        "provider": inbound.get("provider") or "meta_whatsapp",
        "app": inbound.get("app"),
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
        "aiDecision": ai_decision,
        "aiHandoffRequired": bool(ai_handoff_required)
        if ai_handoff_required is not None
        else False,
        "humanActionRequired": human_action_required
        if isinstance(human_action_required, dict)
        else None,
    }


def _build_ticket_seed(normalized: dict[str, Any]) -> dict[str, Any]:
    subject = normalized["text"].strip() if normalized["text"] else "Inbound message"
    if len(subject) > 120:
        subject = f"{subject[:117]}..."
    return {
        "ticketId": normalized.get("ticketId"),
        "provider": normalized["provider"],
        "app": normalized.get("app"),
        "channel": normalized["channel"],
        "text": normalized["text"],
        "timestamp": normalized["timestamp"],
        "customer": {
            "from": normalized["from"],
            "to": normalized["to"],
            "provider": normalized["provider"],
            "app": normalized.get("app"),
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
    return await send_text_message(to, text)


async def _send_whatsapp_text_with_context(
    provider: str,
    to: str,
    text: str,
    *,
    ticket_id: str | None = None,
    run_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    is_gupshup = provider == "gupshup_whatsapp"
    started_at = time.perf_counter()
    if is_gupshup:
        logger.info(
            "GUPSHUP_OUTBOUND attempting to=%s ticket=%s runId=%s correlation_id=%s",
            to,
            ticket_id or "-",
            run_id or "-",
            correlation_id or "-",
        )
    try:
        result = await _send_whatsapp_text(provider, to, text)
    except Exception as exc:
        if is_gupshup:
            logger.warning(
                "GUPSHUP_OUTBOUND failed ticket=%s correlation_id=%s duration_ms=%s error=%s",
                ticket_id or "-",
                correlation_id or "-",
                _duration_ms(started_at),
                exc,
            )
        raise
    logger.info(
        "OUTBOUND_SEND completed provider=%s ticket=%s correlation_id=%s duration_ms=%s",
        provider,
        ticket_id or "-",
        correlation_id or "-",
        _duration_ms(started_at),
    )
    if is_gupshup:
        message_id = _extract_message_id(result) or "-"
        logger.info(
            "GUPSHUP_OUTBOUND ok ticket=%s correlation_id=%s message_id=%s",
            ticket_id or "-",
            correlation_id or "-",
            message_id,
        )
    return result


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
        result = await _send_whatsapp_text_with_context(
            provider,
            to,
            text,
            ticket_id=ticket_id,
            run_id=None,
        )
    except (MetaWhatsAppSendError, GupshupWhatsAppSendError) as exc:
        status_code = getattr(exc, "upstream_status", None) or getattr(
            exc, "status_code", 500
        )
        err_body = getattr(exc, "upstream_body", None) or getattr(exc, "err", str(exc))
        error_payload = {"status_code": status_code, "err": err_body}
        await _emit_outbound_failed(
            ticket_id, provider, channel, to, text, error_payload
        )
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
    store.set_handoff_required(ticket_id, False, None)
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
    return any(
        w in norm
        for w in (
            "si",
            "ok",
            "correcto",
            "dale",
            "perfecto",
            "bueno",
            "confirmado",
            "esta bien",
        )
    )


def _build_commercial_summary(slots: dict[str, Any]) -> str:
    """Build commercial summary - mudanza removed (flujo simplificado)."""
    lines = []
    lines.append(f"• Zona: {slots.get('zona') or '?'}")
    lines.append(f"• Tipología: {slots.get('tipologia') or '?'}")
    val_presup = slots.get("presupuesto")
    mon = slots.get("moneda") or ""
    if val_presup:
        lines.append(f"• Presupuesto: {mon} {val_presup}")
    else:
        lines.append(f"• Presupuesto: ?")
    # Note: Mudanza line removed (flujo simplificado)
    return "\n".join(lines)


async def process_inbound_message(inbound: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_inbound(inbound)
    user_id = normalized.get("from") or "unknown"
    lock = _get_user_lock(user_id)

    async with lock:
        started_at = time.perf_counter()
        timings_ms: dict[str, int] = {}
        correlation_id = _build_correlation_id(normalized)
        decision: str | None = None
        ticket: dict[str, Any] | None = None
        ticket_id = "-"
        answered_fields: list[str] = []
        current_missing_slots: list[str] = []

        def _finalize(payload: dict[str, Any], outcome: str) -> dict[str, Any]:
            timings_ms["total_ms"] = _duration_ms(started_at)
            logger.info(
                "INBOUND_RESULT correlation_id=%s received_at_ms=%s message_id=%s user_phone=%s ticket_id=%s outcome=%s decision=%s answered=%s missing=%s handoff_required=%s handoff_stage=%s actions=%s timings_ms=%s",
                correlation_id,
                normalized.get("timestamp"),
                normalized.get("messageId"),
                normalized.get("from"),
                ticket_id,
                outcome,
                decision or "-",
                answered_fields,
                current_missing_slots,
                bool(ticket.get("handoffRequired")) if ticket else False,
                ticket.get("handoffStage") if ticket else None,
                payload.get("actions") if isinstance(payload, dict) else None,
                timings_ms,
            )
            return payload

        inbound_key = _build_inbound_key(inbound, normalized)
        if not _mark_inbound_processed(inbound_key):
            logger.info(
                "DUPLICATE INBOUND ignored correlation_id=%s inbound_key=%s provider=%s from=%s message_id=%s",
                correlation_id,
                inbound_key,
                normalized.get("provider"),
                normalized.get("from"),
                normalized.get("messageId"),
            )
            return _finalize(
                {
                "duplicate": True,
                "inboundKey": inbound_key,
                "actions": ["DUPLICATE_INBOUND_IGNORED"],
                },
                "duplicate_ignored",
            )
        logger.info(
            "INBOUND_ACCEPTED correlation_id=%s inbound_key=%s provider=%s from=%s message_id=%s received_at_ms=%s",
            correlation_id,
            inbound_key,
            normalized.get("provider"),
            normalized.get("from"),
            normalized.get("messageId"),
            normalized.get("timestamp"),
        )
        actions: list[str] = []
        ai_response_text = normalized.get("aiResponseText")
        ai_decision_prefill = normalized.get("aiDecision")
        ai_handoff_prefill = bool(normalized.get("aiHandoffRequired"))
        ai_human_action_prefill = normalized.get("humanActionRequired")

        logger.debug(
            'INBOUND_SEED from=%s text="%s" timestamp=%s provider=%s message_id=%s',
            _phone_last4(normalized.get("from")),
            _preview_text(normalized.get("text")),
            normalized.get("timestamp"),
            normalized.get("provider"),
            normalized.get("messageId"),
        )
        ticket_seed = _build_ticket_seed(normalized)
        db_started_at = time.perf_counter()
        ticket = await store.create_or_get_ticket_from_inbound(ticket_seed)
        timings_ms["db_ticket_load_ms"] = _duration_ms(db_started_at)
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
        timings_ms["db_ticket_save_ms"] = timings_ms.get("db_ticket_save_ms", 0)
        actions.append("INBOUND_EMITTED")

        # Manual extraction (ensures state update even if AI is disabled)
        extracted_this_turn = _extract_commercial_slots(normalized["text"])
        slot_memory = _ensure_slot_memory(ticket)
        should_parse_visit = bool(slot_memory.get("summarySent")) or bool(
            ticket.get("handoffRequired")
        )
        if should_parse_visit:
            visit_slot_this_turn = commercial_memory.parse_visita(normalized["text"])
            if isinstance(visit_slot_this_turn, dict) and visit_slot_this_turn:
                slot_memory["visit_slot"] = visit_slot_this_turn

        # Avoid overriding a confirmed budget with a later ambiguous short number ("usd 120")
        if slot_memory.get("budget_confirmed"):
            maybe_amount = extracted_this_turn.get("presupuesto")
            maybe_currency = extracted_this_turn.get("moneda") or slot_memory.get(
                "moneda"
            )
            if _detect_budget_ambiguity(
                normalized["text"], maybe_amount, maybe_currency
            ):
                extracted_this_turn.pop("presupuesto", None)
                extracted_this_turn.pop("moneda", None)

        if extracted_this_turn:
            db_started_at = time.perf_counter()
            store.update_ticket_commercial(ticket_id, extracted_this_turn)
            timings_ms["db_ticket_save_ms"] = timings_ms.get(
                "db_ticket_save_ms", 0
            ) + _duration_ms(db_started_at)

        # --- AI WORKFLOW ORCHESTRATION ---
        ai_context = _ensure_ai_context(ticket)
        current_commercial = ticket.get("commercial") or {}

        # Sync slot memory from persisted commercial state.
        slot_memory["zona"] = current_commercial.get("zona")
        slot_memory["tipologia"] = current_commercial.get("tipologia")
        # Note: fecha_mudanza sync removed (flujo simplificado)
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
        if _detect_budget_ambiguity(
            normalized["text"], amount_now, currency_now
        ) and not slot_memory.get("budget_confirmed"):
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
        if (
            isinstance(pending_ambiguity, dict)
            and pending_ambiguity
            and _is_affirmative(normalized["text"])
        ):
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
            db_started_at = time.perf_counter()
            store.update_ticket_commercial(
                ticket_id,
                {
                    "presupuesto": current_commercial.get("presupuesto"),
                    "moneda": current_commercial.get("moneda"),
                },
            )
            timings_ms["db_ticket_save_ms"] = timings_ms.get(
                "db_ticket_save_ms", 0
            ) + _duration_ms(db_started_at)

        # Determine intent lock status based on history or signals.
        if ai_context.get("primaryIntentLocked") != "property_search":
            has_commercial_signal = any(
                value not in (None, "", "UNKNOWN")
                for value in current_commercial.values()
            )
            if has_commercial_signal or _is_property_search_text(normalized["text"]):
                ai_context["primaryIntentLocked"] = "property_search"

        property_search_locked = (
            ai_context.get("primaryIntentLocked") == "property_search"
        )
        contextual_input = _build_contextual_input_from_slot_memory(
            slot_memory,
            normalized["text"],
            "property_search" if property_search_locked else None,
        )

        # 2. Run AI workflow (for reasoning + run trace/indexing).
        ai_output = None
        pre_ai_missing_slots = commercial_memory.calculate_missing_slots(current_commercial)
        should_fast_path_greeting = _is_short_ack_or_greeting(
            normalized["text"]
        ) and bool(pre_ai_missing_slots)
        if should_fast_path_greeting:
            actions.append("FAST_PATH_GREETING")
            decision = "fast_path_greeting"
            logger.info(
                "INBOUND_FAST_PATH correlation_id=%s ticket_id=%s reason=greeting_missing_slots missing=%s",
                correlation_id,
                ticket_id,
                pre_ai_missing_slots,
            )
        elif not ai_response_text:
            llm_started_at = time.perf_counter()
            ai_output = await _run_ai_workflow_reply(
                contextual_input,
                normalized["messageId"],
                ticket_id,
                context={
                    "intentHint": "property_search" if property_search_locked else None,
                    "commercialSlots": current_commercial,
                    "provider": normalized["provider"],
                    "ticketId": ticket_id,
                },
            )
            timings_ms["llm_ms"] = _duration_ms(llm_started_at)

        # 3. Keep canonical commercial state from deterministic parser.
        # AI output is used for decisioning text, but slot values come from parser/memory.
        current_commercial = ticket.get("commercial") or current_commercial
        answered_fields = _update_answered_fields(slot_memory, current_commercial)
        flow_stage = _resolve_flow_stage(ticket, current_commercial, slot_memory)
        flow_stage = _set_flow_stage(
            ticket,
            ticket_id,
            normalized.get("from"),
            flow_stage,
            answered_fields,
        )
        if flow_stage == "handoff_scheduling":
            store.set_handoff_required(ticket_id, True, "schedule_visit")
        logger.info(
            "INBOUND_STATE correlation_id=%s inbound_key=%s ticket=%s answered=%s handoff_required=%s handoff_stage=%s",
            correlation_id,
            inbound_key,
            ticket_id,
            answered_fields,
            bool(ticket.get("handoffRequired")),
            ticket.get("handoffStage"),
        )

        if flow_stage == "operator_engaged" and not ai_handoff_prefill:
            await _emit_handoff_action_required(
                ticket_id=ticket_id,
                provider=normalized.get("provider"),
                commercial=ticket.get("commercial") or {},
            )
            actions.append("HANDOFF_WAITING_OPERATOR")
            decision = "handoff_waiting_operator"
            return _finalize(
                {
                "ticketId": ticket_id,
                "actions": actions,
                "status": ticket.get("status"),
                },
                "accepted_no_outbound",
            )

        handoff_paused = _is_handoff_paused(ticket)
        if (
            handoff_paused
            and flow_stage != "handoff_scheduling"
            and not ai_handoff_prefill
        ):
            await _emit_handoff_action_required(
                ticket_id=ticket_id,
                provider=normalized.get("provider"),
                commercial=ticket.get("commercial") or {},
            )
            actions.append("HANDOFF_WAITING_OPERATOR")
            decision = "handoff_waiting_operator"
            return _finalize(
                {
                "ticketId": ticket_id,
                "actions": actions,
                "status": ticket.get("status"),
                },
                "accepted_no_outbound",
            )

        current_update_keys = set(extracted_this_turn.keys())

        # Emit telemetry
        commercial_missing_slots = commercial_memory.calculate_missing_slots(
            current_commercial,
            answered_fields=answered_fields,
        )
        memory_payload = {
            "missingSlotsCount": len(commercial_missing_slots),
            "missing": commercial_missing_slots,
            "known": [k for k, v in current_commercial.items() if v and v != "UNKNOWN"],
        }
        if current_commercial.get("presupuesto"):
            memory_payload["budget"] = {
                "amount": current_commercial.get("presupuesto"),
                "currency": current_commercial.get("moneda"),
            }
        await events.emit_event("commercial.memory", ticket_id, memory_payload)

        # --- 4. DETERMINE REPLY (Deterministic Logic) ---
        reply_text: str | None = None

        # Check for missing slots in strict order
        current_missing_slots = commercial_memory.calculate_missing_slots(
            current_commercial,
            answered_fields=answered_fields,
        )

        # Priority 1: Budget Ambiguity (immediate resolve)
        pending_ambiguity = slot_memory.get("pending_ambiguity")
        if isinstance(pending_ambiguity, dict) and pending_ambiguity.get("question"):
            reply_text = str(pending_ambiguity.get("question"))
            decision = "resolve_ambiguity"

        # Priority 2: invalid zona guard (do not advance state)
        if not reply_text and "zona" in current_missing_slots:
            last_question_key = str(
                slot_memory.get("last_question_key")
                or slot_memory.get("last_asked_slot")
                or ""
            ).strip().lower()
            extracted_zona = extracted_this_turn.get("zona")
            if (
                last_question_key == "zona"
                and not extracted_zona
                and _looks_like_invalid_zona_input(normalized["text"])
            ):
                reply_text = INVALID_ZONA_REPLY
                decision = "invalid_zona_guard"
                actions.append("INVALID_ZONA_REJECTED")
                slot_memory["last_question"] = reply_text
                slot_memory["last_question_key"] = "zona"
                slot_memory["last_asked_slot"] = "zona"

        # Priority 3: Ask next missing slot (with human-like partial acknowledgment)
        if not reply_text and current_missing_slots:
            rec_q, rec_key = commercial_memory.build_next_best_question(
                current_missing_slots, current_values=current_commercial
            )
            if rec_q:
                reply_text = rec_q
                decision = "ask_next_best_question"
                slot_memory["last_question"] = rec_q
                slot_memory["last_question_key"] = rec_key
                slot_memory["last_asked_slot"] = rec_key

        # Priority 4: Summary (if all present and not sent)
        if not reply_text and not current_missing_slots:
            if not slot_memory.get("summarySent"):
                reply_text = _build_summary_close(current_commercial)
                decision = "summary_close"
                slot_memory["summarySent"] = True
                slot_memory["last_question"] = reply_text
                slot_memory["last_question_key"] = "summary"

                # Set handoff flags
                store.set_handoff_required(ticket_id, True, "schedule_visit")
                _set_flow_stage(
                    ticket,
                    ticket_id,
                    normalized.get("from"),
                    "handoff_scheduling",
                    answered_fields,
                )
                actions.append("HANDOFF_REQUIRED")
            else:
                # Profile is complete; until visit_slot is provided keep prompting scheduling.
                if not slot_memory.get("visit_slot"):
                    reply_text = _build_visit_slot_prompt()
                    decision = "ask_visit_slot"
                    if _is_short_ack_or_greeting(normalized["text"]):
                        actions.append("HANDOFF_SCHEDULING_REPROMPT")
                else:
                    logger.info(
                        "Summary already sent for ticket %s and visit_slot exists; waiting operator follow-up.",
                        ticket_id,
                    )
                    actions.append("HANDOFF_WAITING_OPERATOR")
                    decision = "handoff_waiting_operator"
                    return _finalize(
                        {
                        "ticketId": ticket_id,
                        "actions": actions,
                        "status": ticket.get("status"),
                        },
                        "accepted_no_outbound",
                    )

        # --- Prepend Intro once per ticket (except summary close) ---
        if (
            reply_text
            and decision != "summary_close"
            and not slot_memory.get("intro_sent")
        ):
            if not reply_text.startswith(WORKFLOW_INTRO_PREFIX):
                reply_text = f"{WORKFLOW_INTRO_PREFIX}{reply_text}"
            slot_memory["intro_sent"] = True

        # Use AI output if deterministic failed (shouldn't happen for property_search)
        if not reply_text and ai_output:
            reply_text = _select_ai_reply(ai_output)
            decision = ai_output.get("decision")

        if not reply_text:
            # Fallback
            reply_text = _build_commercial_fallback()
            decision = "fallback"

        logger.info(
            "INBOUND_DECISION correlation_id=%s ticket_id=%s decision=%s answered=%s missing=%s handoff_required=%s handoff_stage=%s",
            correlation_id,
            ticket_id,
            decision or "-",
            answered_fields,
            current_missing_slots,
            bool(ticket.get("handoffRequired")),
            ticket.get("handoffStage"),
        )

        # ... Dispatch Reply ...

        intent = classify_intent(
            normalized["text"]
        )  # Keep intent classification for legacy/telemetry

        # Downgrade intent if locked to property_search and no explicit unit selected
        ai_context = ticket.get("ai_context") or {}
        if (
            ai_context.get("primaryIntentLocked") == "property_search"
            and intent == "RESERVATION"
        ):
            if not _has_unit_selection(normalized["text"]):
                intent = "GENERAL"

        actions.append(f"INTENT_{intent}")

        if intent in ("GREETING", "GENERAL") or (
            decision and intent not in ("RESERVATION", "DOCS")
        ):
            if (ticket.get("status") or "").lower() == "open":
                await store.set_status(ticket_id, "IN_PROGRESS")
                actions.append("STATUS_IN_PROGRESS")

            if _is_duplicate_outbound_text(ticket, reply_text):
                logger.info(
                    "DUPLICATE OUTBOUND ignored ticket=%s provider=%s text=%s",
                    ticket_id,
                    normalized["provider"],
                    _preview_text(reply_text, limit=80),
                )
                actions.append("OUTBOUND_DEDUPED")
                return _finalize(
                    {
                    "ticketId": ticket_id,
                    "actions": actions,
                    "replyText": reply_text,
                    "status": ticket.get("status"),
                    },
                    "outbound_deduped",
                )

            try:
                outbound_started_at = time.perf_counter()
                result = await _send_whatsapp_text_with_context(
                    normalized["provider"],
                    normalized["from"],
                    reply_text,
                    ticket_id=ticket_id,
                    run_id=None,
                    correlation_id=correlation_id,
                )
                timings_ms["outbound_send_ms"] = _duration_ms(outbound_started_at)
            except (MetaWhatsAppSendError, GupshupWhatsAppSendError) as exc:
                actions.append("OUTBOUND_FAILED")
                status_code = getattr(exc, "upstream_status", None) or getattr(
                    exc, "status_code", 500
                )
                err_body = getattr(exc, "upstream_body", None) or getattr(
                    exc, "err", str(exc)
                )
                error_payload = {"status_code": status_code, "err": err_body}
                await _emit_outbound_failed(
                    ticket_id,
                    normalized["provider"],
                    normalized["channel"],
                    normalized["from"],
                    reply_text,
                    error_payload,
                )

                return _finalize(
                    {
                    "ticketId": ticket_id,
                    "actions": actions,
                    "replyText": reply_text,
                    "status": ticket.get("status"),
                    },
                    "outbound_failed",
                )
            if _is_send_error(result):
                actions.append("OUTBOUND_FAILED")
                await store.add_timeline_event(
                    ticket_id,
                    "outbound.failed",
                    {"provider": normalized["provider"], "error": result},
                )
                return _finalize(
                    {
                    "ticketId": ticket_id,
                    "actions": actions,
                    "replyText": reply_text,
                    "status": ticket.get("status"),
                    },
                    "outbound_failed",
                )

            message_id = _extract_message_id(result)
            if not message_id:
                actions.append("OUTBOUND_FAILED")
                await store.add_timeline_event(
                    ticket_id,
                    "outbound.failed",
                    {
                        "provider": normalized["provider"],
                        "error": "missing_message_id",
                        "response": result,
                    },
                )
                return _finalize(
                    {
                    "ticketId": ticket_id,
                    "actions": actions,
                    "replyText": reply_text,
                    "status": ticket.get("status"),
                    },
                    "outbound_failed",
                )

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
            return _finalize(
                {
                "ticketId": ticket_id,
                "actions": actions,
                "replyText": reply_text,
                "status": ticket.get("status"),
                },
                "outbound_sent",
            )

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
                if (
                    ticket.get("status") or ""
                ).upper() == "WAITING_DOCS" and ticket.get("status") != prev_status:
                    actions.append("STATUS_WAITING_DOCS")

            await events.emit_ticket_sla_started(
                ticket_id, "ASSIGNMENT", assignment_due_at
            )
            await events.emit_ticket_sla_started(
                ticket_id, "DOC_VALIDATION", doc_validation_due_at
            )
            actions.append("SLA_STARTED")

            reply_text = _pick_whatsapp_reply_text(
                ai_response_text, _build_docs_reply()
            )
            if _is_duplicate_outbound_text(ticket, reply_text):
                logger.info(
                    "DUPLICATE OUTBOUND ignored ticket=%s provider=%s text=%s",
                    ticket_id,
                    normalized["provider"],
                    _preview_text(reply_text, limit=80),
                )
                actions.append("OUTBOUND_DEDUPED")
                return _finalize(
                    {
                    "ticketId": ticket_id,
                    "actions": actions,
                    "replyText": reply_text,
                    "status": ticket.get("status"),
                    },
                    "outbound_deduped",
                )

            try:
                outbound_started_at = time.perf_counter()
                result = await _send_whatsapp_text_with_context(
                    normalized["provider"],
                    normalized["from"],
                    reply_text,
                    ticket_id=ticket_id,
                    run_id=None,
                    correlation_id=correlation_id,
                )
                timings_ms["outbound_send_ms"] = _duration_ms(outbound_started_at)
            except (MetaWhatsAppSendError, GupshupWhatsAppSendError) as exc:
                actions.append("OUTBOUND_FAILED")
                status_code = getattr(exc, "upstream_status", None) or getattr(
                    exc, "status_code", 500
                )
                err_body = getattr(exc, "upstream_body", None) or getattr(
                    exc, "err", str(exc)
                )
                error_payload = {"status_code": status_code, "err": err_body}
                await _emit_outbound_failed(
                    ticket_id,
                    normalized["provider"],
                    normalized["channel"],
                    normalized["from"],
                    reply_text,
                    error_payload,
                )

                return _finalize(
                    {
                    "ticketId": ticket_id,
                    "actions": actions,
                    "replyText": reply_text,
                    "status": ticket.get("status"),
                    },
                    "outbound_failed",
                )
            if _is_send_error(result):
                actions.append("OUTBOUND_FAILED")
                await store.add_timeline_event(
                    ticket_id,
                    "outbound.failed",
                    {"provider": normalized["provider"], "error": result},
                )
                return _finalize(
                    {
                    "ticketId": ticket_id,
                    "actions": actions,
                    "replyText": reply_text,
                    "status": ticket.get("status"),
                    },
                    "outbound_failed",
                )

            message_id = _extract_message_id(result)
            if not message_id:
                actions.append("OUTBOUND_FAILED")
                await store.add_timeline_event(
                    ticket_id,
                    "outbound.failed",
                    {
                        "provider": normalized["provider"],
                        "error": "missing_message_id",
                        "response": result,
                    },
                )
                return _finalize(
                    {
                    "ticketId": ticket_id,
                    "actions": actions,
                    "replyText": reply_text,
                    "status": ticket.get("status"),
                    },
                    "outbound_failed",
                )

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
            return _finalize(
                {
                "ticketId": ticket_id,
                "actions": actions,
                "replyText": reply_text,
                "status": ticket.get("status"),
                },
                "outbound_sent",
            )

        return _finalize(
            {
            "ticketId": ticket_id,
            "actions": actions,
            "status": ticket.get("status"),
            },
            "accepted_no_outbound",
        )
