from pydantic import BaseModel


class TenantBrandingResponse(BaseModel):
    display_name: str
    logo_url: str
    primary_color: str
    secondary_color: str
    accent_color: str
