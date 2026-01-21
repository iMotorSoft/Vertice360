from __future__ import annotations

import datetime as dt
import unicodedata
from typing import Any

import logging
from backend import globalVar
from backend.modules.messaging.providers.meta.whatsapp import MetaWhatsAppSendError, send_text_message
from backend.modules.vertice360_workflow_demo import events, store


ASSIGNMENT_SLA_MS = 30 * 60 * 1000
DOC_VALIDATION_SLA_MS = 24 * 60 * 60 * 1000

logger = logging.getLogger(__name__)


def _epoch_ms() -> int:
    return int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in normalized if not unicodedata.combining(char))
    return stripped.lower()


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
    return await send_text_message(to, text)


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
        result = await _send_whatsapp_text(to, text)
    except MetaWhatsAppSendError as exc:
        error_payload = {"status_code": exc.status_code, "err": exc.err}
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

    intent = classify_intent(normalized["text"])
    actions.append(f"INTENT_{intent}")

    reply_text: str | None = None
    now_ms = _epoch_ms()

    if intent in ("GREETING", "GENERAL"):
        if (ticket.get("status") or "").lower() == "open":
            await store.set_status(ticket_id, "IN_PROGRESS")
            actions.append("STATUS_IN_PROGRESS")

        reply_text = _pick_whatsapp_reply_text(
            ai_response_text, _build_auto_reply(normalized.get("name"))
        )
        try:
            result = await _send_whatsapp_text(normalized["from"], reply_text)
        except MetaWhatsAppSendError as exc:
            actions.append("OUTBOUND_FAILED")
            error_payload = {"status_code": exc.status_code, "err": exc.err}
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
            prev_status = ticket.get("status")
            await store.set_status(ticket_id, "WAITING_DOCS")
            if (ticket.get("status") or "").upper() == "WAITING_DOCS" and ticket.get("status") != prev_status:
                actions.append("STATUS_WAITING_DOCS")

        await events.emit_ticket_sla_started(ticket_id, "ASSIGNMENT", assignment_due_at)
        await events.emit_ticket_sla_started(ticket_id, "DOC_VALIDATION", doc_validation_due_at)
        actions.append("SLA_STARTED")

        reply_text = _pick_whatsapp_reply_text(ai_response_text, _build_docs_reply())
        try:
            result = await _send_whatsapp_text(normalized["from"], reply_text)
        except MetaWhatsAppSendError as exc:
            actions.append("OUTBOUND_FAILED")
            error_payload = {"status_code": exc.status_code, "err": exc.err}
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
