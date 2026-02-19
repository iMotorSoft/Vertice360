from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx
import globalVar

logger = logging.getLogger(__name__)


class MetaWhatsAppSendError(RuntimeError):
    def __init__(self, status_code: int, err: Any) -> None:
        super().__init__(f"Meta WhatsApp send failed ({status_code})")
        self.status_code = status_code
        self.err = err


async def post_message(payload: dict[str, Any], *, client: httpx.AsyncClient | None = None) -> dict[str, Any]:
    if globalVar.get_env_bool("DEMO_DISABLE_META_SEND", False):
        message_id = f"demo-{uuid.uuid4().hex}"
        return {"status": "skipped", "messages": [{"id": message_id}]}
    if not globalVar.meta_whatsapp_enabled():
        return {"error": "Meta WhatsApp not configured (missing env vars)"}

    url = f"https://graph.facebook.com/{globalVar.META_GRAPH_VERSION}/{globalVar.META_VERTICE360_PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {globalVar.META_VERTICE360_WABA_TOKEN}",
        "Content-Type": "application/json",
    }
    
    async def _post(http_client: httpx.AsyncClient) -> dict[str, Any]:
        response = await http_client.post(url, json=payload, headers=headers, timeout=20.0)

        if response.status_code >= 400:
            try:
                err = response.json()
            except ValueError:
                err = {"raw": response.text}
            logger.error(
                "Meta WhatsApp send failed phone_number_id=%s to=%s status_code=%s err=%s",
                globalVar.META_VERTICE360_PHONE_NUMBER_ID,
                payload.get("to"),
                response.status_code,
                err,
            )
            raise MetaWhatsAppSendError(response.status_code, err)

        return response.json()

    if client is None:
        async with httpx.AsyncClient() as http_client:
            return await _post(http_client)
    return await _post(client)


async def send_message(to: str, text: str) -> dict[str, Any]:
    from .service import send_text_message

    return await send_text_message(to, text)
