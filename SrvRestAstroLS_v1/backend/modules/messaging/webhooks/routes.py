from typing import Dict, Any
from litestar import Router, post, Request
from .dispatcher import handle_bird_webhook

@post("/bird")
async def receive_bird_webhook(request: Request, data: Dict[str, Any]) -> Dict[str, str]:
    """
    Endpoint for receiving Bird webhooks.
    """
    # Capture headers (for signature verification later)
    # Litestar makes headers available via request.headers
    # Converting to dict for parser compatibility
    headers = dict(request.headers.items())
    
    handle_bird_webhook(data, headers)
    return {"status": "ok"}

# Create a router for all webhook types, starting with Bird
webhook_router = Router(
    path="/webhooks",
    route_handlers=[receive_bird_webhook]
)
