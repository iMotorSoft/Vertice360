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


async def create_or_get_ticket_from_inbound(inbound: dict[str, Any]) -> dict[str, Any]:
    raw_ticket_id = inbound.get("ticketId")
    ticket_id = str(raw_ticket_id).strip() if raw_ticket_id is not None else ""
    if ticket_id in tickets:
        ticket = tickets[ticket_id]
        prev_status = ticket.get("status")
        patch = _apply_inbound_updates(ticket, inbound)
        next_status = ticket.get("status")
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


def touch_ticket(ticket_id: str) -> None:
    ticket = tickets.get(ticket_id)
    if not ticket:
        raise KeyError("ticket not found")
    _touch(ticket)


def reset_store() -> None:
    global _ticket_sequence
    tickets.clear()
    _ticket_sequence = itertools.count(1)
