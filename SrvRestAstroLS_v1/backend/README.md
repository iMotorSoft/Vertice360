# Vertice360 Backend

Backend service built with Litestar (Python 3.12) and managed with `uv`.

## Environment

- Python and dependencies are managed via `uv`.
- Environment variables must be set in your shell (e.g., `.bashrc`). Do **not** use `.env` files.
- Demo `vertice360-orquestador` uses `DB_PG_V360_URL` (must point to DB `v360` with `postgresql*` scheme).
- Optional fallback is disabled by default: `ALLOW_FALLBACK_V360_DB=false`.
  - Enable fallback only if you explicitly want to use `VERTICE360_DB_URL` for this demo.

## Commands

- Install dependencies: `uv sync`
- Run the server (dev): `uv run python ls_iMotorSoft_Srv01.py` (defaults to host `0.0.0.0` and port `7062` as defined in `backend/globalVar.py`)

## Structure

Routes, models, middleware, and AG-UI Vertice Flow modules are organized under `SrvRestAstroLS_v1/backend` following a clean, modular layout. Global settings live in `SrvRestAstroLS_v1/backend/globalVar.py`.

`backend/globalVar.py` centralizes app metadata, server host/port, and MLflow placeholders (read from environment variables only).
