# Vertice360 Orquestador Demo — Documento Único (Informe + Config Canónica)

Fecha: 2026-02-28 (AR)  
Stack: **Backend Litestar (Python)** + **Postgres v360** + **Gupshup WhatsApp** + **Astro + Svelte 5 + DaisyUI**  
Objetivo: Demo end-to-end **“Del anuncio al cierre”** con trazabilidad total y posibilidad de intervención humana.

---

## 0) Propósito del producto / demo

Vertice360 Orquestador Demo muestra un flujo comercial completo:

1. Un lead llega desde una **publicidad** y escribe al WhatsApp de la desarrolladora (número demo).
2. El backend **ingesta** el mensaje (webhook Gupshup), lo **persiste** en Postgres v360 y responde con **“Vera”** (humana, sin decir bot/AI).
3. El tablero LIVE (Astro/Svelte) muestra **KPIs**, **tickets**, **timeline** y permite **intervención humana**:
   - enviar mensajes reales al lead,
   - proponer/confirmar/reagendar visita,
   - dejar todo auditable para analítica/RAG.

> Clave comercial: “Vera” se percibe como **atención humana**. La IA puede ayudar detrás, pero no se explicita.

---

## 1) Arquitectura general

### 1.1 Backend (Litestar)
- Entrypoint demo: `backend/ls_iMotorSoft_Srv01_demo.py`
- Webhook Gupshup: `backend/routes/messaging.py`
- Router Orquestador: `backend/routes/demo_vertice360_orquestador.py`
- Dominio Orquestador: `backend/modules/vertice360_orquestador_demo/{services.py,repo.py,db.py,schemas.py}`
- Tests: `backend/tests/test_*orquestador*.py`
- Pool DB: `psycopg_pool open=False` con lifecycle startup/shutdown (ya implementado)

### 1.2 Frontend (Astro + Svelte 5)
- Ruta LIVE (real): `/demo/vertice360-orquestador/`
- Ruta UX mock (wireframe): `/demo/vertice360-orquestador/ux`
- Mobile-first con DaisyUI + Tailwind
- SSE/AG-UI: consume `URL_SSE = {REST_BASE}/api/agui/stream` con reconexión/backoff

### 1.3 Base de datos (Postgres v360)
Persistencia para trazabilidad + analítica/RAG:
- leads
- conversations
- tickets
- messages (IN/OUT)
- events
- (y entidades de visita si corresponde)

---

## 2) Pipeline WhatsApp (Gupshup) — end-to-end

### 2.1 Inbound
1) Inbound entra por webhook:
- `POST /webhooks/messaging/gupshup/whatsapp`

2) Router hard-route:
- `event_type=message` ⇒ SIEMPRE Orquestador (no workflow demo)

3) Persistencia:
- Crear/actualizar lead
- Crear conversation/ticket
- Insertar message IN
- Insertar event(s)

### 2.2 Respuesta “Vera”
- Onboarding conversacional:
  - entrega link a tablero
  - “dos opciones” + cierre humano
- Si detecta `project_code`:
  - pide requisitos faltantes
- Parsing + completitud:
  - `parse_ambientes` (mono/1/2/3/4, variantes)
  - `parse_budget_currency` (k/m, separadores, USD/ARS: u$s/usd/dólar/pesos)
- Persiste requirements en JSONB:
  - `summary_jsonb.requirements { ambientes, presupuesto, moneda }`
- Si requirements completos:
  - responde resumen humano (NO pide horarios)
  - stage ⇒ `Pendiente de visita`
  - events:
    - `orq.requirements.captured`
    - `orq.stage.updated`

---

## 3) Tablero LIVE — comportamiento esperado

### 3.1 Bootstrap (ejemplos de publicidad)
- `GET /api/demo/vertice360-orquestador/bootstrap`
  - devuelve `whatsapp_demo_phone`, `projects`, `marketing_assets`, `users`

El botón “Enviar WhatsApp” abre:
- `wa.me` / `api.whatsapp.com/send`
- `to=<demo_phone_digits>`
- `text="Hola, vengo por un anuncio..." + project_code`

### 3.2 Dashboard (datos reales)
- `GET /api/demo/vertice360-orquestador/dashboard?cliente=...`
  - `kpis`
  - `tickets` reales
  - `cliente_activo`
  - ideal: `last_message_text` + `last_message_at`

### 3.3 Refresco por SSE/AG-UI (regla)
Al recibir eventos relacionados a:
- `orq.*`, `ticket.*`, `messaging.*`, `visit.*`

Entonces UI:
- ejecuta `refetchDashboard()` con debounce (ej. 250–400ms)
- conserva botón “Actualizar” manual
- mantiene reconexión SSE con backoff

> Recomendación: filtrar por `cliente`/`lead_phone` si el evento trae contexto, para evitar refetch innecesario.

---

## 4) Endpoints Orquestador (Backend)

Base path:
- `/api/demo/vertice360-orquestador`

### 4.1 Lectura
- `GET  /bootstrap`
- `GET  /dashboard?cliente=...`

### 4.2 Escritura / Operación
- `POST /ingest_message`
- `POST /visit/propose`
- `POST /visit/confirm`
- `POST /visit/reschedule`

### 4.3 Intervención humana (clave comercial)
- `POST /supervisor/send`
  - debe: persistir OUT + enviar **REAL** por provider (Gupshup) + persistir provider status

### 4.4 Admin (DEV)
- `POST /admin/reset_phone` (header `x-v360-admin-token`)
  - reset de data asociada a phone para re-demo

---

## 5) Configuración canónica — reglas de oro

### 5.1 Single Source of Truth
- Backend: **solo** `backend/globalVar.py` puede leer env vars (`os.environ.get`).
- Frontend: **solo** `astro/src/components/global.js` define REST base URL y SSE.

✅ Permitido: `from globalVar import X`  
❌ Prohibido: leer env vars fuera de `globalVar.py`  
❌ Prohibido: hardcodear secretos en logs

---

## 6) Configuración Backend — `backend/globalVar.py` (Directivas)

Este archivo es **la autoridad** de configuración. Incluye:
- normalización del environment (`dev|stg|prod`)
- host/port
- CORS origins
- paths de storage/data/rules
- DB URLs con **validación estricta** para v360
- llaves de providers (Meta y Gupshup)
- helpers: normalización de teléfono, validación DB, masking de secretos, boot_log

### 6.1 Variables principales (documentación)

#### App / Environment
- `VERTICE360_APP_VERSION` → `APP_VERSION` (default `0.1.0`)
- `VERTICE360_ENV` → `ENVIRONMENT/RUN_ENV` (default `dev`, normalizado a `dev|stg|prod`)
- `DEBUG` (true si no es prod)
- `LOG_LEVEL` (`DEBUG` en no-prod, `INFO` en prod)

#### API server
- `VERTICE360_HOST` → `HOST` (default `0.0.0.0`)
- `VERTICE360_PORT` → `PORT` (default `7062`)
- `VERTICE360_UVICORN_WORKERS` → `UVICORN_WORKERS` (mínimo 1)

#### Frontend / CORS
- `VERTICE360_FE_URL_LOCAL` (default `http://localhost:3062`)
- `VERTICE360_FE_URL_IP` (default `http://127.0.0.1:3062`)
- Se agregan a `FRONTEND_ORIGINS`

#### Public base URL (para links externos)
- `VERTICE360_PUBLIC_BASE_URL_PRO` (default `https://demo.pozo360.imotorsoft.com`)
- `VERTICE360_PUBLIC_BASE_URL_DEV` (hardcoded cloudflare tunnel)
- `VERTICE360_PUBLIC_BASE_URL` (hoy: seteado a PRO por defecto)

> Sugerencia: en el futuro, hacer `VERTICE360_PUBLIC_BASE_URL = _pick_env(dev, stg, prod)` para que el entorno gobierne automáticamente.

#### Project / storage / data
- `VERTICE360_STORAGE_PROVIDER` (`local|s3`, default `local`)
- `VERTICE360_STORAGE_LOCAL_ROOT` (default `{backend_root}/storage`)
- `VERTICE360_DATA_ROOT` (default `{backend_root}/data`)
- `RULES_DIR` (default `{project_root}/rules`)

Helpers:
- `resolve_storage_uri(kind, account_id, period, filename)`
- `ensure_local_dirs()`

#### Database (dos planos)
**DB general (plataforma):**
- `VERTICE360_DB_URL` → `DB_URL` (default `postgresql+psycopg://user:pass@localhost:5432/vertice360`)
- `VERTICE360_DB_SCHEMA` → `DB_SCHEMA` (default `public`)

**DB crítica del demo Orquestador (v360):**
- `DB_PG_V360_URL` (requerida; se valida que el DB sea `v360`)
- `ALLOW_FALLBACK_V360_DB` (default false)
  - si true, habilita fallback a `VERTICE360_DB_URL` (pero también exige que el DB sea `v360`)
- Helper canónico:
  - `get_v360_db_url()`  
    - valida `DB_PG_V360_URL`
    - si falta o es inválida:
      - si `ALLOW_FALLBACK_V360_DB=false` → **RuntimeError**
      - si true → valida `DB_URL` y lo usa como fallback

#### Admin
- `V360_ADMIN_TOKEN` (header `x-v360-admin-token`)
- `V360_DEMO_BOARD_BASE_URL` (default `http://localhost:3062/demo/vertice360-orquestador/`)

#### LLM / OpenAI (compat)
- `VERTICE360_OPENAI_KEY` o `OPENAI_API_KEY` → `OpenAI_Key`
- `VERTICE360_OPENAI_MODEL` → `OpenAI_Model` (default `gpt-4o-mini`)

#### MLflow (opcional)
- `VERTICE360_MLFLOW_TRACKING_URI_DEV` (default file://.../mlruns_vertice360)
- `VERTICE360_MLFLOW_TRACKING_URI_PRO` (default: dev)
- `MLFLOW_ENABLED` (`1|true|True`)
- `MLFLOW_EXPERIMENT` (default `vertice360`)

#### Messaging: Meta WhatsApp Cloud (preparado)
- `META_VERTICE360_WABA_TOKEN`
- `META_VERTICE360_WABA_ID`
- `META_VERTICE360_PHONE_NUMBER_ID`
- `META_VERTICE360_VERIFY_TOKEN`
- `META_APP_SECRET_IMOTORSOFT`
- `META_GRAPH_VERSION` (default `v20.0`)
Helper:
- `meta_whatsapp_enabled()`

#### Messaging: Gupshup WhatsApp (activo en demo)
Base:
- `DEFAULT_GUPSHUP_BASE_URL = https://api.gupshup.io`

Variables por entorno (dev/stg/pro):
- `GUPSHUP_APP_NAME_DEV`, `GUPSHUP_APP_NAME_STG`, `GUPSHUP_APP_NAME_PRO`
- `GUPSHUP_API_KEY_DEV`, `GUPSHUP_API_KEY_STG`, `GUPSHUP_API_KEY_PRO`
- `GUPSHUP_BASE_URL_DEV`, `GUPSHUP_BASE_URL_STG`, `GUPSHUP_BASE_URL_PRO`
- Fuente (legacy):
  - `GUPSHUP_SRC_NUMBER_DEV/PRO/STG` (ojo: **NO es el sender canónico**)

Selección automática por entorno:
- `GUPSHUP_APP_NAME = _pick_env(dev, stg, prod)`
- `GUPSHUP_API_KEY = _pick_env(dev, stg, prod)`
- `GUPSHUP_BASE_URL = _pick_env(dev, stg, prod)`

**Sender canónico (single source of truth):**
- `GUPSHUP_WA_SENDER` se toma de env `GUPSHUP_WA_SENDER` y se normaliza a E.164 con:
  - `normalize_phone_e164()`

Compat:
- `GUPSHUP_SRC_NUMBER = digits-only` (derivado de `GUPSHUP_WA_SENDER`)

Helpers:
- `get_gupshup_wa_sender_e164()` (para logs/payloads internos)
- `get_gupshup_wa_sender_provider_value()` (digits-only wire format)
- `gupshup_provider_requested()` (app+key)
- `gupshup_whatsapp_enabled()` (app+key+sender)

> Regla: **Outbound real debe depender de `gupshup_whatsapp_enabled()`**.  
> Si app/key existen pero falta sender, globalVar ya loggea WARNING.

### 6.2 Boot log (importante para demos)
`boot_log()` imprime:
- env, host/port, workers
- db config (incluye validación v360)
- si admin token está seteado
- storage paths
- mode inbound_router=orquestador
- MLflow/OpenAI (masked)
- Meta config (masked)
- Gupshup config + enabled

✅ Esto permite diagnosticar demo en 10 segundos sin mirar código.

---

## 7) Configuración Frontend — `astro/src/components/global.js` (Directivas)

Este archivo es la única fuente de verdad para:
- REST base URL
- SSE URL
- URLs auxiliares (wa.me, api.whatsapp.com, fuentes, etc.)
- Cloudflare sitekey (pendiente de completar)

### 7.1 Variables y contratos

REST:
- `URL_REST_DEV = http://localhost:7062`
- `URL_REST_PRO = https://demo.vertice360.imotorsoft.com`
- `URL_REST = URL_REST_DEV` (switch manual a PRO)

Helper:
- `getRestBaseUrl()` (normaliza: sin trailing slashes)

SSE:
- `URL_SSE = {getRestBaseUrl()}/api/agui/stream`

Constantes:
- `URL_WA_ME = https://wa.me`
- `URL_WA_API = https://api.whatsapp.com/send`
- (y otras de fonts/svg)

Cloudflare:
- `CLOUDFLARE_SITEKEY_DEV = <pendiente>`
- `CLOUDFLARE_SITEKEY_PRO = <pendiente>`
- `CLOUDFLARE_SITEKEY = CLOUDFLARE_SITEKEY_DEV`

### 7.2 Guardrails frontend
- ❌ No hardcodear URLs REST/SSE fuera de `global.js`
- ✅ Todos los fetches deben construir endpoints desde `getRestBaseUrl()`
- ✅ SSE siempre desde `URL_SSE` (no duplicar)

> Sugerencia: exportar funciones tipo `apiBootstrap()`, `apiDashboard(cliente)`, `apiSupervisorSend()` para eliminar strings repetidos.

---

## 8) Operación local (comandos canónicos)

Backend:
```bash
cd backend
source .venv/bin/activate
python ls_iMotorSoft_Srv01_demo.py
