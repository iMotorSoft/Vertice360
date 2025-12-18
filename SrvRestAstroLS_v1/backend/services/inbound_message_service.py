import logging
from ..modules.messaging.domain.inbound_event import InboundEvent

# Configure logger
logger = logging.getLogger(__name__)

def handle_inbound_event(event: InboundEvent) -> None:
    """
    Generic handler for processing inbound events from any provider.
    Currently logs the event details.
    """
    logger.info(
        "InboundEvent received: provider=%s channel=%s from=%s ext_id=%s text=%s",
        event.provider,
        event.channel,
        event.from_addr,
        event.external_message_id,
        event.text
    )
    
    # Placeholder for future logic (e.g., save to DB, trigger workflows)
    # db.save(event)
