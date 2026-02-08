"""Gupshup WhatsApp provider stubs (no endpoints wired yet)."""

from .client import GupshupHTTPError, GupshupWhatsAppClient, send_message
from .mapper import build_text_payload
from .service import GupshupWhatsAppSendError, SendAck, normalize_wa_to, send_text_message
from .signature import verify_signature

__all__ = [
    "GupshupWhatsAppClient",
    "GupshupHTTPError",
    "GupshupWhatsAppSendError",
    "SendAck",
    "normalize_wa_to",
    "send_text_message",
    "send_message",
    "build_text_payload",
    "verify_signature",
]
