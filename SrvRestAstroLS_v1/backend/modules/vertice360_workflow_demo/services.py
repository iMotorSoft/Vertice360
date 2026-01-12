from __future__ import annotations

import datetime as dt
import unicodedata
from typing import Any

from backend.modules.messaging.providers.meta.whatsapp import send_message
from backend.modules.vertice360_workflow_demo import events, store


ASSIGNMENT_SLA_MS = 30 * 60 * 1000
DOC_VALIDATION_SLA_MS = 24 * 60 * 60 * 1000


def _epoch_ms() -> int:
    return int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in normalized if not unicodedata.combining(char))
    return stripped.lower()


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


def _build_auto_reply(name: str | None) -> str:
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


async def _send_whatsapp_text(to: str, text: str) -> dict[str, Any]:
    return await send_message(to, text)


async def process_inbound_message(inbound: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_inbound(inbound)
    actions: list[str] = []

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

    intent = classify_intent(normalized["text"])
    actions.append(f"INTENT_{intent}")

    reply_text: str | None = None
    now_ms = _epoch_ms()

    if intent in ("GREETING", "GENERAL"):
        if (ticket.get("status") or "").lower() == "open":
            await store.set_status(ticket_id, "IN_PROGRESS")
            actions.append("STATUS_IN_PROGRESS")

        reply_text = _build_auto_reply(normalized.get("name"))
        result = await _send_whatsapp_text(normalized["from"], reply_text)
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
            sentAt=now_ms,
        )
        store.add_message(
            ticket_id,
            {
                "direction": "outbound",
                "provider": normalized["provider"],
                "channel": normalized["channel"],
                "messageId": message_id,
                "text": reply_text,
                "at": now_ms,
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

    if intent in ("RESERVATION", "DOCS"):
        assignment_due_at = now_ms + ASSIGNMENT_SLA_MS
        doc_validation_due_at = now_ms + DOC_VALIDATION_SLA_MS
        ticket["sla"] = {
            "assignmentStartedAt": now_ms,
            "assignmentDueAt": assignment_due_at,
            "docValidationStartedAt": now_ms,
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
            await store.set_status(ticket_id, "WAITING_DOCS")
            actions.append("STATUS_WAITING_DOCS")

        await events.emit_ticket_sla_started(ticket_id, "ASSIGNMENT", assignment_due_at)
        await events.emit_ticket_sla_started(ticket_id, "DOC_VALIDATION", doc_validation_due_at)
        actions.append("SLA_STARTED")

        reply_text = _build_docs_reply()
        result = await _send_whatsapp_text(normalized["from"], reply_text)
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
            sentAt=now_ms,
        )
        store.add_message(
            ticket_id,
            {
                "direction": "outbound",
                "provider": normalized["provider"],
                "channel": normalized["channel"],
                "messageId": message_id,
                "text": reply_text,
                "at": now_ms,
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
