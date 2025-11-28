from litestar import get

from models.tenant import TenantBrandingResponse


@get("/tenant/branding")
async def tenant_branding() -> TenantBrandingResponse:
    """Return demo branding for future multi-tenant support."""
    return TenantBrandingResponse(
        display_name="Estudio Demo",
        logo_url="/static/logo-demo.svg",
        primary_color="#0050E6",
        secondary_color="#FFD700",
        accent_color="#0038B8",
    )
