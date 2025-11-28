# Pozo360 Backend

Backend service built with Litestar (Python 3.12) and managed with `uv`.

## Environment

- Python and dependencies are managed via `uv`.
- Environment variables must be set in your shell (e.g., `.bashrc`). Do **not** use `.env` files.

## Commands

- Install dependencies: `uv sync`
- Run the server (dev): `uv run python ls_iMotorSoft_Srv01.py` (defaults to host `0.0.0.0` and port `7062` as defined in `backend/globalVar.py`)

## Structure

Routes, models, middleware, and AG-UI Pozo Flow modules are organized under `SrvRestAstroLS_v1/backend` following a clean, modular layout. Global settings live in `SrvRestAstroLS_v1/backend/globalVar.py`.

`backend/globalVar.py` centralizes app metadata, server host/port, and MLflow placeholders (read from environment variables only).
