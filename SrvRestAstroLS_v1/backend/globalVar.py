# -*- coding: utf-8 -*-
# vertice360 / globalVar.py

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Optional

# =========================
# App / environment
# =========================
APP_NAME: str = "Vertice360"
APP_VERSION: str = os.environ.get("VERTICE360_APP_VERSION", "0.1.0")
# Validate and normalize environment
_env_raw = os.environ.get("VERTICE360_ENV", "dev").lower().strip()
ENVIRONMENT: Literal["dev", "stg", "prod"]
if _env_raw in ("dev", "stg", "prod"):
    ENVIRONMENT = _env_raw  # type: ignore[assignment]
else:
    ENVIRONMENT = "dev"  # type: ignore[assignment]
    print(
        f"[Vertice360] WARNING: Invalid VERTICE360_ENV='{os.environ.get('VERTICE360_ENV')}', defaulting to 'dev'"
    )
RUN_ENV: Literal["dev", "stg", "prod"] = ENVIRONMENT

ENABLE_PRUEBAS: bool = False
PRUEBA_NIVEL: int = 0

DEBUG: bool = RUN_ENV != "prod"
LOG_LEVEL: str = "DEBUG" if DEBUG else "INFO"

# =========================
# API server
# =========================
HOST: str = os.environ.get("VERTICE360_HOST", "0.0.0.0")
PORT: int = int(os.environ.get("VERTICE360_PORT", "7062"))
UVICORN_WORKERS: int = max(1, int(os.environ.get("VERTICE360_UVICORN_WORKERS", "1")))

# =========================
# Frontend / CORS
# =========================
FRONTEND_ORIGINS: list[str] = [
    os.environ.get("VERTICE360_FE_URL_LOCAL", "http://localhost:3062"),
    os.environ.get("VERTICE360_FE_URL_IP", "http://127.0.0.1:3062"),
]

# =========================
# Public base URL (dev/pro) https://demo.pozo360.imotorsoft.com
# =========================
VERTICE360_PUBLIC_BASE_URL_DEV: str = (
    "https://attribute-lighter-vip-joined.trycloudflare.com"
)
VERTICE360_PUBLIC_BASE_URL_PRO: str = os.environ.get(
    "VERTICE360_PUBLIC_BASE_URL_PRO",
    "https://demo.pozo360.imotorsoft.com",
)
VERTICE360_PUBLIC_BASE_URL: str = VERTICE360_PUBLIC_BASE_URL_PRO


# =========================
# Project / data roots
# =========================
# Este archivo vive en: .../Vertice360/SrvRestAstroLS_v1/backend/globalVar.py
PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
VERTICE360_ROOT: Path = PROJECT_ROOT  # alias

_storage_provider = os.environ.get("VERTICE360_STORAGE_PROVIDER", "local")
STORAGE_PROVIDER: Literal["local", "s3"] = (
    "s3" if _storage_provider == "s3" else "local"
)
STORAGE_LOCAL_ROOT: str = os.environ.get(
    "VERTICE360_STORAGE_LOCAL_ROOT", (VERTICE360_ROOT / "storage").as_posix()
)
STORAGE_INCOMING: str = "incoming"
STORAGE_CANONICAL: str = "canonical"
STORAGE_ARCHIVES: str = "archives"

DATA_ROOT: str = os.environ.get(
    "VERTICE360_DATA_ROOT", (VERTICE360_ROOT / "data").as_posix()
)
DATA_REPORTS: str = "reports"

PARTITION_ACCOUNT: str = "account"
PARTITION_PERIOD: str = "period"  # YYYY-MM

# =========================
# Database
# =========================
DB_URL: str = os.environ.get(
    "VERTICE360_DB_URL",
    "postgresql+psycopg://user:pass@localhost:5432/vertice360",
)
DB_SCHEMA: str = os.environ.get("VERTICE360_DB_SCHEMA", "public")
ENABLE_PG_TRGM: bool = True
ENABLE_PG_VECTOR: bool = True

# =========================
# Security / Roles
# =========================
JWT_SECRET: str = os.environ.get("VERTICE360_JWT_SECRET", "change_me_dev_only")
JWT_ISSUER: str = APP_NAME
JWT_AUDIENCE: str = f"{APP_NAME}-app"
ROLES: tuple[str, ...] = ("ADMIN", "OPERATOR", "AUDITOR", "VIEWER")

# =========================
# Features / Rules
# =========================
FEATURE_AI: bool = False
VERTICE360_AI_WORKFLOW_REPLY: bool = True
VERTICE360_AI_WORKFLOW_REPLY_PREVIEW_MAX: int = 240
WORKFLOW_TICKET_SESSION_TTL_SECONDS: int = int(
    os.environ.get("WORKFLOW_TICKET_SESSION_TTL_SECONDS", "1800")
)
DEFAULT_DATE_WINDOW_DAYS: int = 3
DEFAULT_ROUNDING_DECIMALS: int = 2

RULES_DIR: str = (PROJECT_ROOT / "rules").as_posix()
RULES_PROFILES_DIR: str = f"{RULES_DIR}/profiles"
RULES_RULESETS_DIR: str = f"{RULES_DIR}/rulesets"

# =========================
# LLM / OpenAI (compat)
# =========================
OpenAI_Key: Optional[str] = os.environ.get("VERTICE360_OPENAI_KEY") or os.environ.get(
    "OPENAI_API_KEY"
)
OpenAI_Model: str = os.environ.get("VERTICE360_OPENAI_MODEL", "gpt-4o-mini")

# =========================
# MLflow (optional)
# =========================
MLFLOW_TRACKING_URI_DEV: str = os.environ.get(
    "VERTICE360_MLFLOW_TRACKING_URI_DEV",
    f"file://{(PROJECT_ROOT / 'mlruns_vertice360').as_posix()}",
)
MLFLOW_TRACKING_URI_PRO: str = os.environ.get(
    "VERTICE360_MLFLOW_TRACKING_URI_PRO", MLFLOW_TRACKING_URI_DEV
)
MLFLOW_TRACKING_URI: str = (
    MLFLOW_TRACKING_URI_DEV if RUN_ENV != "prod" else MLFLOW_TRACKING_URI_PRO
)
MLFLOW_ENABLED: bool = os.environ.get("MLFLOW_ENABLED", "0") in ("1", "true", "True")
MLFLOW_EXPERIMENT: str = os.environ.get("MLFLOW_EXPERIMENT", "vertice360")

# =========================
# Messaging / Meta WhatsApp Cloud (Vertice360)
# =========================
META_VERTICE360_WABA_TOKEN: str = os.environ.get("META_VERTICE360_WABA_TOKEN", "")
META_VERTICE360_WABA_ID: str = os.environ.get("META_VERTICE360_WABA_ID", "")
META_VERTICE360_PHONE_NUMBER_ID: str = os.environ.get(
    "META_VERTICE360_PHONE_NUMBER_ID", ""
)
META_VERTICE360_VERIFY_TOKEN: str = os.environ.get("META_VERTICE360_VERIFY_TOKEN", "")
META_APP_SECRET_IMOTORSOFT: str = os.environ.get("META_APP_SECRET_IMOTORSOFT", "")
META_GRAPH_VERSION: str = os.environ.get("META_GRAPH_VERSION", "v20.0")

# =========================
# Messaging / Gupshup WhatsApp (Vertice360)
# =========================
DEFAULT_GUPSHUP_BASE_URL: str = "https://api.gupshup.io"
GUPSHUP_APP_NAME_DEV: str = os.environ.get("GUPSHUP_APP_NAME_DEV", "")
GUPSHUP_APP_NAME_PRO: str = os.environ.get("GUPSHUP_APP_NAME_PRO", "vertice360pro")
GUPSHUP_API_KEY_DEV: str = os.environ.get("GUPSHUP_API_KEY_DEV", "")
GUPSHUP_API_KEY_PRO: str = os.environ.get("GUPSHUP_API_KEY_PRO", "")
GUPSHUP_SRC_NUMBER_DEV: str = os.environ.get("GUPSHUP_SRC_NUMBER_DEV", "")
GUPSHUP_SRC_NUMBER_PRO: str = os.environ.get("GUPSHUP_SRC_NUMBER_PRO", "4526325250")
GUPSHUP_BASE_URL_DEV: str = os.environ.get(
    "GUPSHUP_BASE_URL_DEV", DEFAULT_GUPSHUP_BASE_URL
)
GUPSHUP_BASE_URL_PRO: str = os.environ.get("GUPSHUP_BASE_URL_PRO", GUPSHUP_BASE_URL_DEV)

# Optional staging constants (fallback to dev if not defined)
GUPSHUP_APP_NAME_STG: str = os.environ.get("GUPSHUP_APP_NAME_STG", GUPSHUP_APP_NAME_DEV)
GUPSHUP_API_KEY_STG: str = os.environ.get("GUPSHUP_API_KEY_STG", GUPSHUP_API_KEY_DEV)
GUPSHUP_SRC_NUMBER_STG: str = os.environ.get(
    "GUPSHUP_SRC_NUMBER_STG", GUPSHUP_SRC_NUMBER_DEV
)
GUPSHUP_BASE_URL_STG: str = os.environ.get("GUPSHUP_BASE_URL_STG", GUPSHUP_BASE_URL_DEV)


# =========================
# Environment-aware selection helper
# =========================
def _pick_env(dev, stg, prod):
    """Select value based on current ENVIRONMENT."""
    return {"dev": dev, "stg": stg, "prod": prod}[ENVIRONMENT]


# Automatic environment selection
GUPSHUP_APP_NAME: str = _pick_env(
    GUPSHUP_APP_NAME_DEV, GUPSHUP_APP_NAME_STG, GUPSHUP_APP_NAME_PRO
)
GUPSHUP_API_KEY: str = _pick_env(
    GUPSHUP_API_KEY_DEV, GUPSHUP_API_KEY_STG, GUPSHUP_API_KEY_PRO
)
GUPSHUP_SRC_NUMBER: str = _pick_env(
    GUPSHUP_SRC_NUMBER_DEV, GUPSHUP_SRC_NUMBER_STG, GUPSHUP_SRC_NUMBER_PRO
)
GUPSHUP_BASE_URL: str = _pick_env(
    GUPSHUP_BASE_URL_DEV, GUPSHUP_BASE_URL_STG, GUPSHUP_BASE_URL_PRO
)


# =========================
# Helpers
# =========================
def resolve_storage_uri(
    kind: Literal["incoming", "canonical", "archives"],
    account_id: str | int | None = None,
    period: str | None = None,
    filename: str | None = None,
) -> str:
    """Construye URI file:// (local) o s3:// (si cambias el provider)."""
    if STORAGE_PROVIDER == "local":
        base = Path(STORAGE_LOCAL_ROOT) / kind
        if kind == "canonical":
            if account_id is not None:
                base = base / f"{PARTITION_ACCOUNT}={account_id}"
            if period is not None:
                base = base / f"{PARTITION_PERIOD}={period}"
        if filename:
            base = base / filename
        return f"file://{base.as_posix()}"

    bucket = os.environ.get("VERTICE360_S3_BUCKET", "vertice360-bucket")
    prefix = os.environ.get("VERTICE360_S3_PREFIX", "storage")
    parts = [prefix, kind]
    if kind == "canonical":
        if account_id is not None:
            parts.append(f"{PARTITION_ACCOUNT}={account_id}")
        if period is not None:
            parts.append(f"{PARTITION_PERIOD}={period}")
    if filename:
        parts.append(filename)
    key = "/".join(parts)
    return f"s3://{bucket}/{key}"


def ensure_local_dirs() -> None:
    """Crea carpetas locales críticas (modo local)."""
    if STORAGE_PROVIDER == "local":
        for sub in (STORAGE_INCOMING, STORAGE_CANONICAL, STORAGE_ARCHIVES):
            Path(STORAGE_LOCAL_ROOT, sub).mkdir(parents=True, exist_ok=True)
    Path(DATA_ROOT, DATA_REPORTS).mkdir(parents=True, exist_ok=True)


def is_prod() -> bool:
    return RUN_ENV == "prod"


def mask(value: Optional[str], visible: int = 4) -> str:
    if not value:
        return ""
    return value[:visible] + "****"


def public_url(path: str) -> str:
    base = (VERTICE360_PUBLIC_BASE_URL or "").strip()
    if not base:
        return ""
    clean_path = str(path or "").strip()
    if not clean_path:
        return base.rstrip("/")
    if not clean_path.startswith("/"):
        clean_path = f"/{clean_path}"
    return f"{base.rstrip('/')}{clean_path}"


def meta_whatsapp_enabled() -> bool:
    return bool(
        META_VERTICE360_WABA_TOKEN
        and META_VERTICE360_PHONE_NUMBER_ID
        and META_VERTICE360_VERIFY_TOKEN
    )


def gupshup_whatsapp_enabled() -> bool:
    return bool(GUPSHUP_APP_NAME and GUPSHUP_API_KEY and GUPSHUP_SRC_NUMBER)


def boot_log() -> None:
    print(
        f"[{APP_NAME}] version={APP_VERSION} env={RUN_ENV} debug={DEBUG} log={LOG_LEVEL}"
    )
    print(f"[{APP_NAME}] host={HOST} port={PORT}")
    print(f"[{APP_NAME}] uvicorn_workers={UVICORN_WORKERS}")
    print(f"[{APP_NAME}] db={DB_URL}")
    print(
        f"[{APP_NAME}] storage_provider={STORAGE_PROVIDER} local_root={STORAGE_LOCAL_ROOT}"
    )
    print(f"[{APP_NAME}] data_root={DATA_ROOT}")
    print(f"[{APP_NAME}] rules_dir={RULES_DIR}")
    print(f"[{APP_NAME}] ai_workflow_reply={VERTICE360_AI_WORKFLOW_REPLY}")
    print(f"[{APP_NAME}] mlflow={MLFLOW_TRACKING_URI}")
    print(f"[{APP_NAME}] openai_key={mask(OpenAI_Key)} model={OpenAI_Model}")
    print(
        f"[{APP_NAME}] meta_phone_id={META_VERTICE360_PHONE_NUMBER_ID} meta_graph={META_GRAPH_VERSION}"
    )
    print(
        f"[{APP_NAME}] meta_verify_token={mask(META_VERTICE360_VERIFY_TOKEN)} "
        f"meta_app_secret={mask(META_APP_SECRET_IMOTORSOFT)}"
    )
    print(
        f"[{APP_NAME}] gupshup_app={GUPSHUP_APP_NAME} gupshup_src={GUPSHUP_SRC_NUMBER} "
        f"gupshup_enabled={gupshup_whatsapp_enabled()}"
    )


# Self-test block
if __name__ == "__main__":
    print(
        f"ENV={ENVIRONMENT} gupshup_app={GUPSHUP_APP_NAME} gupshup_src={GUPSHUP_SRC_NUMBER} gupshup_enabled={gupshup_whatsapp_enabled()}"
    )
