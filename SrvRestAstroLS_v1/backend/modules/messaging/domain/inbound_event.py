from dataclasses import dataclass
from typing import Dict, Optional, Any

@dataclass
class InboundEvent:
    provider: str
    channel: str
    direction: str  # "inbound" | "outbound"
    raw: Dict[str, Any]
    external_message_id: Optional[str] = None
    from_addr: Optional[str] = None
    to_addr: Optional[str] = None
    text: Optional[str] = None
    timestamp: Optional[str] = None  # ISO format preferred
