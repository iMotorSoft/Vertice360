"""
Litestar application entrypoint for Pozo360.
Run with: uv run python ls_iMotorSoft_Srv01.py
"""

import sys
from pathlib import Path

from litestar import Litestar
from litestar.middleware import DefineMiddleware

CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

import globalVar  # noqa: E402
from middleware.tenant_context import TenantContextMiddleware  # noqa: E402
from routes.agui_pozo_flow_v01 import run_agui_pozo_flow  # noqa: E402
from routes.health import health_check  # noqa: E402
from routes.tenant import tenant_branding  # noqa: E402
from routes.version import version  # noqa: E402


def create_app() -> Litestar:
    """Build and configure the Litestar app."""
    route_handlers = [health_check, version, tenant_branding, run_agui_pozo_flow]
    middleware = [DefineMiddleware(TenantContextMiddleware)]

    return Litestar(route_handlers=route_handlers, middleware=middleware)


app = create_app()


if __name__ == "__main__":
    # Running via `uv run python ls_iMotorSoft_Srv01.py` will serve the app.
    import uvicorn

    globalVar.boot_log()
    uvicorn.run(app, host=globalVar.HOST, port=globalVar.PORT)
