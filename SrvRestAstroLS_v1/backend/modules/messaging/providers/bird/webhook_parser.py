from typing import Dict, Any, Optional
from backend.modules.messaging.domain.inbound_event import InboundEvent

def parse_bird_event(payload: Dict[str, Any], headers: Dict[str, Any], channel_hint: Optional[str] = None) -> InboundEvent:
    """
    Parses a Bird webhook payload into a generic InboundEvent.
    Adapt logic based on actual Bird webhook structure.
    """
    # Assuming standard Bird/MessageBird webhook structure
    # This is a best-effort parser based on common fields.
    
    # Example structure might verify:
    # {
    #   "id": "...",
    #   "from": "...",
    #   "to": "...",
    #   "content": { "text": "..." },
    #   "createdDatetime": "..."
    # }
    
    event_id = payload.get("id")
    sender = payload.get("from")
    recipient = payload.get("to")
    
    # Try to extract text, structure varies by channel (sms, whatsapp, etc)
    text = None
    content = payload.get("content", {})
    if isinstance(content, dict):
        text = content.get("text")
    elif isinstance(content, str):
        text = content
    
    # If not found in content, check message/body fields common in older hooks
    if not text:
        text = payload.get("body") or payload.get("message")

    timestamp = payload.get("createdDatetime") or payload.get("created_at")

    return InboundEvent(
        provider="bird",
        channel=channel_hint or "unknown",
        direction="inbound", # Webhooks are typically inbound 
        external_message_id=event_id,
        from_addr=sender,
        to_addr=recipient,
        text=text,
        timestamp=timestamp,
        raw=payload
    )
