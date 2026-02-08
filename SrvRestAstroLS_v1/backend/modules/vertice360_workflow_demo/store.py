from __future__ import annotations

import datetime as dt
import itertools
from typing import Any

from backend.modules.vertice360_workflow_demo import events


_ticket_sequence = itertools.count(1)
tickets: dict[str, dict[str, Any]] = {}
TIMELINE_DEDUPE_WINDOW_MS = 2000


def _epoch_ms() -> int:
    return int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)


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
    commercial = ticket.get("commercial")
    if not isinstance(commercial, dict):
        commercial = {}
        ticket["commercial"] = commercial
    for key in ("zona", "tipologia", "presupuesto", "moneda", "fecha_mudanza"):
        commercial.setdefault(key, None)
    return commercial


def _ensure_ai_context(ticket: dict[str, Any]) -> dict[str, Any]:
    ai_context = ticket.get("ai_context")
    if not isinstance(ai_context, dict):
        ai_context = {}
        ticket["ai_context"] = ai_context
    ai_context.setdefault("primaryIntentLocked", None)
    slots = ai_context.get("commercialSlots")
    if not isinstance(slots, dict):
        slots = {}
        ai_context["commercialSlots"] = slots
    for key in ("zona", "tipologia", "presupuesto", "moneda", "fecha_mudanza"):
        slots.setdefault(key, None)
    return ai_context


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


def _apply_inbound_updates(ticket: dict[str, Any], inbound: dict[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    updates = {
        "provider": inbound.get("provider"),
        "status": inbound.get("status"),
        "channel": inbound.get("channel"),
        "customer": inbound.get("customer"),
        "subject": inbound.get("subject"),
        "assignee": inbound.get("assignee"),
        "requestedDocs": inbound.get("requestedDocs"),
        "sla": inbound.get("sla"),
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
    # Reverse search to find latest
    for ticket in reversed(tickets.values()):
        # Check matching phone
        t_phone = (ticket.get("customer") or {}).get("from")
        if t_phone == phone:
            # Check if active (not closed)
            status = str(ticket.get("status") or "").upper()
            if status != "CLOSED":
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
        if patch:
            _touch(ticket)
            _, appended = _append_timeline_event(ticket, events.TICKET_UPDATED, {"patch": patch})
            if appended:
                await events.emit_ticket_updated(
                    ticket_id,
                    prev_status,
                    next_status,
                    patch,
                    actor="inbound",
                )
        return ticket

    # If no ticketId, accept an active ticket for this user
    phone = inbound.get("from") or (inbound.get("customer") or {}).get("from")
    existing_ticket = _find_active_ticket_by_phone(phone)
    if existing_ticket:
        ticket = existing_ticket
        ticket_id = ticket["ticketId"]
        prev_status = ticket.get("status")
        patch = _apply_inbound_updates(ticket, inbound)
        next_status = ticket.get("status")
        _ensure_commercial(ticket)
        _ensure_ai_context(ticket)
        _ensure_slot_memory(ticket)
        # Even if no structural patch, we might want to log the "re-attach" implicitly
        # by simply returning it. The inbound message will be added by add_message separately.
        if patch:
            _touch(ticket)
            _, appended = _append_timeline_event(ticket, events.TICKET_UPDATED, {"patch": patch})
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
            "fecha_mudanza": None,
        },
        "ai_context": {
            "primaryIntentLocked": None,
            "commercialSlots": {
                "zona": None,
                "tipologia": None,
                "presupuesto": None,
                "moneda": None,
                "fecha_mudanza": None,
            },
        },
        "slot_memory": {
            "zona": None,
            "tipologia": None,
            "presupuesto_amount": None,
            "presupuesto_raw": None,
            "moneda": None,
            "fecha_mudanza": None,
            "budget_ambiguous": False,
            "budget_confirmed": False,
            "confirmed_budget": False,
            "confirmed_currency": False,
            "last_question": None,
            "last_question_key": None,
            "last_asked_slot": None,
            "asked_count": 0,
            "pending_ambiguity": None,
        },
        "pendingAction": None,
        "docsReceivedAt": inbound.get("docsReceivedAt"),
        "createdAt": now_ms,
        "updatedAt": now_ms,
    }
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
        assignment_due_at = ticket["sla"].get("assignmentDueAt") or ticket["sla"].get("dueAt")
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


async def add_timeline_event(ticket_id: str, name: str, value: dict[str, Any] | None = None) -> dict[str, Any]:
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
        for key in ("zona", "tipologia", "presupuesto", "moneda", "fecha_mudanza"):
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


def touch_ticket(ticket_id: str) -> None:
    ticket = tickets.get(ticket_id)
    if not ticket:
        raise KeyError("ticket not found")
    _touch(ticket)


def reset_store() -> None:
    global _ticket_sequence
    tickets.clear()
    _ticket_sequence = itertools.count(1)
