"""HTTP client for Gupshup WhatsApp."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import globalVar
MESSAGE_PATH = "/sm/api/v1/msg"


@dataclass(frozen=True)
class GupshupConfig:
    base_url: str
    api_key: str
    app_name: str
    src_number: str

    @classmethod
    def from_env(cls) -> "GupshupConfig":
        return cls(
            base_url=globalVar.GUPSHUP_BASE_URL,
            api_key=globalVar.GUPSHUP_API_KEY,
            app_name=globalVar.GUPSHUP_APP_NAME,
            src_number=globalVar.GUPSHUP_SRC_NUMBER,
        )


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
            "app": self._config.app_name,
            "src": self._config.src_number,
            "to": to,
            "text": text,
        }

        async def _post(http_client: httpx.AsyncClient) -> dict[str, Any]:
            response = await http_client.post(url, json=payload, headers=headers, timeout=20.0)
            response.raise_for_status()
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


async def send_message(to: str, text: str) -> dict[str, Any]:
    """Convenience wrapper around the default client."""
    client = GupshupWhatsAppClient()
    return await client.send_text(to, text)
