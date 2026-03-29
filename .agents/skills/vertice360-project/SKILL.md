---
name: vertice360-project
description: Reglas y flujo de trabajo para desarrollar Vertice360 con Codex CLI, incluyendo demos de vertice360_orquestador, workflow, AI workflow studio, AG-UI/SSE y providers de mensajeria.
---

# Vertice360

## Proposito
Vertice360 es una plataforma B2B con backend Litestar y frontend Astro/Svelte.
Los frentes principales que hoy existen en el repo son:
- `vertice360_orquestador_demo`
- `vertice360_workflow_demo`
- `vertice360_ai_workflow_demo`
- AG-UI / SSE
- mensajeria con providers Bird, Gupshup y Meta

## Ubicacion del skill
Usar esta copia del skill dentro del repo:
`.agents/skills/vertice360-project/SKILL.md`

## Raiz del proyecto
Asumir como raiz el directorio actual del repositorio Vertice360.

## Estructura relevante
- `SrvRestAstroLS_v1/backend/modules/vertice360_orquestador_demo/`
- `SrvRestAstroLS_v1/backend/modules/vertice360_workflow_demo/`
- `SrvRestAstroLS_v1/backend/modules/vertice360_ai_workflow_demo/`
- `SrvRestAstroLS_v1/backend/modules/agui_stream/`
- `SrvRestAstroLS_v1/backend/modules/agui_pozo_flow_v01/`
- `SrvRestAstroLS_v1/backend/modules/messaging/providers/gupshup/`
- `SrvRestAstroLS_v1/backend/modules/messaging/providers/meta/`
- `SrvRestAstroLS_v1/backend/modules/messaging/providers/bird/`
- `SrvRestAstroLS_v1/backend/routes/demo_vertice360_orquestador.py`
- `SrvRestAstroLS_v1/backend/routes/demo_vertice360_workflow.py`
- `SrvRestAstroLS_v1/backend/routes/demo_vertice360_ai_workflow.py`
- `SrvRestAstroLS_v1/backend/routes/messaging.py`
- `SrvRestAstroLS_v1/astro/src/components/global.js`
- `SrvRestAstroLS_v1/astro/src/lib/vertice360_orquestador/`
- `SrvRestAstroLS_v1/astro/src/lib/vertice360_workflow/`
- `SrvRestAstroLS_v1/astro/src/lib/vertice360_ai_workflow_studio/`
- `SrvRestAstroLS_v1/astro/src/components/demo/vertice360-orquestador/`
- `SrvRestAstroLS_v1/astro/src/pages/demo/vertice360-orquestador/`
- `SrvRestAstroLS_v1/astro/src/pages/demo/vertice360-workflow/`
- `SrvRestAstroLS_v1/astro/src/pages/demo/vertice360-ai-workflow-studio/`

## Reglas de trabajo
1. No inventar una estructura nueva fuera del patron actual.
2. No mezclar cambios de demos distintos salvo que el objetivo lo pida.
3. Preferir cambios chicos, claros y reversibles.
4. En backend usar flujo `uv` y respetar que las variables de entorno viven en shell, no en `.env`.
5. No romper contratos existentes de rutas demo si el frontend ya depende de ellos.
6. En frontend Astro/Svelte, reutilizar la convencion real de `SrvRestAstroLS_v1/astro/src/components/global.js` para `URL_REST` y `URL_SSE`.
7. No instalar dependencias ni ejecutar comandos destructivos salvo pedido explicito.
8. Si la validacion requiere DB, credenciales o entorno humano, dejarlo explicito.
9. Respetar `backend/globalVar.py` para metadata y configuracion base del servicio.
10. Si el cambio toca AG-UI o SSE, revisar tambien impacto en frontend y rutas relacionadas.

## Convenciones para resultados
Al terminar una tarea:
1. resumir archivos modificados
2. explicar cambios principales
3. indicar como validar manualmente
4. listar supuestos o dependencias de entorno

## Que priorizar
- primero mantener estable el backend Litestar y sus contratos
- luego demos Vertice360 funcionales
- luego integracion AG-UI/SSE
- luego refinamientos UI o tooling

## Que evitar
- mezclar refactors grandes con cambios funcionales puntuales
- duplicar clientes API si ya existe un helper en `astro/src/lib/`
- hardcodear endpoints cuando ya existe `global.js`
- introducir logica nueva sin aclarar dependencias de DB o entorno
