# Demo Vertice360 Orquestador - DB v360

## Variables de entorno

Configurar en shell (`~/.bashrc` o equivalente):

```bash
export DB_PG_V360_URL="postgresql+psycopg://USER:PASS@HOST:5432/v360"
# Seguro por defecto (no fallback):
export ALLOW_FALLBACK_V360_DB=false
```

## Validaciones aplicadas en `backend/globalVar.py`

- `DB_PG_V360_URL` debe usar esquema Postgres (`postgresql`, `postgresql+psycopg` o `postgres`).
- Debe apuntar a base `v360` (`/v360` o `?dbname=v360`).
- Si falta o es inválida, se loguea `WARNING`.
- Solo se usa fallback a `VERTICE360_DB_URL` cuando `ALLOW_FALLBACK_V360_DB=true`.

## Endpoints demo

Base path:

`/api/demo/vertice360-orquestador`

Incluye:

- `GET /bootstrap`
- `GET /dashboard`
- `POST /ingest_message`
- `POST /visit/propose`
- `POST /visit/confirm`
- `POST /visit/reschedule`
- `POST /supervisor/send`
