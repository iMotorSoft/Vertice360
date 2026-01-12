from __future__ import annotations

import time
from typing import Any

from litestar import Controller, Router, get, post
from litestar.exceptions import HTTPException

from backend.modules.agui_stream import broadcaster
from backend.modules.vertice360_workflow_demo import events, store


ALLOWED_STATUSES = {"OPEN", "IN_PROGRESS", "WAITING_DOCS", "ESCALATED", "CLOSED"}
ALLOWED_DOC_ACTIONS = {"REQUEST", "RECEIVE", "CLEAR"}
ALLOWED_SLA_TYPES = {"ASSIGNMENT", "DOC_VALIDATION"}


def _epoch_ms() -> int:
    return int(time.time() * 1000)


def _ensure_payload_keys(payload: dict[str, Any], required: list[str]) -> None:
    missing = [key for key in required if not payload.get(key)]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing fields: {', '.join(missing)}")


def _get_ticket_or_404(ticket_id: str) -> dict[str, Any]:
    ticket = store.tickets.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


def _sla_summary(sla: dict[str, Any] | None) -> dict[str, Any]:
    data = sla or {}
    return {
        "assignmentDueAt": data.get("assignmentDueAt"),
        "assignmentBreachedAt": data.get("assignmentBreachedAt"),
        "docValidationDueAt": data.get("docValidationDueAt"),
        "docValidationBreachedAt": data.get("docValidationBreachedAt"),
    }


def _customer_summary(customer: dict[str, Any] | None) -> dict[str, Any]:
    data = customer or {}
    return {
        "from": data.get("from"),
        "displayName": data.get("displayName") or data.get("name"),
    }


def _ticket_provider(ticket: dict[str, Any]) -> str | None:
    provider = ticket.get("provider")
    if provider:
        return provider
    customer = ticket.get("customer") or {}
    return customer.get("provider")


def _ticket_summary(ticket: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticketId": ticket.get("ticketId"),
        "status": ticket.get("status"),
        "channel": ticket.get("channel"),
        "provider": _ticket_provider(ticket),
        "customer": _customer_summary(ticket.get("customer")),
        "subject": ticket.get("subject"),
        "assignee": ticket.get("assignee"),
        "lastMessageText": ticket.get("lastMessageText"),
        "lastMessageAt": ticket.get("lastMessageAt"),
        "sla": _sla_summary(ticket.get("sla")),
        "createdAt": ticket.get("createdAt"),
        "updatedAt": ticket.get("updatedAt"),
    }


def _ticket_detail(ticket: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticketId": ticket.get("ticketId"),
        "status": ticket.get("status"),
        "channel": ticket.get("channel"),
        "provider": _ticket_provider(ticket),
        "customer": ticket.get("customer"),
        "subject": ticket.get("subject"),
        "assignee": ticket.get("assignee"),
        "requestedDocs": ticket.get("requestedDocs") or [],
        "docsReceivedAt": ticket.get("docsReceivedAt"),
        "sla": _sla_summary(ticket.get("sla")),
        "messages": ticket.get("messages") or [],
        "timeline": ticket.get("timeline") or [],
        "createdAt": ticket.get("createdAt"),
        "updatedAt": ticket.get("updatedAt"),
    }


def _append_timeline_event(ticket: dict[str, Any], name: str, value: dict[str, Any]) -> None:
    ticket.setdefault("timeline", []).append(
        {
            "name": name,
            "timestamp": _epoch_ms(),
            "value": value,
        }
    )


class WorkflowTicketsController(Controller):
    path = "/tickets"

    @get("")
    async def list_tickets(self) -> list[dict[str, Any]]:
        items = sorted(
            store.tickets.values(),
            key=lambda ticket: ticket.get("updatedAt") or 0,
            reverse=True,
        )
        return [_ticket_summary(ticket) for ticket in items]

    @get("/{ticket_id:str}")
    async def ticket_detail(self, ticket_id: str) -> dict[str, Any]:
        ticket = _get_ticket_or_404(ticket_id)
        return _ticket_detail(ticket)

    @post("/{ticket_id:str}/assign")
    async def assign_ticket(self, ticket_id: str, data: dict[str, Any]) -> dict[str, Any]:
        _ensure_payload_keys(data, ["team", "name"])
        ticket = _get_ticket_or_404(ticket_id)
        await store.assign_ticket(ticket_id, {"team": data["team"], "name": data["name"]})
        if (ticket.get("status") or "").upper() == "OPEN":
            await store.set_status(ticket_id, "IN_PROGRESS")
        return _ticket_detail(ticket)

    @post("/{ticket_id:str}/status")
    async def update_status(self, ticket_id: str, data: dict[str, Any]) -> dict[str, Any]:
        _ensure_payload_keys(data, ["status"])
        status = str(data["status"]).upper()
        if status not in ALLOWED_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status")
        ticket = _get_ticket_or_404(ticket_id)
        await store.set_status(ticket_id, status)
        return _ticket_detail(ticket)

    @post("/{ticket_id:str}/docs")
    async def update_docs(self, ticket_id: str, data: dict[str, Any]) -> dict[str, Any]:
        _ensure_payload_keys(data, ["action"])
        action = str(data["action"]).upper()
        if action not in ALLOWED_DOC_ACTIONS:
            raise HTTPException(status_code=400, detail="Invalid docs action")

        ticket = _get_ticket_or_404(ticket_id)
        prev_status = ticket.get("status")
        patch: dict[str, Any] = {}

        if action == "REQUEST":
            requested = data.get("requestedDocs") or []
            if not isinstance(requested, list) or not requested:
                raise HTTPException(status_code=400, detail="requestedDocs must be a non-empty list")
            ticket["requestedDocs"] = list(requested)
            ticket["docsReceivedAt"] = None
            patch["requestedDocs"] = ticket["requestedDocs"]
            patch["docsReceivedAt"] = None
            ticket["status"] = "WAITING_DOCS"
            patch["status"] = ticket["status"]

        if action == "RECEIVE":
            received_at = _epoch_ms()
            ticket["docsReceivedAt"] = received_at
            patch["docsReceivedAt"] = received_at
            if (ticket.get("status") or "").upper() == "WAITING_DOCS":
                ticket["status"] = "IN_PROGRESS"
                patch["status"] = ticket["status"]

        if action == "CLEAR":
            ticket["requestedDocs"] = []
            ticket["docsReceivedAt"] = None
            patch["requestedDocs"] = []
            patch["docsReceivedAt"] = None

        store.touch_ticket(ticket_id)
        _append_timeline_event(ticket, events.TICKET_UPDATED, {"patch": patch})
        await events.emit_ticket_updated(
            ticket_id,
            prev_status,
            ticket.get("status"),
            patch,
            actor="agent",
        )
        return _ticket_detail(ticket)

    @post("/{ticket_id:str}/close")
    async def close_ticket(self, ticket_id: str, data: dict[str, Any]) -> dict[str, Any]:
        _ensure_payload_keys(data, ["resolutionCode"])
        ticket = _get_ticket_or_404(ticket_id)
        await store.close_ticket(ticket_id, data["resolutionCode"])
        return _ticket_detail(ticket)

    @post("/{ticket_id:str}/escalate")
    async def escalate_ticket(self, ticket_id: str, data: dict[str, Any]) -> dict[str, Any]:
        _ensure_payload_keys(data, ["reason", "toTeam"])
        ticket = _get_ticket_or_404(ticket_id)
        prev_status = ticket.get("status")
        ticket["status"] = "ESCALATED"
        store.touch_ticket(ticket_id)
        patch = {"status": ticket["status"]}
        _append_timeline_event(ticket, events.TICKET_UPDATED, {"patch": patch})
        await events.emit_ticket_updated(ticket_id, prev_status, ticket["status"], patch, actor="agent")
        await events.emit_ticket_escalated(ticket_id, data["reason"], data["toTeam"])
        return _ticket_detail(ticket)

    @post("/{ticket_id:str}/simulate-breach")
    async def simulate_breach(self, ticket_id: str, data: dict[str, Any]) -> dict[str, Any]:
        _ensure_payload_keys(data, ["slaType"])
        sla_type = str(data["slaType"]).upper()
        if sla_type not in ALLOWED_SLA_TYPES:
            raise HTTPException(status_code=400, detail="Invalid slaType")

        ticket = _get_ticket_or_404(ticket_id)
        prev_status = ticket.get("status")
        
        sla = ticket.get("sla")
        if sla is None:
            sla = {}
            ticket["sla"] = sla
            
        now_ms = _epoch_ms()
        patch: dict[str, Any] = {}

        if sla_type == "ASSIGNMENT":
            sla["assignmentBreachedAt"] = now_ms
            patch["sla"] = {"assignmentBreachedAt": now_ms}
            due_at = sla.get("assignmentDueAt")
        else:
            sla["docValidationBreachedAt"] = now_ms
            patch["sla"] = {"docValidationBreachedAt": now_ms}
            due_at = sla.get("docValidationDueAt")

        ticket["status"] = "ESCALATED"
        patch["status"] = ticket["status"]
        store.touch_ticket(ticket_id)
        _append_timeline_event(ticket, events.TICKET_UPDATED, {"patch": patch})

        await events.emit_ticket_sla_breached(ticket_id, sla_type, due_at, now_ms)
        await events.emit_ticket_escalated(ticket_id, "SLA_BREACH", "SUPERVISOR")
        await events.emit_ticket_updated(ticket_id, prev_status, ticket["status"], patch, actor="system")
        return _ticket_detail(ticket)


@post("/reset")
async def reset_demo() -> dict[str, bool]:
    from backend.modules.vertice360_workflow_demo.services import process_inbound_message

    store.reset_store()
    now_ms = _epoch_ms()

    # Seed demo tickets
    seeds = [
        {
            "from": "+5491100000001",
            "name": "Juan Perez",
            "text": "Hola, estoy interesado en la unidad de 2 ambientes. ¿Sigue disponible?",
            "messageId": f"demo-msg-{now_ms}-1",
        },
        {
            "from": "+5491100000005",
            "name": "Maria Garcia",
            "text": "Adjunto mi comprobante de reserva y el DNI. Saludos!",
            "messageId": f"demo-msg-{now_ms}-2",
            "mediaCount": 2,
        },
        {
            "from": "+5491100000010",
            "name": "Soporte VTX",
            "text": "Test de integracion SSE",
            "messageId": f"demo-msg-{now_ms}-3",
        },
    ]

    for seed in seeds:
        seed["timestamp"] = now_ms
        await process_inbound_message(seed)
        now_ms += 500  # Small delay for sequencing

    payload = {
        "type": "CUSTOM",
        "timestamp": now_ms,
        "name": "workflow.reset",
        "value": {"at": now_ms, "reason": "manual"},
        "correlationId": "workflow",
    }
    await broadcaster.publish("workflow.reset", payload)
    return {"ok": True}


router = Router(
    path="/api/demo/vertice360-workflow",
    route_handlers=[WorkflowTicketsController, reset_demo],
)
