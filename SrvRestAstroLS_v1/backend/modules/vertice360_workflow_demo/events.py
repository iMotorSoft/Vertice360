"""AG-UI CustomEvent helpers for workflow demo.

Regla clave: para cualquier evento ticket.* o messaging.*, el correlationId SIEMPRE es ticketId,
y value.ticketId SIEMPRE debe existir.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from backend.modules.agui_stream import broadcaster


TICKET_CREATED = "ticket.created"
TICKET_UPDATED = "ticket.updated"
TICKET_ASSIGNED = "ticket.assigned"
TICKET_SLA_STARTED = "ticket.sla.started"
TICKET_SLA_BREACHED = "ticket.sla.breached"
TICKET_ESCALATED = "ticket.escalated"
TICKET_CLOSED = "ticket.closed"
TICKET_SURVEY_SENT = "ticket.survey.sent"
TICKET_SURVEY_RECEIVED = "ticket.survey.received"
MESSAGING_INBOUND = "messaging.inbound"
MESSAGING_OUTBOUND = "messaging.outbound"
MESSAGING_DELIVERY = "messaging.delivery"


def _epoch_ms() -> int:
    return int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)


def _normalize_ticket_id(ticket_id: str) -> str:
    ticket_id = str(ticket_id or "").strip()
    if not ticket_id:
        raise ValueError("ticketId is required")
    return ticket_id


def _coerce_epoch_ms(value: int | float | str | None, default: int | None = None) -> int:
    if value is None:
        if default is None:
            raise ValueError("timestamp is required")
        return default
    if isinstance(value, bool):
        raise ValueError("timestamp must be epoch ms int")
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    raise ValueError("timestamp must be epoch ms int")


async def emit_event(name: str, ticket_id: str, value: dict[str, Any]) -> None:
    ticket_id = _normalize_ticket_id(ticket_id)
    if value is None:
        value = {}
    if "ticketId" not in value:
        value["ticketId"] = ticket_id

    payload = {
        "type": "CUSTOM",
        "timestamp": _epoch_ms(),
        "name": name,
        "value": value,
        "correlationId": ticket_id,
    }
    await broadcaster.publish(name, payload)


async def emit_ticket_created(ticket: dict[str, Any]) -> None:
    ticket_id = _normalize_ticket_id(ticket.get("ticketId"))
    await emit_event(TICKET_CREATED, ticket_id, {"ticketId": ticket_id, "ticket": ticket})


async def emit_ticket_updated(
    ticket_id: str,
    prev_status: str | None,
    next_status: str | None,
    patch: dict[str, Any] | None,
    actor: str | None,
) -> None:
    value = {
        "prev": {"status": prev_status or "unknown"},
        "next": {"status": next_status or "unknown"},
        "patch": patch or {},
        "actor": actor,
    }
    await emit_event(TICKET_UPDATED, ticket_id, value)


async def emit_ticket_assigned(
    ticket_id: str,
    assignee: Any,
    dueAt: int | float | str | None,
) -> None:
    assignment_due_at = _coerce_epoch_ms(dueAt, _epoch_ms())
    value = {
        "assignee": assignee,
        "dueAt": assignment_due_at,
        "sla": {"assignmentDueAt": assignment_due_at},
    }
    await emit_event(TICKET_ASSIGNED, ticket_id, value)


async def emit_ticket_sla_started(ticket_id: str, slaType: str, dueAt: int | float | str | None) -> None:
    due_at = _coerce_epoch_ms(dueAt, _epoch_ms())
    value = {"slaType": slaType, "dueAt": due_at}
    await emit_event(TICKET_SLA_STARTED, ticket_id, value)


async def emit_ticket_sla_breached(
    ticket_id: str,
    slaType: str,
    dueAt: int | float | str | None,
    breachedAt: int | float | str | None,
) -> None:
    due_at = _coerce_epoch_ms(dueAt, _epoch_ms())
    breached_at = _coerce_epoch_ms(breachedAt, _epoch_ms())
    value = {"slaType": slaType, "dueAt": due_at, "breachedAt": breached_at}
    await emit_event(TICKET_SLA_BREACHED, ticket_id, value)


async def emit_ticket_escalated(ticket_id: str, reason: str, to_team: str) -> None:
    value = {"reason": reason, "toTeam": to_team}
    await emit_event(TICKET_ESCALATED, ticket_id, value)


async def emit_ticket_closed(ticket_id: str, resolution: str | None) -> None:
    value = {"resolution": resolution}
    await emit_event(TICKET_CLOSED, ticket_id, value)


async def emit_ticket_survey_sent(ticket_id: str, surveyId: str, channelUsed: str) -> None:
    value = {"surveyId": surveyId, "channelUsed": channelUsed, "sentAt": _epoch_ms()}
    await emit_event(TICKET_SURVEY_SENT, ticket_id, value)


async def emit_ticket_survey_received(
    ticket_id: str,
    surveyId: str,
    score: int | float,
    text: str | None = None,
) -> None:
    value = {"surveyId": surveyId, "score": score, "text": text, "receivedAt": _epoch_ms()}
    await emit_event(TICKET_SURVEY_RECEIVED, ticket_id, value)


async def emit_messaging_inbound(
    ticket_id: str,
    provider: str,
    channel: str,
    messageId: str,
    from_: str,
    to: str,
    text: str,
    mediaCount: int = 0,
    receivedAt: int | float | str | None = None,
) -> None:
    if not messageId:
        raise ValueError("messageId is required for messaging.inbound")
    received_at = _coerce_epoch_ms(receivedAt, _epoch_ms())
    value = {
        "provider": provider,
        "channel": channel,
        "messageId": messageId,
        "from": from_,
        "to": to,
        "text": text,
        "mediaCount": mediaCount,
        "receivedAt": received_at,
    }
    await emit_event(MESSAGING_INBOUND, ticket_id, value)


async def emit_messaging_outbound(
    ticket_id: str,
    provider: str,
    channel: str,
    messageId: str,
    to: str,
    text: str,
    sentAt: int | float | str | None = None,
) -> None:
    if not messageId:
        raise ValueError("messageId is required for messaging.outbound")
    sent_at = _coerce_epoch_ms(sentAt, _epoch_ms())
    value = {
        "provider": provider,
        "channel": channel,
        "messageId": messageId,
        "to": to,
        "text": text,
        "sentAt": sent_at,
    }
    await emit_event(MESSAGING_OUTBOUND, ticket_id, value)


async def emit_messaging_delivery(
    ticket_id: str,
    provider: str,
    messageId: str,
    status: str,
    at: int | float | str | None = None,
) -> None:
    if not messageId:
        raise ValueError("messageId is required for messaging.delivery")
    delivered_at = _coerce_epoch_ms(at, _epoch_ms())
    value = {
        "provider": provider,
        "messageId": messageId,
        "status": status,
        "at": delivered_at,
    }
    await emit_event(MESSAGING_DELIVERY, ticket_id, value)
