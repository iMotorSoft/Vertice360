# Global.js Strict Audit (Frontend Astro) - 2026-02-19

## Alcance
- Regla auditada: no hardcodear URLs en `astro/src` fuera de `astro/src/components/global.js`.
- Regla adicional: no duplicar base URL del backend para el módulo LIVE del orquestador.

## Hallazgos iniciales (antes de normalizar)
### Hardcodes de URL en `astro/src`
- `src/components/global.js:8`
  - `const URL_REST_DEV = 'http://localhost:7062';`
- `src/components/global.js:9`
  - `const URL_REST_PRO = 'https://demo.vertice360.imotorsoft.com';`
- `src/components/demo/vertice360-orquestador/Landing.svelte:5`
  - ``const waUrl = `https://wa.me/...`;``
- `src/components/demo/vertice360-orquestador/Landing.svelte:28`
  - `xmlns="http://www.w3.org/2000/svg"`
- `src/components/demo/vertice360-orquestador/OrquestadorApp.svelte:197`
  - `` `https://wa.me/...` ``
- `src/components/demo/vertice360-orquestador/OrquestadorApp.svelte:380`
  - `xmlns="http://www.w3.org/2000/svg"`
- `src/components/demo/vertice360-orquestador/OrquestadorAppLive.svelte:98`
  - `` `https://wa.me/...` ``
- `src/components/demo/vertice360-orquestador/OrquestadorAppLive.svelte:743`
  - `xmlns="http://www.w3.org/2000/svg"`
- `src/lib/vertice360_ai_workflow_studio/ui/Vertice360AiWorkflowStudioApp.svelte:173`
  - `@import url("https://fonts.googleapis.com/...Outfit...")`
- `src/lib/vertice360_workflow/ui/Vertice360WorkflowApp.svelte:108`
  - `@import url("https://fonts.googleapis.com/...Space+Grotesk...")`

### Config duplicada / señal a revisar
- `src/config/api.ts:4`
  - `export const API_BASE_URL = getRestBaseUrl();`
  - Nota: no rompe la regla por sí sola, pero no debe ser la fuente usada por el orquestador LIVE.

## Impacto
- Fragmenta la política de configuración: distintas URLs repartidas por componentes.
- Aumenta riesgo de drift entre demos/módulos al cambiar entornos.
- Dificulta enforce automático de estándares de configuración.

## Reemplazo canónico aplicado
- Source of truth: `src/components/global.js` (`getRestBaseUrl`, `URL_REST`, constantes URL comunes).
- Orquestador LIVE:
  - `src/lib/vertice360_orquestador/api.js` usa `getRestBaseUrl()` + `new URL(...)`.
  - `OrquestadorAppLive.svelte` no arma base URL; consume únicamente `api.js`.
- URLs auxiliares (`wa.me`, `xmlns`, Google Fonts) centralizadas en `global.js` y consumidas por import.

## Verificación post-normalización
- `rg -n "localhost:7062|http://localhost|https?://[^\\s'\\\"]+" src`
  - Resultado: matches solo en `src/components/global.js`.
- `rg -n "API_BASE_URL|URL_REST_DEV|URL_REST_PRO|/api/demo/vertice360-orquestador" src`
  - Resultado: el orquestador LIVE usa `src/lib/vertice360_orquestador/api.js` con `getRestBaseUrl()`; sin hardcode de host.

## Guard anti-regresión
- Script: `scripts/check_no_hardcoded_urls.mjs`
- Comando: `npm run check:globals`
- Comportamiento:
  - Escanea recursivo `src/`
  - Bloquea `localhost:7062`, `http://localhost`, `https?://...`
  - Permite excepción únicamente para `src/components/global.js`
