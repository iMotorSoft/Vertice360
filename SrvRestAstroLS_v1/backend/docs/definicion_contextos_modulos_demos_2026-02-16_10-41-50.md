# Definicion y Contextos para Modulos Nuevos y Demos

Fecha: 2026-02-16 10:41:50
Alcance: `backend` + integracion con `astro` (AG-UI, SSE, mobile-first)

## 0) Tooling del proyecto (acordado)

- Package manager frontend: `pnpm`
- Build frontend: `bun`

Comandos de referencia en `astro/`:

- Instalar dependencias: `pnpm install`
- Desarrollo local: `pnpm dev`
- Build: `bun run build`

## 1) Objetivo

Definir una base tecnica estable para crear modulos/demos nuevos sin romper funcionalidades existentes, reutilizando estructura actual, con telemetria y tests aislados desde el inicio.

## 2) Archivos base analizados

- Backend config: `backend/globalVar.py`
- Backend demo entrypoint: `backend/ls_iMotorSoft_Srv01_demo.py`
- Backend prod entrypoint: `backend/ls_iMotorSoft_Srv01.py`
- Astro config global: `astro/src/components/global.js`
- AG-UI stream: `backend/modules/agui_stream/*`
- Workflow demo: `backend/modules/vertice360_workflow_demo/*`, `backend/routes/demo_vertice360_workflow.py`
- AI workflow demo: `backend/modules/vertice360_ai_workflow_demo/*`, `backend/routes/demo_vertice360_ai_workflow.py`
- Messaging/webhooks: `backend/routes/messaging.py`, `backend/modules/messaging/*`
- CRM demo: `backend/modules/crm_demo/*`
- Telemetria y MLflow: `backend/middleware/telemetry_middleware.py`, `backend/telemetry/*`, `backend/ml/mlflow_client.py`
- Testing base: `backend/tests/conftest.py` y smoke tests de workflow

### 2.1) Estructura de directorios (referencia actual)

```text
Vertice360/SrvRestAstroLS_v1/
├── backend/                               # Backend Python (Litestar)
│   ├── globalVar.py                       # Config centralizada
│   ├── ls_iMotorSoft_Srv01.py             # Entrypoint base/prod
│   ├── ls_iMotorSoft_Srv01_demo.py        # Entrypoint demo
│   ├── db/                                # Datos/mocks demo
│   ├── docs/                              # Documentacion tecnica backend
│   ├── middleware/                        # Tenant + telemetry middleware
│   ├── ml/                                # Cliente MLflow
│   ├── models/                            # Modelos comunes
│   ├── modules/                           # Dominios de negocio
│   │   ├── agui_stream/                   # Stream SSE global AG-UI
│   │   ├── agui_pozo_flow_v01/            # Flujo AG-UI pozo (v1)
│   │   ├── crm_demo/                      # Demo CRM
│   │   ├── demo_ag_vertice360/            # Demo antigravity
│   │   ├── messaging/                     # Proveedores + webhooks
│   │   ├── vertice360_workflow_demo/      # Workflow operativo
│   │   └── vertice360_ai_workflow_demo/   # Workflow AI studio
│   ├── routes/                            # Routers HTTP
│   ├── scripts/                           # Scripts operativos/diagnostico
│   ├── services/                          # Servicios compartidos
│   ├── telemetry/                         # Logging, context, metrics, tracing
│   └── tests/                             # Tests de regresion/integracion
├── astro/                                 # Frontend Astro + Svelte 5
│   ├── src/
│   │   ├── components/                    # UI compartida + demos
│   │   │   └── demo/
│   │   │       ├── antigravity/
│   │   │       ├── codex/
│   │   │       ├── crm/
│   │   │       ├── messaging/
│   │   │       ├── sse_test/
│   │   │       └── vertice360-orquestador/
│   │   ├── config/                        # Config frontend
│   │   ├── layouts/                       # Layouts Astro
│   │   ├── lib/                           # Estado/API/SSE por dominio
│   │   │   ├── crm/
│   │   │   ├── messaging/
│   │   │   ├── vertice360_workflow/
│   │   │   └── vertice360_ai_workflow_studio/
│   │   ├── pages/
│   │   │   └── demo/
│   │   │       ├── antigravity/
│   │   │       ├── codex/
│   │   │       ├── crm/
│   │   │       ├── messaging/
│   │   │       ├── sse-test/
│   │   │       ├── vertice360-ai-workflow-studio/
│   │   │       ├── vertice360-orquestador/
│   │   │       └── vertice360-workflow/
│   │   └── styles/
│   ├── public/
│   └── package.json
├── doc/                                   # Documentacion funcional/proyecto
└── scripts/                               # Scripts auxiliares del workspace
```

Regla de mantenimiento:

- Cuando se cree un modulo nuevo, actualizar primero esta seccion para mantener contexto comun del equipo.

### 2.2) Prompt reutilizable para actualizar esta seccion

Usar este prompt en Codex/CLI cuando quieras refrescar la estructura del proyecto en este documento:

```text
Actualiza la seccion "2.1) Estructura de directorios (referencia actual)" del archivo:
backend/docs/definicion_contextos_modulos_demos_2026-02-16_10-41-50.md

Objetivo:
- Reflejar la estructura REAL actual de directorios del workspace Vertice360/SrvRestAstroLS_v1.
- Mantener formato arbol tipo markdown (bloque ```text```).
- Incluir solo directorios relevantes para arquitectura (backend, astro, doc, scripts y subcarpetas funcionales).
- No listar carpetas de ruido tecnico salvo que aporten contexto (ej: .venv, node_modules solo si se decide explicitar).

Reglas:
- No cambiar otras secciones del documento.
- Mantener comentarios cortos al final de cada ruta clave.
- Si existe una carpeta nueva de dominio, agregarla en el arbol y en comentario funcional.
- Conservar la "Regla de mantenimiento".

Pasos sugeridos:
1) Relevar directorios con find/rg en:
   - ../ (maxdepth 2)
   - ../astro/src (maxdepth 3)
   - ../backend/modules (maxdepth 2)
2) Comparar contra el arbol actual del documento.
3) Editar solo la seccion 2.1.
4) Dejar el archivo listo sin tocar codigo fuente.
```

## 3) Lo que ya funciona bien (base a preservar)

- Patron modular por dominio en `backend/modules/*` con separacion `services`, `store`, `events`.
- Contrato de eventos AG-UI consistente en workflow (`type`, `name`, `timestamp`, `value`, `correlationId`).
- SSE global centralizado en `backend/modules/agui_stream` con reconexion en frontend.
- Demos funcionales separadas por router (`/api/demo/...`) y stores in-memory para iteracion rapida.
- Buen set de tests de regresion para workflow/messaging.

## 4) Riesgos tecnicos actuales (a gestionar en nuevos modulos)

- `astro/src/components/global.js` queda hardcodeado a `URL_REST_DEV`, riesgo de errores al pasar a remoto.
- `backend/ml/mlflow_client.py` esta listo pero casi no se usa en flujos reales (telemetria ML incompleta).
- En `routes/messaging.py` conviven varias responsabilidades (envio, webhooks, workflow bridge); cualquier cambio debe ser incremental y con tests.
- Stores demo in-memory (workflow/CRM/AI runs) no son persistentes; para demo esta bien, pero exige tests fuertes para evitar regresiones.

## 5) Contextos canonicos para crecimiento

### 5.1 Contexto Configuracion

- Backend: toda config nueva debe entrar primero por `globalVar.py`.
- Frontend: no hardcodear URLs por modulo; consumir desde `components/global.js` o equivalente central.
- Regla: cada feature flag o credencial nueva tiene default seguro + helper de validacion.

### 5.2 Contexto Runtime de App

- Demo runtime: `ls_iMotorSoft_Srv01_demo.py` (incluye routers demo + SSE + webhooks + telemetry middleware).
- Prod runtime: `ls_iMotorSoft_Srv01.py` (solo rutas productivas/minimas).
- Regla: una feature demo nueva se registra en demo entrypoint, no en prod, salvo decision explicita.

### 5.3 Contexto Dominio (Backend)

- `modules/agui_stream`: transporte de eventos SSE.
- `modules/vertice360_workflow_demo`: estado del ticket y reglas operativas.
- `modules/vertice360_ai_workflow_demo`: pipeline AI (heuristico/LLM) y eventos de corrida.
- `modules/messaging`: proveedores WhatsApp (Meta/Gupshup), parseo y envio.
- `modules/crm_demo`: demo CRM desacoplada.

Regla: para nueva capacidad, extender primero modulo existente del dominio y crear modulo nuevo solo si cambia el bounded context.

## 6) Regla de reutilizacion (evitar archivos nuevos innecesarios)

Antes de crear archivo nuevo, validar esta secuencia:

1. Si es regla de negocio de workflow: extender `modules/vertice360_workflow_demo/services.py`.
2. Si es estado de ticket: extender `modules/vertice360_workflow_demo/store.py`.
3. Si es emision de evento UI: extender `modules/vertice360_workflow_demo/events.py`.
4. Si es endpoint demo workflow: extender `routes/demo_vertice360_workflow.py`.
5. Si es mensajeria/provider: extender `routes/messaging.py` y `modules/messaging/providers/...`.
6. Si es consumo frontend workflow: extender `astro/src/lib/vertice360_workflow/{api.js,state.svelte.js,sse.js}`.

Crear modulo nuevo solo si no encaja en los dominios anteriores.

## 7) Blueprint minimo para modulo nuevo (backend)

Estructura recomendada (solo si aplica):

- `modules/<nuevo_modulo>/__init__.py`
- `modules/<nuevo_modulo>/services.py`
- `modules/<nuevo_modulo>/store.py` (si hay estado)
- `modules/<nuevo_modulo>/events.py` (si impacta AG-UI)
- `routes/demo_<nuevo_modulo>.py`
- `tests/test_<nuevo_modulo>_smoke.py`

Contrato minimo:

- Los eventos `ticket.*` o `messaging.*` deben mantener `correlationId == ticketId`.
- Cualquier endpoint nuevo debe devolver errores consistentes (`detail` o payload de error estructurado).
- Si hay side effects, agregar idempotencia o dedupe.

## 8) Contexto AG-UI / SSE (obligatorio para demos)

Envelope estandar:

```json
{
  "type": "CUSTOM",
  "timestamp": 1739400000000,
  "name": "dominio.evento",
  "value": {},
  "correlationId": "ticket-or-run-id"
}
```

Reglas:

- `name` estable y versionable por dominio.
- `value` chico y semantico (sin payload gigante).
- Para ticket events: incluir siempre `value.ticketId`.
- Frontend debe ser tolerante a eventos faltantes o fuera de orden.

## 9) UX responsive (mobile-first) para demos

Aplicar por defecto:

- Layout de 1 columna en mobile, 2 columnas solo en ancho suficiente.
- Acciones criticas visibles sin hover (botones/tabs grandes, tactiles).
- Evitar tablas anchas sin fallback; usar cards/listas en celular.
- SSE/event logs con truncado + expandir, no bloques infinitos.
- Estados de carga/error vacio explicitos en cada panel.

Archivos donde aplicar primero en frontend demo:

- `astro/src/lib/vertice360_workflow/ui/*`
- `astro/src/lib/vertice360_ai_workflow_studio/ui/*`

### 9.1) Gate obligatorio UX-first (antes de implementar funcionalidad)

Antes de construir cualquier modulo/demo funcional, se debe completar una etapa UX-only:

1. Definir alcance visual: landing, flujo y componentes.
2. Crear mockup navegable (sin backend real) para validacion de disenio.
3. Usar mockup data realista (estructura y volumen similares a produccion).
4. Validar mobile-first con foco en uso tactil (usuarios mayormente celular).
5. Aprobar con equipo de diseno antes de pasar a implementacion funcional.

Entregables minimos de esta etapa:

- Pantallas clave de landing y vistas principales del modulo.
- Estados de UI: loading, vacio, error, exito.
- Biblioteca de componentes base a reutilizar en implementacion.
- Contrato visual inicial para `api.js/state.svelte.js/sse.js` (aunque sea con datos mock).

### 9.2) Plantilla estandar: Brief UX (completar antes de desarrollo)

Copiar y completar este bloque por cada modulo/demo nuevo:

```md
# Brief UX - <nombre_modulo_o_demo>

## 1) Contexto
- Objetivo de negocio:
- Tipo de pieza: landing | dashboard | flujo operativo | componente
- Audiencia principal:
- Dispositivo prioritario: mobile (siempre), desktop (secundario)

## 2) Alcance UX (fase mockup)
- Pantallas incluidas:
- Componentes nuevos:
- Componentes reutilizados:
- Estados obligatorios por pantalla: loading, vacio, error, exito

## 3) Datos mock realistas
- Fuente de referencia real (endpoint/estructura):
- Volumen estimado (ej: 20 tickets, 200 eventos):
- Casos borde incluidos:
  - datos incompletos
  - latencia simulada
  - errores de API
  - textos largos / truncado

## 4) Reglas UX no negociables
- Responsive sin scroll horizontal en 360px de ancho.
- Targets tactiles >= 44x44.
- Acciones principales visibles sin hover.
- Contraste y foco accesibles.

## 5) Entregables de diseno
- Mockup navegable (link):
- Biblioteca de componentes base:
- Guía visual breve (tipografia, color, spacing):
- Notas de interaccion/animacion:

## 6) Criterio de aprobacion UX
- [ ] Validado por diseno
- [ ] Validado por producto/negocio
- [ ] Validado en mobile real o emulacion confiable
- [ ] Listo para implementacion funcional
```

## 10) Telemetria + MLflow (incremental, sin romper)

### 10.1 Telemetria base

Ya disponible:

- `TelemetryMiddleware` inyecta `x-request-id` y `x-correlation-id`.
- `telemetry/logging.py` agrega contexto a logs.

A reforzar en modulos nuevos:

- Log de inicio/fin por accion de negocio con `ticketId` o `runId`.
- Medicion de latencia por etapa critica (`*_ms`).

### 10.2 MLflow

`ml/mlflow_client.py` esta listo; falta adopcion en servicios principales.

Uso recomendado en modulos nuevos:

- `with start_run(run_name=..., tags=...)`
- `log_params(...)` para modo/provider/intent.
- `log_metrics(...)` para latencia, dedupe hits, success/error rate.
- `log_artifact_text(...)` para resumen de decision (sin datos sensibles).

## 11) Testing aislado (regla de oro)

Base existente:

- `tests/conftest.py` ya resetea stores y hooks.
- Se puede mockear envio WhatsApp/SSE sin red real.

Checklist minimo por feature nueva:

1. Test unitario de logica pura (parser/reglas).
2. Test de servicio con store in-memory (estado antes/despues).
3. Test de endpoint demo (request/response).
4. Test de contrato de evento SSE (`name`, `correlationId`, `value`).
5. Test de no regresion sobre flujo previo sensible.

Regla:

- Si se toca workflow o messaging, agregar al menos un test de idempotencia y uno de orden de eventos.

## 12) Definicion operativa para proximos modulos/demos

### Paso 0: UX-only con mockup data realista (obligatorio)

- Prototipar landing/componentes y flujo completo sin logica funcional final.
- Validar navegacion y responsive en viewport mobile antes de escribir servicios/rutas.
- Alinear con diseno un baseline reutilizable para implementacion posterior.

### Paso A: Definir bounded context

- Workflow operativo, AI workflow, messaging, CRM u otro nuevo.

### Paso B: Reusar punto de extension existente

- Extender `services/store/events` del dominio antes de crear modulo nuevo.

### Paso C: Exponer en router demo

- Crear o extender `routes/demo_*.py` con contrato claro.

### Paso D: Integrar al stream global

- Emitir eventos AG-UI con envelope estandar.

### Paso E: Cerrar con tests de aislamiento

- Smoke + regresion del flujo previo + contrato SSE.

## 13) Recomendaciones concretas inmediatas

1. Formalizar un flujo UX-first: primero mockup de landing/componentes con datos realistas, luego implementacion funcional.
2. Crear una capa de config frontend por entorno (dev/stg/prod) para reemplazar hardcode en `components/global.js`.
3. Empezar a instrumentar `vertice360_workflow_demo/services.py` y `vertice360_ai_workflow_demo/services.py` con `ml/mlflow_client.py`.
4. Mantener `routes/messaging.py` estable, moviendo nueva logica de negocio hacia servicios auxiliares para reducir acoplamiento del controlador.
5. Para cada demo nueva, replicar patron `api.js + state.svelte.js + sse.js + ui/*` y probar primero en mobile viewport.

## 14) Criterio de aceptacion para cambios futuros

Un modulo/demo se considera listo solo si cumple:

- Mockup UX (landing/componentes + estados) aprobado con datos realistas antes del desarrollo funcional.
- Reuso de estructura existente o justificacion clara de modulo nuevo.
- Eventos AG-UI validos y trazables.
- UX mobile usable sin scroll horizontal critico.
- Logs con correlacion y medicion minima de latencia.
- Tests aislados verdes + test de no regresion del flujo impactado.

## 15) Consideraciones anti-error HMR/hidratacion (Astro + Svelte 5)

Objetivo: evitar pantallas en blanco o hidratar parcialmente (solo header) en demos client-side.

Reglas tecnicas:

1. Evitar `{@const ...}` dentro de bloques `#each` en componentes altamente dinamicos (tablas/listas largas) cuando se trabaja en modo `pnpm dev` con HMR activo.
2. No depender de JS para mostrar el contenedor principal de app.
   - `#app` debe renderizar visible por defecto.
   - Si hay modo landing/app por query param, ocultar solo la landing cuando corresponda.
3. Si hay gating por URL (`?cliente=...`), validar siempre ambos escenarios:
   - sin `cliente` (landing visible + app no rota)
   - con `cliente` (app visible e interactiva)
4. Mantener handlers de UI sin efectos colaterales durante render; evitar logica mutable en expresiones de template.

Checklist de validacion dev (obligatorio antes de cerrar cambios UI):

1. Probar en `pnpm dev` y hacer hard refresh (`Ctrl+Shift+R`) en la ruta impactada.
2. Si aparece error de hidratacion tipo `[$.HMR]`, reiniciar dev server antes de seguir (`pnpm dev`).
3. Confirmar build de produccion (`bun run build` o `pnpm -C astro run build`) para descartar fallas solo-HMR.
4. Verificar que no exista estado "solo header" ni blank screen en mobile y desktop.

Accion correctiva recomendada si reaparece:

- Revisar primero componentes modificados recientemente para patrones sensibles de HMR (especialmente `#each` + constructos avanzados de template) y degradar a expresiones directas estables.
