import time
import logging
from typing import Callable, Any
from litestar.types import ASGIApp, Scope, Receive, Send, Message
from litestar.middleware import MiddlewareProtocol

from ..telemetry.context import (
    set_request_id,
    set_correlation_id,
    generate_uuid,
    get_request_id,
    get_correlation_id
)

logger = logging.getLogger(__name__)

class TelemetryMiddleware(MiddlewareProtocol):
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        
        # Extract headers from scope (list of tuples bytes)
        req_headers = dict(scope.get("headers", []))
        
        # Helper to get header value (bytes to str)
        def get_header(name: str) -> str | None:
            key = name.lower().encode("latin-1")
            val = req_headers.get(key)
            return val.decode("latin-1") if val else None

        # Request ID
        req_id = get_header("X-Request-Id") or generate_uuid()
        set_request_id(req_id)
        
        # Correlation ID
        corr_id = get_header("X-Correlation-Id") or generate_uuid()
        set_correlation_id(corr_id)

        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "")
        print(f"\n>>> [MIDDLEWARE] New Request: {method} {path}")
        
        logger.info(f"START {method} {path}")

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                # Inject headers into response
                # headers is MutableMapping or list of tuples
                headers = message.setdefault("headers", [])
                
                # Check if we need to encode
                rid = (get_request_id() or "").encode("latin-1")
                cid = (get_correlation_id() or "").encode("latin-1")
                
                headers.append((b"x-request-id", rid))
                headers.append((b"x-correlation-id", cid))
                
                status = message.get("status")
                duration = (time.time() - start_time) * 1000
                logger.info(f"END {method} {path} status={status} duration={duration:.2f}ms")
                
            await send(message)

        await self.app(scope, receive, send_wrapper)
