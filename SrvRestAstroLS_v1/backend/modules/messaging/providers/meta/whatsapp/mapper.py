from __future__ import annotations

from typing import Any, Iterable


def extract_inbound_messages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for value in _iter_change_values(payload):
        metadata = _extract_metadata(value)
        contacts = _extract_contact_wa_ids(value)
        for message in value.get("messages", []) or []:
            if not isinstance(message, dict):
                continue
            wa_id = message.get("from") or message.get("wa_id") or _first_contact(contacts)
            to = metadata.get("phone_number_id") or metadata.get("display_phone_number")
            data: dict[str, Any] = {
                "wa_id": wa_id,
                "from": message.get("from") or wa_id,
                "to": to,
                "text": _extract_text(message),
                "timestamp": message.get("timestamp"),
                "message_id": message.get("id"),
                "media_count": _count_media(message),
            }
            raw = _message_raw(message)
            if raw:
                data["raw"] = raw
            messages.append(data)
    return messages


def extract_status_updates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    statuses: list[dict[str, Any]] = []
    for value in _iter_change_values(payload):
        for status in value.get("statuses", []) or []:
            if not isinstance(status, dict):
                continue
            data: dict[str, Any] = {
                "wa_id": status.get("recipient_id"),
                "message_id": status.get("id"),
                "status": status.get("status"),
                "timestamp": status.get("timestamp"),
            }
            raw = _status_raw(status)
            if raw:
                data["raw"] = raw
            statuses.append(data)
    return statuses


def _iter_change_values(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for entry in payload.get("entry", []) or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes", []) or []:
            if not isinstance(change, dict):
                continue
            value = change.get("value")
            if isinstance(value, dict):
                yield value


def _extract_contact_wa_ids(value: dict[str, Any]) -> list[str]:
    wa_ids: list[str] = []
    for contact in value.get("contacts", []) or []:
        if not isinstance(contact, dict):
            continue
        wa_id = contact.get("wa_id")
        if wa_id:
            wa_ids.append(wa_id)
    return wa_ids


def _extract_metadata(value: dict[str, Any]) -> dict[str, Any]:
    metadata = value.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _first_contact(wa_ids: list[str]) -> str | None:
    return wa_ids[0] if wa_ids else None


def _extract_text(message: dict[str, Any]) -> str | None:
    text = message.get("text", {}).get("body")
    if text:
        return text

    button = message.get("button", {})
    if button:
        return button.get("text") or button.get("payload")

    interactive = message.get("interactive", {})
    if interactive:
        button_reply = interactive.get("button_reply", {})
        if button_reply:
            return button_reply.get("title") or button_reply.get("id")
        list_reply = interactive.get("list_reply", {})
        if list_reply:
            return list_reply.get("title") or list_reply.get("id")

    return message.get("type")


def _message_raw(message: dict[str, Any]) -> dict[str, Any]:
    raw: dict[str, Any] = {}
    message_type = message.get("type")
    if message_type:
        raw["type"] = message_type
    if "context" in message:
        raw["context"] = message.get("context")
    if "errors" in message:
        raw["errors"] = message.get("errors")
    return raw


def _count_media(message: dict[str, Any]) -> int:
    media_keys = ("image", "video", "audio", "document", "sticker")
    count = sum(1 for key in media_keys if key in message)
    if count == 0 and message.get("type") in media_keys:
        count = 1
    return count


def _status_raw(status: dict[str, Any]) -> dict[str, Any]:
    raw: dict[str, Any] = {}
    for key in ("conversation", "pricing", "errors"):
        if key in status and status.get(key) is not None:
            raw[key] = status.get(key)
    return raw
