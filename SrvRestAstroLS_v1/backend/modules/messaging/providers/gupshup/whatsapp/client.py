"""HTTP client for Gupshup WhatsApp."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import time
from typing import Any

import httpx
import globalVar
MESSAGE_PATH = "/wa/api/v1/msg"
MAX_ERROR_BODY_CHARS = 2000
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GupshupConfig:
    base_url: str
    api_key: str
    app_name: str
    sender_e164: str
    source_number: str

    @classmethod
    def from_env(cls) -> "GupshupConfig":
        return cls(
            base_url=globalVar.GUPSHUP_BASE_URL,
            api_key=globalVar.GUPSHUP_API_KEY,
            app_name=globalVar.GUPSHUP_APP_NAME,
            sender_e164=globalVar.get_gupshup_wa_sender_e164(),
            source_number=globalVar.get_gupshup_wa_sender_provider_value(),
        )


class GupshupHTTPError(RuntimeError):
    """Raised when Gupshup returns a non-success HTTP status."""

    def __init__(self, *, status_code: int, response_text: str, url: str) -> None:
        super().__init__(f"Gupshup HTTP error ({status_code})")
        self.status_code = status_code
        self.response_text = response_text
        self.url = url


class GupshupWhatsAppClient:
    def __init__(
        self,
        config: GupshupConfig | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config or GupshupConfig.from_env()
        self._client = client

    async def send_text(self, to: str, text: str) -> dict[str, Any]:
        url = _join_url(self._config.base_url, MESSAGE_PATH)
        headers = {"apikey": self._config.api_key}
        payload = {
            # TODO: confirmar nombres de campos exactos en docs de Gupshup.
            "channel": "whatsapp",
            "source": self._config.source_number,
            "destination": to,
            "message": {"type": "text", "text": text},
            "src.name": self._config.app_name,
        }

        async def _post(http_client: httpx.AsyncClient) -> dict[str, Any]:
            started_at = time.perf_counter()
            response = await http_client.post(url, data=_encode_payload(payload), headers=headers, timeout=20.0)
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            logger.info(
                "GUPSHUP_HTTP_SEND sender=%s source=%s url=%s status=%s duration_ms=%s",
                self._config.sender_e164 or "-",
                self._config.source_number or "-",
                url,
                response.status_code,
                duration_ms,
            )
            if response.status_code >= 400:
                raise GupshupHTTPError(
                    status_code=response.status_code,
                    response_text=_truncate_error_text(response.text),
                    url=str(response.request.url),
                )
            try:
                return response.json()
            except ValueError:
                return {"raw": response.text}

        if self._client is None:
            async with httpx.AsyncClient() as http_client:
                return await _post(http_client)
        return await _post(self._client)


def _join_url(base: str, path: str) -> str:
    return f"{base.rstrip('/')}{path}"


def _encode_payload(payload: dict[str, Any]) -> dict[str, str]:
    encoded: dict[str, str] = {}
    for key, value in payload.items():
        if isinstance(value, (dict, list)):
            encoded[key] = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
        elif value is None:
            continue
        else:
            encoded[key] = str(value)
    return encoded


def _truncate_error_text(text: str) -> str:
    if len(text) <= MAX_ERROR_BODY_CHARS:
        return text
    return f"{text[:MAX_ERROR_BODY_CHARS]}... [truncated]"


async def send_message(to: str, text: str) -> dict[str, Any]:
    """Convenience wrapper around the default client."""
    client = GupshupWhatsAppClient()
    return await client.send_text(to, text)
