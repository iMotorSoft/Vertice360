# Runbook de Produccion Vertice360

Fecha/Hora de creacion (local): 2026-03-06 12:18:25 -03
Fecha/Hora de creacion (UTC): 2026-03-06 15:18:26Z
Estado: borrador operativo inicial (actualizable)

## Objetivo
Dejar un procedimiento manual y repetible para pasar de entorno dev a produccion,
con foco en:
- Configuracion de variables en VM (`~/.bashrc`).
- Build frontend Astro.
- Copia de `dist` al servidor de produccion.
- Copia de backend al servidor de produccion.
- Validaciones posteriores al deploy.

## 1) Variables de entorno en VM de produccion (`~/.bashrc`)

Agregar/ajustar este bloque:

```bash
# ===== Vertice360 backend (prod) =====
export VERTICE360_ENV="prod"
export VERTICE360_HOST="0.0.0.0"
export VERTICE360_PORT="7062"
export VERTICE360_UVICORN_WORKERS="2"

# URL publica backend/demo
export VERTICE360_PUBLIC_BASE_URL_PRO="https://demo.vertice360.imotorsoft.com"

# CORS frontend permitido
export VERTICE360_FE_URL_LOCAL="https://demo.vertice360.imotorsoft.com"
export VERTICE360_FE_URL_IP="https://demo.vertice360.imotorsoft.com"

# DB principal + DB v360 (obligatoria para orquestador live)
export VERTICE360_DB_URL="postgresql+psycopg://USER:PASS@HOST:5432/vertice360"
export DB_PG_V360_URL="postgresql+psycopg://USER:PASS@HOST:5432/v360"
export ALLOW_FALLBACK_V360_DB="false"

# Seguridad
export VERTICE360_JWT_SECRET="CAMBIAR_ESTE_SECRET_EN_PROD"
export V360_ADMIN_TOKEN="TOKEN_ADMIN_LARGO_Y_ALEATORIO"

# ===== Gupshup (si aplica) =====
export GUPSHUP_APP_NAME_PRO="vertice360pro"
export GUPSHUP_API_KEY_PRO="TU_API_KEY_PROD"
export GUPSHUP_SRC_NUMBER_PRO="54911XXXXXXXX"
export GUPSHUP_BASE_URL_PRO="https://api.gupshup.io"

# Alias canonico runtime
export GUPSHUP_APP_NAME="$GUPSHUP_APP_NAME_PRO"
export GUPSHUP_API_KEY="$GUPSHUP_API_KEY_PRO"
export GUPSHUP_WA_SENDER="$GUPSHUP_SRC_NUMBER_PRO"

# ===== Meta WhatsApp (si aplica) =====
export META_VERTICE360_WABA_TOKEN="..."
export META_VERTICE360_WABA_ID="..."
export META_VERTICE360_PHONE_NUMBER_ID="..."
export META_VERTICE360_VERIFY_TOKEN="..."
export META_APP_SECRET_IMOTORSOFT="..."
export META_GRAPH_VERSION="v20.0"

# ===== OpenAI (si aplica) =====
export VERTICE360_OPENAI_KEY="..."
export VERTICE360_OPENAI_MODEL="gpt-4o-mini"
```

Aplicar cambios:

```bash
source ~/.bashrc
```

## 2) Paso manual obligatorio en frontend (Astro)

Archivo:
- `astro/src/components/global.js`

Cambio manual previo a build:

```js
export const URL_REST = URL_REST_PRO;
```

Contexto:
- Hoy suele estar en `URL_REST_DEV`.
- Si no se cambia, frontend en produccion puede seguir pegando a backend local/dev.

## 3) Build de frontend (Astro)

Desde `SrvRestAstroLS_v1/astro`:

```bash
npm ci
npm run build
```

Salida esperada:
- Carpeta `astro/dist/` generada.
- Sin errores de compilacion.

## 4) Copia de frontend `dist` al servidor de produccion

Definir placeholders (reemplazar):

```bash
export PROD_HOST="TU_HOST_PROD"
export PROD_USER="TU_USUARIO"
export PROD_FE_PATH="/var/www/vertice360"
```

### Opcion recomendada: `rsync`

```bash
rsync -avz --delete \
  /media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/Vertice360/SrvRestAstroLS_v1/astro/dist/ \
  ${PROD_USER}@${PROD_HOST}:${PROD_FE_PATH}/
```

### Opcion simple: `scp`

```bash
scp -r \
  /media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/Vertice360/SrvRestAstroLS_v1/astro/dist/* \
  ${PROD_USER}@${PROD_HOST}:${PROD_FE_PATH}/
```

## 5) Copia de backend al servidor de produccion

Definir path destino backend:

```bash
export PROD_BE_PATH="/opt/vertice360/backend"
```

### Opcion recomendada: `rsync` (sin basura local)

```bash
rsync -avz --delete \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude '.ruff_cache' \
  --exclude 'tests' \
  /media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/Vertice360/SrvRestAstroLS_v1/backend/ \
  ${PROD_USER}@${PROD_HOST}:${PROD_BE_PATH}/
```

### Opcion alternativa: `scp`

```bash
scp -r \
  /media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/Vertice360/SrvRestAstroLS_v1/backend/* \
  ${PROD_USER}@${PROD_HOST}:${PROD_BE_PATH}/
```

Nota:
- `scp` no borra archivos viejos en destino.
- `rsync --delete` mantiene destino espejo.

## 6) Reinicio de servicios en produccion (manual)

Ejemplo (ajustar nombres reales):

```bash
ssh ${PROD_USER}@${PROD_HOST}

# backend
sudo systemctl restart vertice360-backend
sudo systemctl status vertice360-backend --no-pager

# frontend (si se sirve por nginx)
sudo systemctl reload nginx
sudo systemctl status nginx --no-pager
```

## 7) Validaciones post-deploy

## 7.1 Backend

```bash
curl -fsS https://demo.vertice360.imotorsoft.com/health
curl -fsS https://demo.vertice360.imotorsoft.com/version
```

Validar log de arranque:
- `env=prod`
- `db_v360_valid=True` o warning controlado
- `gupshup_enabled` segun configuracion

## 7.2 Frontend

Abrir en navegador:
- `https://demo.vertice360.imotorsoft.com/demo/vertice360-orquestador/`

Confirmar:
- Carga landing.
- Con `?cliente=...` abre app live.
- SSE activa (badge Live/Reconexion y actualizacion de conversaciones).

## 7.3 Endpoints live orquestador

```bash
curl -fsS "https://demo.vertice360.imotorsoft.com/api/demo/vertice360-orquestador/bootstrap?cliente=5491100000000"
curl -fsS "https://demo.vertice360.imotorsoft.com/api/demo/vertice360-orquestador/dashboard?cliente=5491100000000"
```

## 8) Checklist corto de release

- [ ] `global.js` en `URL_REST_PRO`.
- [ ] `npm run build` OK.
- [ ] `~/.bashrc` de VM actualizado y recargado.
- [ ] `DB_PG_V360_URL` apunta a DB `v360`.
- [ ] Backend copiado (rsync/scp).
- [ ] Frontend `dist` copiado (rsync/scp).
- [ ] Servicios reiniciados.
- [ ] Health checks OK.
- [ ] Prueba funcional orquestador OK.

## 9) Puntos importantes para futuras actualizaciones

Cada vez que se actualice este documento, registrar:
- Fecha/hora local + UTC.
- Commit/tag desplegado (frontend y backend).
- Variables cambiadas en produccion.
- Resultado de validaciones (OK/NO OK).
- Incidentes y rollback si aplica.

## 10) Registro de cambios del documento

- 2026-03-06 12:18:25 -03 (2026-03-06 15:18:26Z): creacion inicial.
