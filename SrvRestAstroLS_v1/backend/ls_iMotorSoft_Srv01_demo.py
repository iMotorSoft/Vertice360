# Servidor DEMO Vertice360 – usa mock/demo data y expone la demo Codex:
# - /demo/codex/* (Codex CLI)
# Este launcher también expone la demo Antigravity (AG-UI) de Vertice360 bajo /api/demo/ag y /demo/antigravity (NO PRODUCCIÓN).
# NO usar este launcher para producción.

import sys
from pathlib import Path

from litestar import Litestar
from litestar.middleware import DefineMiddleware
from litestar.config.cors import CORSConfig

CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

import globalVar  # noqa: E402
from middleware.tenant_context import TenantContextMiddleware  # noqa: E402
from routes.demo_codex_vertice360 import router as codex_demo_router  # noqa: E402
from routes.demo_codex_chat import router as codex_chat_router  # noqa: E402
from routes.demo_ag_vertice360 import router as ag_demo_router  # noqa: E402
from routes.health import health_check  # noqa: E402
from routes.version import version  # noqa: E402
from backend.modules.agui_stream import agui_stream, debug_trigger_event  # noqa: E402
from backend.modules.crm_demo import crm_router  # noqa: E402
from routes.demo_sse_test import SseTestController  # noqa: E402
from backend.modules.messaging.webhooks import webhook_router  # noqa: E402
from backend.telemetry.logging import setup_logging  # noqa: E402
from backend.middleware.telemetry_middleware import TelemetryMiddleware  # noqa: E402
from backend.routes.messaging import messaging_router  # noqa: E402


def create_app() -> Litestar:
    """Construye la app Litestar de demo Codex."""
    route_handlers = [
        health_check,
        version,
        codex_demo_router,
        codex_chat_router,
        ag_demo_router,
        agui_stream,
        debug_trigger_event,
        crm_router,
        SseTestController,
        webhook_router,
        messaging_router,
    ]
    middleware = [DefineMiddleware(TenantContextMiddleware), DefineMiddleware(TelemetryMiddleware)]
    # Abrimos CORS en modo demo para permitir llamadas desde Astro (dev/preview).
    cors_config = CORSConfig(
        allow_origins=globalVar.FRONTEND_ORIGINS,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=[
            "Accept",
            "Content-Type",
            "Authorization",
            "Cache-Control",
            "Last-Event-ID",
            "X-Requested-With",
        ],
        expose_headers=["Content-Type"],
        allow_credentials=False,  # poné True sólo si usás cookies/sesión en navegador
        max_age=86400,
    )
    return Litestar(route_handlers=route_handlers, middleware=middleware, cors_config=cors_config)


app = create_app()
setup_logging()  # Configure formatted logging on startup


if __name__ == "__main__":
    import uvicorn

    globalVar.boot_log()
    uvicorn.run(app, host=globalVar.HOST, port=globalVar.PORT)
