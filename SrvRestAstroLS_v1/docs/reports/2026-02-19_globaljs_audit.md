# Auditoría global.js y base URL (2026-02-19)

## Exports actuales
Archivo: `astro/src/components/global.js`

- `SITE_TITLE`
- `SITE_DESCRIPTION`
- `URL_REST`
- `getRestBaseUrl`
- `URL_SSE`
- `CLOUDFLARE_SITEKEY`

### Cómo calcula hoy la base REST
- Constantes internas:
  - `URL_REST_DEV = 'http://localhost:7062'`
  - `URL_REST_PRO = 'https://demo.vertice360.imotorsoft.com'`
- Export activo:
  - `URL_REST = URL_REST_DEV`
- Helper actual:
  - `getRestBaseUrl() => String(URL_REST || '').replace(/\/+$/, '')`

### Uso de runtime/env
- No usa `window`, `globalThis`, `process.env` ni `import.meta.env`.
- Es configuración estática por constantes y exports ESM.

## Patrón canonical actual en el repo
Patrón dominante para backend base URL en módulos frontend:

1. Importar desde `components/global` (`URL_REST`/`URL_SSE` o helper global).
2. Construir endpoint con esa base (ej. `const API_BASE = `${URL_REST}/api/demo/...``).
3. Evitar `API_BASE_URL` alternativo como source principal.

Referencias (archivo -> línea aproximada -> qué hace):
- `astro/src/lib/crm/api.js:1` -> importa `URL_REST` desde `components/global`.
- `astro/src/lib/vertice360_workflow/api.js:1` -> importa `URL_REST` desde `components/global`.
- `astro/src/lib/vertice360_ai_workflow_studio/api.js:1` -> importa `URL_REST` desde `components/global.js`.
- `astro/src/lib/vertice360_ai_workflow_studio/sse.js:1` -> importa `URL_SSE` desde `components/global.js`.
- `astro/src/lib/vertice360_orquestador/api.js:1` -> importa `getRestBaseUrl` desde `components/global.js`.

## Hardcodes detectados
Búsqueda ejecutada:
- `rg -n "localhost:7062|API_BASE_URL|http://localhost|/api/demo/" astro/src`

### Hallazgos relevantes de base URL
- `astro/src/components/global.js:8` -> `URL_REST_DEV` hardcodeado a `http://localhost:7062` (esperado como configuración dev central).
- `astro/src/config/api.ts:1` -> `API_BASE_URL = "http://localhost:7062"` (fuente alternativa; no canonical).
- `astro/src/components/demo/sse_test/SseTestCard.svelte:19` -> `SSE_URL` hardcodeado absoluto (`http://localhost:7062/...`).

### Hallazgos de endpoints hardcodeados por path (`/api/demo/...`)
- `astro/src/components/demo/codex/*` (llamadas fetch con `/api/demo/codex/...` sobre `URL_REST`).
- `astro/src/components/demo/messaging/providers/*` (paths `/api/demo/messaging/...`).
- `astro/src/components/demo/antigravity/*` (fetch directo con path relativo `/api/demo/ag/...`).
- `astro/src/lib/crm/api.js` (paths `/api/demo/crm/...`).
- `astro/src/lib/vertice360_workflow/api.js` y `astro/src/lib/vertice360_ai_workflow_studio/api.js` (paths `/api/demo/...`).
- `astro/src/lib/vertice360_orquestador/api.js` (prefix `/api/demo/vertice360-orquestador`).

Nota: no todo `/api/demo/...` es problema de consistencia; el punto crítico es la fuente del host/base URL. El patrón canonical vigente en el repo es `components/global.js`.
