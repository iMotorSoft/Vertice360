from __future__ import annotations

import logging
from contextlib import contextmanager
from threading import Lock
from typing import Any, Callable, Iterator, TypeVar

from backend import globalVar

try:
    import psycopg  # type: ignore
except ImportError:  # pragma: no cover - depends on runtime env
    psycopg = None

try:
    from psycopg_pool import ConnectionPool  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    ConnectionPool = None


logger = logging.getLogger(__name__)

T = TypeVar("T")

_pool: Any | None = None
_pool_lock = Lock()


def psycopg_available() -> bool:
    return psycopg is not None


def _normalize_conninfo(url: str) -> str:
    candidate = str(url or "").strip()
    if candidate.startswith("postgresql+psycopg://"):
        return "postgresql://" + candidate[len("postgresql+psycopg://") :]
    return candidate


def _get_conninfo() -> str:
    return _normalize_conninfo(globalVar.get_v360_db_url())


def _get_pool() -> Any | None:
    if ConnectionPool is None:
        return None

    global _pool
    if _pool is not None:
        return _pool

    with _pool_lock:
        if _pool is not None:
            return _pool
        conninfo = _get_conninfo()
        min_size = globalVar.get_env_int("V360_DB_POOL_MIN_SIZE", 1, minimum=1)
        max_size = globalVar.get_env_int("V360_DB_POOL_MAX_SIZE", 4, minimum=min_size)
        _pool = ConnectionPool(
            conninfo=conninfo,
            min_size=min_size,
            max_size=max_size,
            kwargs={"autocommit": False},
        )
        logger.info("V360_DB_POOL initialized min_size=%s max_size=%s", min_size, max_size)
    return _pool


@contextmanager
def get_connection() -> Iterator[Any]:
    if psycopg is None:
        raise RuntimeError(
            "psycopg is required for vertice360-orquestador demo. "
            "Install with: uv add psycopg[binary]"
        )

    pool = _get_pool()
    if pool is not None:
        with pool.connection() as conn:
            yield conn
        return

    conninfo = _get_conninfo()
    with psycopg.connect(conninfo, autocommit=False) as conn:
        yield conn


def run_in_transaction(callback: Callable[[Any], T]) -> T:
    with get_connection() as conn:
        try:
            result = callback(conn)
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise


def can_connect() -> bool:
    if not psycopg_available():
        return False
    try:
        with get_connection() as conn:
            conn.execute("select 1")
        return True
    except Exception as exc:  # pragma: no cover - environment-dependent
        logger.warning("V360_DB_CONNECTIVITY_FAILED error=%s", exc)
        return False
