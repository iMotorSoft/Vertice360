from litestar import get

from models.common import HealthResponse


@get("/health")
async def health_check() -> HealthResponse:
    """Simple health endpoint."""
    return HealthResponse(status="ok", service="Pozo360")
