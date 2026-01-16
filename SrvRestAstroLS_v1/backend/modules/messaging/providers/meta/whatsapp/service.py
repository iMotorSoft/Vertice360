from __future__ import annotations

import logging
from typing import Any

import httpx

from .client import MetaWhatsAppSendError, post_message
from .mapper import normalize_wa_to, waid_to_graph_to

logger = logging.getLogger(__name__)


async def send_text_message(
    to: str,
    text: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    wa_id = normalize_wa_to(to)
    graph_to = waid_to_graph_to(wa_id)
    logger.info("Meta WhatsApp send mapped wa_id=%s graph_to=%s", wa_id, graph_to)
    payload = {
        "messaging_product": "whatsapp",
        "to": graph_to,
        "type": "text",
        "text": {"body": text},
    }
    return await post_message(payload, client=client)


__all__ = ["MetaWhatsAppSendError", "normalize_wa_to", "send_text_message"]
