from __future__ import annotations

import datetime as dt
import itertools
from typing import Any

from backend.modules.vertice360_workflow_demo import events


_ticket_sequence = itertools.count(1)
tickets: dict[str, dict[str, Any]] = {}


def _epoch_ms() -> int:
    return int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)


def _normalize_requested_docs(requested_docs: list[str] | None) -> list[str]:
    if not requested_docs:
        return []
    return list(requested_docs)


def _build_timeline_event(name: str, value: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "timestamp": _epoch_ms(),
        "name": name,
        "value": value or {},
    }


def _touch(ticket: dict[str, Any]) -> None:
    ticket["updatedAt"] = _epoch_ms()


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
            timeline_event = _build_timeline_event(events.TICKET_UPDATED, {"patch": patch})
            ticket["timeline"].append(timeline_event)
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
    timeline_event = _build_timeline_event(events.TICKET_CREATED, inbound)
    ticket["timeline"].append(timeline_event)
    tickets[ticket_id] = ticket
    await events.emit_ticket_created(ticket)
    return ticket


async def assign_ticket(ticket_id: str, assignee: Any) -> dict[str, Any]:
    ticket = tickets.get(ticket_id)
    if not ticket:
        raise KeyError("ticket not found")
    ticket["assignee"] = assignee
    _touch(ticket)
    assignment_due_at = None
    if isinstance(ticket.get("sla"), dict):
        assignment_due_at = ticket["sla"].get("assignmentDueAt") or ticket["sla"].get("dueAt")
    timeline_event = _build_timeline_event(
        events.TICKET_ASSIGNED,
        {"assignee": assignee, "dueAt": assignment_due_at},
    )
    ticket["timeline"].append(timeline_event)
    await events.emit_ticket_assigned(ticket_id, assignee, assignment_due_at)
    return ticket


async def set_status(ticket_id: str, status: str) -> dict[str, Any]:
    ticket = tickets.get(ticket_id)
    if not ticket:
        raise KeyError("ticket not found")
    prev_status = ticket.get("status")
    ticket["status"] = status
    _touch(ticket)
    timeline_event = _build_timeline_event(events.TICKET_UPDATED, {"status": status})
    ticket["timeline"].append(timeline_event)
    await events.emit_ticket_updated(
        ticket_id,
        prev_status,
        status,
        {"status": status},
        actor="system",
    )
    return ticket


async def add_timeline_event(ticket_id: str, name: str, value: dict[str, Any] | None = None) -> dict[str, Any]:
    ticket = tickets.get(ticket_id)
    if not ticket:
        raise KeyError("ticket not found")
    timeline_event = _build_timeline_event(name, value)
    ticket["timeline"].append(timeline_event)
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
    timeline_event = _build_timeline_event(events.TICKET_CLOSED, timeline_value)
    ticket["timeline"].append(timeline_event)
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
