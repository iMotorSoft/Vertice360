"""Service layer for Gupshup WhatsApp."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from .client import GupshupHTTPError, GupshupWhatsAppClient


def normalize_wa_to(to: str) -> str:
    """Normalize destination WhatsApp number (placeholder)."""
    return to


class GupshupWhatsAppSendError(Exception):
    """Raised when sending a message via Gupshup fails."""

    def __init__(
        self,
        message: str,
        *,
        upstream_status: int | None = None,
        upstream_body: str | None = None,
        url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.upstream_status = upstream_status
        self.upstream_body = upstream_body
        self.url = url


@dataclass(frozen=True)
class SendAck:
    provider_message_id: str
    raw: dict[str, Any]


class GupshupWhatsAppService:
    def __init__(self, client: GupshupWhatsAppClient | None = None) -> None:
        self._client = client or GupshupWhatsAppClient()

    async def send_text_message(self, to: str, text: str) -> SendAck:
        normalized_to = normalize_wa_to(to)
        try:
            raw = await self._client.send_text(normalized_to, text)
        except GupshupHTTPError as exc:
            raise GupshupWhatsAppSendError(
                "Gupshup send failed",
                upstream_status=exc.status_code,
                upstream_body=exc.response_text,
                url=exc.url,
            ) from exc
        except httpx.HTTPError as exc:
            raise GupshupWhatsAppSendError("Gupshup send failed", upstream_body=str(exc)) from exc
        except Exception as exc:
            raise GupshupWhatsAppSendError("Gupshup send failed", upstream_body=str(exc)) from exc

        provider_message_id = _extract_message_id(raw)
        return SendAck(provider_message_id=provider_message_id, raw=raw)


def _extract_message_id(raw: dict[str, Any]) -> str:
    # TODO: confirmar key exacta del id de mensaje en la respuesta.
    message_id = raw.get("messageId") or raw.get("id") or ""
    return str(message_id) if message_id else ""


async def send_text_message(to: str, text: str) -> SendAck:
    """Convenience wrapper around the default service."""
    service = GupshupWhatsAppService()
    return await service.send_text_message(to, text)
