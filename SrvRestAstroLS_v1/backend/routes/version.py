import sys
from pathlib import Path

from litestar import get

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
ROOT_DIR = BACKEND_DIR.parent

if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

import globalVar  # noqa: E402
from models.common import VersionResponse


@get("/version")
async def version() -> VersionResponse:
    """Return application version metadata."""
    return VersionResponse(app_name=globalVar.APP_NAME, version=globalVar.APP_VERSION, environment=globalVar.ENVIRONMENT)
