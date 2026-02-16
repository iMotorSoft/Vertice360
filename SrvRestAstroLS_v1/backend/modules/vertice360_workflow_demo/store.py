from __future__ import annotations

import datetime as dt
import itertools
import logging
import unicodedata
from typing import Any

from backend.modules.vertice360_workflow_demo import events


_ticket_sequence = itertools.count(1)
tickets: dict[str, dict[str, Any]] = {}
TIMELINE_DEDUPE_WINDOW_MS = 2000
_RESET_COMMANDS = {
    "reiniciar",
    "empezar de nuevo",
    "empezar nuevamente",
    "reset",
    "cancelar",
}

logger = logging.getLogger(__name__)


def _epoch_ms() -> int:
    return int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    stripped = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(stripped.lower().split())


def _preview_text(text: str, limit: int = 30) -> str:
    compact = " ".join(str(text or "").split())
    return compact[:limit]


def _phone_last4(phone: Any) -> str:
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if not digits:
        return "----"
    return digits[-4:]


def is_new_session_trigger(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    return normalized in _RESET_COMMANDS


def _normalize_phone_key(phone: Any) -> str:
    return "".join(ch for ch in str(phone or "") if ch.isdigit())


def _normalize_provider_key(provider: Any) -> str:
    return str(provider or "").strip().lower()


def _normalize_app_key(app: Any, fallback: Any = None) -> str:
    value = str(app or "").strip().lower()
    if value:
        return value
    return str(fallback or "default").strip().lower() or "default"


def _build_conversation_key(
    provider: Any, app: Any, phone: Any, channel: Any = None
) -> str | None:
    provider_key = _normalize_provider_key(provider)
    phone_key = _normalize_phone_key(phone)
    app_key = _normalize_app_key(app, fallback=channel)
    if not provider_key or not phone_key:
        return None
    return f"{provider_key}:{app_key}:{phone_key}"


def _conversation_key_from_ticket(ticket: dict[str, Any]) -> str | None:
    customer = ticket.get("customer") or {}
    return _build_conversation_key(
        ticket.get("provider") or customer.get("provider"),
        ticket.get("app") or customer.get("app"),
        customer.get("from"),
        ticket.get("channel") or customer.get("channel"),
    )


def _conversation_key_from_inbound(inbound: dict[str, Any]) -> str | None:
    customer = inbound.get("customer") or {}
    return _build_conversation_key(
        inbound.get("provider") or customer.get("provider"),
        inbound.get("app") or customer.get("app"),
        inbound.get("from") or customer.get("from"),
        inbound.get("channel") or customer.get("channel"),
    )


def _is_present(value: Any) -> bool:
    return value not in (None, "", "UNKNOWN")


def _has_commercial_data(ticket: dict[str, Any]) -> bool:
    """Check if ticket has commercial data - fecha_mudanza removed (flujo simplificado)."""
    commercial = ticket.get("commercial")
    if isinstance(commercial, dict):
        for key in ("zona", "tipologia", "presupuesto", "moneda"):
            if _is_present(commercial.get(key)):
                return True
    slot_memory = ticket.get("slot_memory")
    if isinstance(slot_memory, dict):
        for key in (
            "zona",
            "tipologia",
            "presupuesto_amount",
            "moneda",
        ):
            if _is_present(slot_memory.get(key)):
                return True
    return False


def _extract_inbound_text(inbound: dict[str, Any]) -> str:
    text = inbound.get("text")
    if text is not None:
        return str(text)
    subject = inbound.get("subject")
    if subject is not None:
        return str(subject)
    return ""


def _is_inbound_seed(inbound: dict[str, Any]) -> bool:
    return "text" in inbound or "timestamp" in inbound


def _refresh_last_inbound(ticket: dict[str, Any], inbound: dict[str, Any]) -> None:
    if not _is_inbound_seed(inbound):
        return
    now_ms = _epoch_ms()
    if ticket.get("lastInboundAt") != now_ms:
        ticket["lastInboundAt"] = now_ms
        _touch(ticket)


def _should_start_new_session(
    existing_ticket: dict[str, Any],
    inbound: dict[str, Any],
) -> tuple[bool, str | None, bool, bool, bool]:
    _ = existing_ticket  # reserved for future policy
    has_commercial_data = _has_commercial_data(existing_ticket)
    explicit_reset = is_new_session_trigger(_extract_inbound_text(inbound))
    if explicit_reset:
        return True, "explicit_reset", explicit_reset, has_commercial_data, False
    return False, None, explicit_reset, has_commercial_data, False


def _normalize_requested_docs(requested_docs: list[str] | None) -> list[str]:
    if not requested_docs:
        return []
    return list(requested_docs)


def _build_timeline_event(
    name: str,
    value: dict[str, Any] | None,
    timestamp_ms: int | None = None,
) -> dict[str, Any]:
    return {
        "timestamp": _epoch_ms() if timestamp_ms is None else timestamp_ms,
        "name": name,
        "value": value or {},
    }


def _touch(ticket: dict[str, Any]) -> None:
    ticket["updatedAt"] = _epoch_ms()


def _ensure_commercial(ticket: dict[str, Any]) -> dict[str, Any]:
    """Ensure commercial fields exist - fecha_mudanza removed (flujo simplificado)."""
    commercial = ticket.get("commercial")
    if not isinstance(commercial, dict):
        commercial = {}
        ticket["commercial"] = commercial
    for key in ("zona", "tipologia", "presupuesto", "moneda"):
        commercial.setdefault(key, None)
    return commercial


def _ensure_ai_context(ticket: dict[str, Any]) -> dict[str, Any]:
    """Ensure AI context exists - fecha_mudanza removed (flujo simplificado)."""
    ai_context = ticket.get("ai_context")
    if not isinstance(ai_context, dict):
        ai_context = {}
        ticket["ai_context"] = ai_context
    ai_context.setdefault("primaryIntentLocked", None)
    slots = ai_context.get("commercialSlots")
    if not isinstance(slots, dict):
        slots = {}
        ai_context["commercialSlots"] = slots
    for key in ("zona", "tipologia", "presupuesto", "moneda"):
        slots.setdefault(key, None)
    return ai_context


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
    return slot_memory


def _ensure_handoff_state(ticket: dict[str, Any]) -> None:
    ticket.setdefault("handoffRequired", False)
    ticket.setdefault("handoffStage", None)
    ticket.setdefault("lastOperatorName", None)
    ticket.setdefault("pendingAction", None)


def _ensure_flow_stage(ticket: dict[str, Any]) -> str:
    stage = str(ticket.get("flowStage") or "").strip().lower()
    if stage in {"collecting_profile", "handoff_scheduling", "operator_engaged"}:
        return stage
    handoff_stage = str(ticket.get("handoffStage") or "").strip().lower()
    if handoff_stage == "operator_engaged":
        stage = "operator_engaged"
    elif bool(ticket.get("handoffRequired")):
        stage = "handoff_scheduling"
    else:
        stage = "collecting_profile"
    ticket["flowStage"] = stage
    return stage


def _is_duplicate_timeline_event(
    last_event: dict[str, Any] | None,
    name: str,
    value: dict[str, Any] | None,
    now_ms: int,
) -> bool:
    if not last_event:
        return False
    if last_event.get("name") != name:
        return False
    if (last_event.get("value") or {}) != (value or {}):
        return False
    last_ts = last_event.get("timestamp")
    if not isinstance(last_ts, int):
        return False
    return now_ms - last_ts <= TIMELINE_DEDUPE_WINDOW_MS


def _append_timeline_event(
    ticket: dict[str, Any],
    name: str,
    value: dict[str, Any] | None,
) -> tuple[dict[str, Any], bool]:
    timeline = ticket.setdefault("timeline", [])
    now_ms = _epoch_ms()
    last_event = timeline[-1] if timeline else None
    if _is_duplicate_timeline_event(last_event, name, value, now_ms):
        return last_event, False
    timeline_event = _build_timeline_event(name, value, now_ms)
    timeline.append(timeline_event)
    return timeline_event, True


def generate_ticket_id() -> str:
    return f"VTX-{next(_ticket_sequence):04d}"


def _reserve_ticket_id() -> str:
    ticket_id = generate_ticket_id()
    while ticket_id in tickets:
        ticket_id = generate_ticket_id()
    return ticket_id


def _apply_inbound_updates(
    ticket: dict[str, Any], inbound: dict[str, Any]
) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    conversation_key = _conversation_key_from_inbound(inbound)
    updates = {
        "provider": inbound.get("provider"),
        "app": inbound.get("app"),
        "status": inbound.get("status"),
        "channel": inbound.get("channel"),
        "customer": inbound.get("customer"),
        "subject": inbound.get("subject"),
        "assignee": inbound.get("assignee"),
        "requestedDocs": inbound.get("requestedDocs"),
        "sla": inbound.get("sla"),
        "conversationKey": conversation_key,
    }

    for key, value in updates.items():
        if value is None:
            continue
        if key == "requestedDocs":
            value = _normalize_requested_docs(value)
        if ticket.get(key) != value:
            ticket[key] = value
            patch[key] = value

    return patch


def _find_active_ticket_by_phone(phone: str) -> dict[str, Any] | None:
    if not phone:
        return None
    phone_key = _normalize_phone_key(phone)
    if not phone_key:
        return None
    # Reverse search to find latest
    for ticket in reversed(tickets.values()):
        # Check matching phone
        t_phone = _normalize_phone_key((ticket.get("customer") or {}).get("from"))
        if t_phone == phone_key:
            # Check if active (not closed)
            status = str(ticket.get("status") or "").upper()
            if status != "CLOSED":
                return ticket
    return None


def _find_active_ticket_by_conversation_key(
    conversation_key: str | None,
) -> dict[str, Any] | None:
    if not conversation_key:
        return None
    for ticket in reversed(tickets.values()):
        status = str(ticket.get("status") or "").upper()
        if status == "CLOSED":
            continue
        ticket_key = str(ticket.get("conversationKey") or "").strip().lower()
        if not ticket_key:
            ticket_key = (
                str(_conversation_key_from_ticket(ticket) or "").strip().lower()
            )
        if ticket_key and ticket_key == conversation_key:
            return ticket
    return None


async def create_or_get_ticket_from_inbound(inbound: dict[str, Any]) -> dict[str, Any]:
    raw_ticket_id = inbound.get("ticketId")
    ticket_id = str(raw_ticket_id).strip() if raw_ticket_id is not None else ""

    # If explicit ticketId provided, lookup directly
    if ticket_id and ticket_id in tickets:
        ticket = tickets[ticket_id]
        prev_status = ticket.get("status")
        patch = _apply_inbound_updates(ticket, inbound)
        next_status = ticket.get("status")
        _ensure_commercial(ticket)
        _ensure_ai_context(ticket)
        _ensure_slot_memory(ticket)
        _ensure_handoff_state(ticket)
        _ensure_flow_stage(ticket)
        _refresh_last_inbound(ticket, inbound)
        if patch:
            _touch(ticket)
            _, appended = _append_timeline_event(
                ticket, events.TICKET_UPDATED, {"patch": patch}
            )
            if appended:
                await events.emit_ticket_updated(
                    ticket_id,
                    prev_status,
                    next_status,
                    patch,
                    actor="inbound",
                )
        return ticket

    # If no ticketId, accept an active ticket for this user conversation key.
    phone = inbound.get("from") or (inbound.get("customer") or {}).get("from")
    conversation_key = _conversation_key_from_inbound(inbound)
    existing_ticket = _find_active_ticket_by_conversation_key(
        conversation_key
    ) or _find_active_ticket_by_phone(phone)
    if existing_ticket:
        _ensure_commercial(existing_ticket)
        _ensure_slot_memory(existing_ticket)
        _ensure_handoff_state(existing_ticket)
        _ensure_flow_stage(existing_ticket)
        raw_text = _extract_inbound_text(inbound)
        normalized_text = _normalize_text(raw_text)
        should_reset, reason, trigger, has_data, ttl_expired = (
            _should_start_new_session(existing_ticket, inbound)
        )
        logger.debug(
            'SESSION_DECISION from=%s raw_text="%s" norm="%s" trigger=%s has_data=%s ttl_expired=%s action=%s prev_ticket=%s',
            _phone_last4(phone),
            _preview_text(raw_text),
            _preview_text(normalized_text),
            int(trigger),
            int(has_data),
            int(ttl_expired),
            "new" if should_reset else "reuse",
            existing_ticket.get("ticketId") or "-",
        )
        if should_reset:
            logger.info(
                "NEW_SESSION ticket_reset reason=%s trigger=%s has_data=%s prev_ticket=%s",
                reason,
                trigger,
                has_data,
                existing_ticket.get("ticketId"),
            )
        else:
            ticket = existing_ticket
            ticket_id = ticket["ticketId"]
            prev_status = ticket.get("status")
            patch = _apply_inbound_updates(ticket, inbound)
            next_status = ticket.get("status")
            _ensure_commercial(ticket)
            _ensure_ai_context(ticket)
            _ensure_slot_memory(ticket)
            _ensure_handoff_state(ticket)
            _ensure_flow_stage(ticket)
            _refresh_last_inbound(ticket, inbound)
            # Even if no structural patch, we might want to log the "re-attach" implicitly
            # by simply returning it. The inbound message will be added by add_message separately.
            if patch:
                _touch(ticket)
                _, appended = _append_timeline_event(
                    ticket, events.TICKET_UPDATED, {"patch": patch}
                )
                if appended:
                    await events.emit_ticket_updated(
                        ticket_id,
                        prev_status,
                        next_status,
                        patch,
                        actor="inbound",
                    )
            return ticket

    # Create new if none found
    if not ticket_id:
        ticket_id = _reserve_ticket_id()
    now_ms = _epoch_ms()
    ticket = {
        "ticketId": ticket_id,
        "status": inbound.get("status", "OPEN"),
        "provider": inbound.get("provider"),
        "app": inbound.get("app"),
        "channel": inbound.get("channel"),
        "customer": inbound.get("customer"),
        "subject": inbound.get("subject"),
        "assignee": inbound.get("assignee"),
        "requestedDocs": _normalize_requested_docs(inbound.get("requestedDocs")),
        "sla": inbound.get("sla"),
        "timeline": [],
        "messages": [],
        "commercial": {
            "zona": None,
            "tipologia": None,
            "presupuesto": None,
            "moneda": None,
            # Note: fecha_mudanza removed (flujo simplificado)
        },
        "ai_context": {
            "primaryIntentLocked": None,
            "commercialSlots": {
                "zona": None,
                "tipologia": None,
                "presupuesto": None,
                "moneda": None,
                # Note: fecha_mudanza removed (flujo simplificado)
            },
        },
        "slot_memory": {
            "zona": None,
            "tipologia": None,
            "presupuesto_amount": None,
            "presupuesto_raw": None,
            "moneda": None,
            # Note: fecha_mudanza removed - flow goes directly to handoff after presupuesto
            "budget_ambiguous": False,
            "budget_confirmed": False,
            "confirmed_budget": False,
            "confirmed_currency": False,
            "last_question": None,
            "last_question_key": None,
            "last_asked_slot": None,
            "asked_count": 0,
            "pending_ambiguity": None,
            "answered_fields": [],
            "summarySent": False,
            "intro_sent": False,
            "visit_slot": None,
            "handoff_completed": False,  # New flag to track handoff state
        },
        "handoffRequired": False,
        "handoffStage": None,
        "flowStage": "collecting_profile",
        "lastOperatorName": None,
        "pendingAction": None,
        "conversationKey": conversation_key,
        "docsReceivedAt": inbound.get("docsReceivedAt"),
        "lastInboundAt": None,
        "createdAt": now_ms,
        "updatedAt": now_ms,
    }
    _ensure_flow_stage(ticket)
    _refresh_last_inbound(ticket, inbound)
    logger.debug(
        "TICKET_INIT ticket_id=%s from=%s commercial_snapshot=%s answered_fields=%s handoff=%s",
        ticket_id,
        _phone_last4((ticket.get("customer") or {}).get("from")),
        {
            "zona": (ticket.get("commercial") or {}).get("zona"),
            "ambientes": (ticket.get("commercial") or {}).get("tipologia"),
            "presupuesto": (ticket.get("commercial") or {}).get("presupuesto"),
            "moneda": (ticket.get("commercial") or {}).get("moneda"),
            # Note: mudanza/fecha_mudanza removed (flujo simplificado)
        },
        (ticket.get("slot_memory") or {}).get("answered_fields") or [],
        {
            "required": bool(ticket.get("handoffRequired")),
            "stage": ticket.get("handoffStage"),
        },
    )
    _append_timeline_event(ticket, events.TICKET_CREATED, inbound)
    tickets[ticket_id] = ticket
    await events.emit_ticket_created(ticket)
    return ticket


async def assign_ticket(ticket_id: str, assignee: Any) -> dict[str, Any]:
    ticket = tickets.get(ticket_id)
    if not ticket:
        raise KeyError("ticket not found")
    if ticket.get("assignee") == assignee:
        return ticket
    ticket["assignee"] = assignee
    _touch(ticket)
    assignment_due_at = None
    if isinstance(ticket.get("sla"), dict):
        assignment_due_at = ticket["sla"].get("assignmentDueAt") or ticket["sla"].get(
            "dueAt"
        )
    _, appended = _append_timeline_event(
        ticket,
        events.TICKET_ASSIGNED,
        {"assignee": assignee, "dueAt": assignment_due_at},
    )
    if appended:
        await events.emit_ticket_assigned(ticket_id, assignee, assignment_due_at)
    return ticket


async def set_status(
    ticket_id: str,
    status: str,
    actor: str | None = "system",
    patch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ticket = tickets.get(ticket_id)
    if not ticket:
        raise KeyError("ticket not found")
    prev_status = ticket.get("status")
    patch_payload: dict[str, Any] = {}
    changed = False

    if patch:
        for key, value in patch.items():
            if key == "status":
                continue
            if key == "requestedDocs":
                value = _normalize_requested_docs(value)
            if key == "sla" and isinstance(value, dict):
                current = ticket.get("sla") or {}
                merged = {**current, **value}
                if merged != current:
                    ticket["sla"] = merged
                    patch_payload["sla"] = value
                    changed = True
                continue
            if ticket.get(key) != value:
                ticket[key] = value
                patch_payload[key] = value
                changed = True

    status_changed = prev_status != status
    blocked_transition = prev_status == "ESCALATED" and status == "WAITING_DOCS"
    if status_changed and not blocked_transition:
        ticket["status"] = status
        patch_payload["status"] = status
        changed = True

    if not changed:
        return ticket

    _touch(ticket)
    _, appended = _append_timeline_event(
        ticket,
        events.TICKET_UPDATED,
        {"patch": patch_payload},
    )
    if appended:
        await events.emit_ticket_updated(
            ticket_id,
            prev_status,
            ticket.get("status"),
            patch_payload,
            actor=actor,
        )
    return ticket


async def add_timeline_event(
    ticket_id: str, name: str, value: dict[str, Any] | None = None
) -> dict[str, Any]:
    ticket = tickets.get(ticket_id)
    if not ticket:
        raise KeyError("ticket not found")
    timeline_event, appended = _append_timeline_event(ticket, name, value)
    if appended:
        _touch(ticket)
        await events.emit_event(name, ticket_id, {"timeline": timeline_event})
    return timeline_event


async def close_ticket(ticket_id: str, reason: str | None = None) -> dict[str, Any]:
    ticket = tickets.get(ticket_id)
    if not ticket:
        raise KeyError("ticket not found")
    ticket["status"] = "CLOSED"
    _touch(ticket)
    timeline_value = {"reason": reason} if reason else {}
    _, appended = _append_timeline_event(ticket, events.TICKET_CLOSED, timeline_value)
    if appended:
        await events.emit_ticket_closed(ticket_id, reason)
    return ticket


def add_message(ticket_id: str, message: dict[str, Any]) -> None:
    ticket = tickets.get(ticket_id)
    if not ticket:
        raise KeyError("ticket not found")
    ticket.setdefault("messages", []).append(message)
    ticket["lastMessageText"] = message.get("text")
    ticket["lastMessageAt"] = message.get("at")
    _touch(ticket)


def update_ticket_commercial(ticket_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    ticket = tickets.get(ticket_id)
    if not ticket:
        raise KeyError("ticket not found")
    commercial = _ensure_commercial(ticket)
    ai_context = _ensure_ai_context(ticket)
    changed = False
    for key, value in patch.items():
        if value is None:
            continue
        if commercial.get(key) != value:
            commercial[key] = value
            changed = True
    slots = ai_context.get("commercialSlots")
    if isinstance(slots, dict):
        for key in ("zona", "tipologia", "presupuesto", "moneda"):
            slots[key] = commercial.get(key)
    if changed:
        _touch(ticket)
    return commercial


def set_pending_action(ticket_id: str, action: str | None) -> None:
    ticket = tickets.get(ticket_id)
    if not ticket:
        raise KeyError("ticket not found")
    if ticket.get("pendingAction") != action:
        ticket["pendingAction"] = action
        _touch(ticket)


def set_handoff_required(
    ticket_id: str, required: bool, action: str | None = "schedule_visit"
) -> None:
    ticket = tickets.get(ticket_id)
    if not ticket:
        raise KeyError("ticket not found")
    required_bool = bool(required)
    changed = False
    if ticket.get("handoffRequired") != required_bool:
        ticket["handoffRequired"] = required_bool
        changed = True
    target_stage = "required" if required_bool else None
    if ticket.get("handoffStage") != target_stage:
        ticket["handoffStage"] = target_stage
        changed = True
    target_action = action if required_bool else None
    if ticket.get("pendingAction") != target_action:
        ticket["pendingAction"] = target_action
        changed = True
    if changed:
        _touch(ticket)


def set_handoff_stage(
    ticket_id: str, stage: str | None, operator_name: str | None = None
) -> None:
    ticket = tickets.get(ticket_id)
    if not ticket:
        raise KeyError("ticket not found")
    normalized_stage = str(stage).strip().lower() if stage is not None else None
    if normalized_stage not in (None, "", "required", "operator_engaged"):
        raise ValueError("invalid handoff stage")
    if normalized_stage == "":
        normalized_stage = None

    changed = False
    if ticket.get("handoffStage") != normalized_stage:
        ticket["handoffStage"] = normalized_stage
        changed = True

    if normalized_stage in {"required", "operator_engaged"}:
        if ticket.get("handoffRequired") is not True:
            ticket["handoffRequired"] = True
            changed = True
    else:
        if ticket.get("handoffRequired") is not False:
            ticket["handoffRequired"] = False
            changed = True
        if ticket.get("pendingAction") is not None:
            ticket["pendingAction"] = None
            changed = True

    clean_operator = str(operator_name).strip() if operator_name is not None else None
    if clean_operator == "":
        clean_operator = None
    if clean_operator is not None and ticket.get("lastOperatorName") != clean_operator:
        ticket["lastOperatorName"] = clean_operator
        changed = True

    if changed:
        _touch(ticket)


def touch_ticket(ticket_id: str) -> None:
    ticket = tickets.get(ticket_id)
    if not ticket:
        raise KeyError("ticket not found")
    _touch(ticket)


def reset_store() -> None:
    global _ticket_sequence
    tickets.clear()
    _ticket_sequence = itertools.count(1)
