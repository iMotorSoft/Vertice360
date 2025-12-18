from typing import Dict, Any
from ..providers.bird.webhook_parser import parse_bird_event
from backend.services.inbound_message_service import handle_inbound_event

def handle_bird_webhook(payload: Dict[str, Any], headers: Dict[str, Any]) -> None:
    """
    Dispatcher for Bird webhooks. 
    Parses the event and delegates to the generic inbound message service.
    """
    # 1. Parse
    event = parse_bird_event(payload, headers)
    
    # 2. Dispatch to service
    handle_inbound_event(event)
