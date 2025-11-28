"""
Tenant context middleware stub.
Assigns a demo tenant ID based on the Host header for future multi-tenant support.
"""

from litestar.middleware.base import MiddlewareProtocol
from litestar.types import ASGIApp, Receive, Scope, Send


class TenantContextMiddleware(MiddlewareProtocol):
    """Attach a tenant identifier to the ASGI scope."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Basic host-based hook for future tenant resolution.
        host_header = None
        for name, value in scope.get("headers", []):
            if name == b"host":
                host_header = value.decode()
                break

        scope["tenant_id"] = "demo"
        scope["tenant_host"] = host_header or "unknown"

        await self.app(scope, receive, send)
