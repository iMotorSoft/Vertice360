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
ENVIRONMENT: Literal["dev", "stg", "prod"] = os.environ.get("VERTICE360_ENV", "dev")
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

# =========================
# Frontend / CORS
# =========================
FRONTEND_ORIGINS: list[str] = [
    os.environ.get("VERTICE360_FE_URL_LOCAL", "http://localhost:3062"),
    os.environ.get("VERTICE360_FE_URL_IP", "http://127.0.0.1:3062"),
]


# =========================
# Project / data roots
# =========================
# Este archivo vive en: .../Vertice360/SrvRestAstroLS_v1/backend/globalVar.py
PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
VERTICE360_ROOT: Path = PROJECT_ROOT  # alias

_storage_provider = os.environ.get("VERTICE360_STORAGE_PROVIDER", "local")
STORAGE_PROVIDER: Literal["local", "s3"] = "s3" if _storage_provider == "s3" else "local"
STORAGE_LOCAL_ROOT: str = os.environ.get(
    "VERTICE360_STORAGE_LOCAL_ROOT", (VERTICE360_ROOT / "storage").as_posix()
)
STORAGE_INCOMING: str = "incoming"
STORAGE_CANONICAL: str = "canonical"
STORAGE_ARCHIVES: str = "archives"

DATA_ROOT: str = os.environ.get("VERTICE360_DATA_ROOT", (VERTICE360_ROOT / "data").as_posix())
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
DEFAULT_DATE_WINDOW_DAYS: int = 3
DEFAULT_ROUNDING_DECIMALS: int = 2

RULES_DIR: str = (PROJECT_ROOT / "rules").as_posix()
RULES_PROFILES_DIR: str = f"{RULES_DIR}/profiles"
RULES_RULESETS_DIR: str = f"{RULES_DIR}/rulesets"

# =========================
# LLM / OpenAI (compat)
# =========================
OpenAI_Key: Optional[str] = (
    os.environ.get("VERTICE360_OPENAI_KEY")
    or os.environ.get("OPENAI_API_KEY")
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
MLFLOW_TRACKING_URI: str = MLFLOW_TRACKING_URI_DEV if RUN_ENV != "prod" else MLFLOW_TRACKING_URI_PRO
MLFLOW_ENABLED: bool = os.environ.get("MLFLOW_ENABLED", "0") in ("1", "true", "True")
MLFLOW_EXPERIMENT: str = os.environ.get("MLFLOW_EXPERIMENT", "vertice360")

# =========================
# Messaging / Meta WhatsApp Cloud (Vertice360)
# =========================
META_VERTICE360_WABA_TOKEN: str = os.environ.get("META_VERTICE360_WABA_TOKEN", "")
META_VERTICE360_WABA_ID: str = os.environ.get("META_VERTICE360_WABA_ID", "")
META_VERTICE360_PHONE_NUMBER_ID: str = os.environ.get("META_VERTICE360_PHONE_NUMBER_ID", "")
META_VERTICE360_VERIFY_TOKEN: str = os.environ.get("META_VERTICE360_VERIFY_TOKEN", "")
META_APP_SECRET_IMOTORSOFT: str = os.environ.get("META_APP_SECRET_IMOTORSOFT", "")
META_GRAPH_VERSION: str = os.environ.get("META_GRAPH_VERSION", "v20.0")


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

def meta_whatsapp_enabled() -> bool:
    return bool(
        META_VERTICE360_WABA_TOKEN
        and META_VERTICE360_PHONE_NUMBER_ID
        and META_VERTICE360_VERIFY_TOKEN
    )

def boot_log() -> None:
    print(f"[{APP_NAME}] version={APP_VERSION} env={RUN_ENV} debug={DEBUG} log={LOG_LEVEL}")
    print(f"[{APP_NAME}] host={HOST} port={PORT}")
    print(f"[{APP_NAME}] db={DB_URL}")
    print(f"[{APP_NAME}] storage_provider={STORAGE_PROVIDER} local_root={STORAGE_LOCAL_ROOT}")
    print(f"[{APP_NAME}] data_root={DATA_ROOT}")
    print(f"[{APP_NAME}] rules_dir={RULES_DIR}")
    print(f"[{APP_NAME}] ai_workflow_reply={VERTICE360_AI_WORKFLOW_REPLY}")
    print(f"[{APP_NAME}] mlflow={MLFLOW_TRACKING_URI}")
    print(f"[{APP_NAME}] openai_key={mask(OpenAI_Key)} model={OpenAI_Model}")
    print(f"[{APP_NAME}] meta_phone_id={META_VERTICE360_PHONE_NUMBER_ID} meta_graph={META_GRAPH_VERSION}")
    print(
        f"[{APP_NAME}] meta_verify_token={mask(META_VERTICE360_VERIFY_TOKEN)} "
        f"meta_app_secret={mask(META_APP_SECRET_IMOTORSOFT)}"
    )
