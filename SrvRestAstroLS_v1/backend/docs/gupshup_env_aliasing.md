# Gupshup Env Aliasing (Canonical Pattern)

Fecha: 2026-02-22

## Objetivo
Usar un unico set de variables canónicas en runtime Python:

- `GUPSHUP_APP_NAME`
- `GUPSHUP_API_KEY`
- `GUPSHUP_WA_SENDER`

Y resolver el alias por entorno fuera del codigo (bashrc/scripts), usando `*_DEV`/`*_PRO`.

## Auditoría actual del backend

### 1) `globalVar.py`
Variables canónicas usadas por runtime/provider:

- `GUPSHUP_APP_NAME`
- `GUPSHUP_API_KEY`
- `GUPSHUP_WA_SENDER`
- `GUPSHUP_BASE_URL`

Flags derivados:

- `gupshup_provider_requested()` -> `bool(GUPSHUP_APP_NAME and GUPSHUP_API_KEY)`
- `gupshup_whatsapp_enabled()` -> `bool(gupshup_provider_requested() and get_gupshup_wa_sender_provider_value())`

Normalizacion sender:

- `normalize_phone_e164()` acepta `14386196758` o `+14386196758`
- `get_gupshup_wa_sender_e164()` expone siempre `+<digits>`
- `get_gupshup_wa_sender_provider_value()` expone `digits` para wire format

### 2) Provider Gupshup
Archivo: `modules/messaging/providers/gupshup/whatsapp/client.py`

`GupshupConfig.from_env()` consume:

- `globalVar.GUPSHUP_BASE_URL`
- `globalVar.GUPSHUP_API_KEY`
- `globalVar.GUPSHUP_APP_NAME`
- `globalVar.get_gupshup_wa_sender_e164()`
- `globalVar.get_gupshup_wa_sender_provider_value()`

No usa `*_DEV/*_PRO` directo.

## Mapping recomendado (afuera del codigo)

### Regla

- `GUPSHUP_APP_NAME = GUPSHUP_APP_NAME_DEV` o `_PRO`
- `GUPSHUP_API_KEY = GUPSHUP_API_KEY_DEV` o `_PRO`
- `GUPSHUP_WA_SENDER = GUPSHUP_SRC_NUMBER_DEV` o `_PRO`

## Ejemplo para `.bashrc`

```bash
# Elegi entorno
export VERTICE360_ENV="dev"  # dev|prod

if [ "$VERTICE360_ENV" = "dev" ]; then
  export GUPSHUP_APP_NAME="$GUPSHUP_APP_NAME_DEV"
  export GUPSHUP_API_KEY="$GUPSHUP_API_KEY_DEV"
  export GUPSHUP_WA_SENDER="$GUPSHUP_SRC_NUMBER_DEV"
elif [ "$VERTICE360_ENV" = "prod" ]; then
  export GUPSHUP_APP_NAME="$GUPSHUP_APP_NAME_PRO"
  export GUPSHUP_API_KEY="$GUPSHUP_API_KEY_PRO"
  export GUPSHUP_WA_SENDER="$GUPSHUP_SRC_NUMBER_PRO"
fi
```

## Ejemplo para `scripts/run_demo_dev.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

export VERTICE360_ENV="dev"

# Alias canónico (dev -> canonical)
export GUPSHUP_APP_NAME="${GUPSHUP_APP_NAME_DEV:-}"
export GUPSHUP_API_KEY="${GUPSHUP_API_KEY_DEV:-}"
export GUPSHUP_WA_SENDER="${GUPSHUP_SRC_NUMBER_DEV:-}"

# Arranque demo
exec python -m backend.ls_iMotorSoft_Srv01_demo
```

## Validacion esperada en boot log

Con canónicas correctamente seteadas:

- `gupshup_app=<app>`
- `gupshup_sender=+<digits>`
- `gupshup_enabled=True`

Sin imprimir secretos (`api key` nunca se loguea).
