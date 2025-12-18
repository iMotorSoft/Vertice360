from contextvars import ContextVar
from typing import Optional
import uuid

# Context variables to hold ID strings
_request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)

def set_request_id(value: str) -> None:
    """Sets the request ID for the current context."""
    _request_id_ctx.set(value)

def get_request_id() -> Optional[str]:
    """Gets the request ID from the current context."""
    return _request_id_ctx.get()

def set_correlation_id(value: str) -> None:
    """Sets the correlation ID for the current context."""
    _correlation_id_ctx.set(value)

def get_correlation_id() -> Optional[str]:
    """Gets the correlation ID from the current context."""
    return _correlation_id_ctx.get()

def generate_uuid() -> str:
    """Helper to generate a new UUID string."""
    return str(uuid.uuid4())
