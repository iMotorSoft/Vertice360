# Informe de estado: demo Astro/Svelte `vertice360-orquestador`
Fecha: 2026-02-19

## 1) Inventario de páginas
| path | propósito | notas |
|---|---|---|
| `astro/src/pages/demo/vertice360-orquestador/index.astro` | Single entrypoint: landing + tablero en la misma ruta | Renderiza `Landing` y `OrquestadorApp`; con `cliente` en query muestra tablero y oculta landing; sin `cliente` hace reset de UI (`orquestador:reset-ui`). |
| `astro/src/pages/demo/vertice360-orquestador/orquestador.astro` | Ruta de tablero directo | Siempre renderiza `OrquestadorApp` (sin gating de landing). URL esperada: `/demo/vertice360-orquestador/orquestador`. |
| `astro/src/pages/demo/vertice360-orquestador/README.txt` | Documentación operativa del wireframe | Declara explícitamente estado "UX-only", sin integración backend, y rutas de uso con `?cliente=...`. |

## 2) Inventario de componentes
| path | uso | datos/props |
|---|---|---|
| `astro/src/components/demo/vertice360-orquestador/OrquestadorApp.svelte` | Componente principal del tablero | Props: `initialCliente`, `clientPhone`. Estado local completo con `$state` (conversaciones, modales, notice, lead seleccionado). Carga mock desde `orquestadorAds`, `orquestadorKpis`, `orquestadorConversations`. Sin `fetch` a API. |
| `astro/src/components/demo/vertice360-orquestador/Landing.svelte` | Landing de inicio demo | Sin props; usa teléfonos/código hardcodeados para CTA a WhatsApp. |
| `astro/src/components/demo/vertice360-orquestador/VisitProposalModal.svelte` | Modal UI para proponer/reagendar/reenviar visita | Props: `open`, `cliente`, `mode`, `onClose`, `onSubmit`. Defaults de campos hardcodeados (`Asesor Demo`, opciones de horario, mensaje). |
| `astro/src/components/demo/vertice360-orquestador/LeadDetailModal.svelte` | Modal de detalle + "Composer Supervisor" | Props: `open`, `lead`, `onClose`. Construye conversación sintética local (`buildConversation`) y agrega mensajes supervisor solo en UI. |
| `astro/src/components/demo/vertice360-orquestador/OrquestadorShell.svelte` | Wrapper alternativo landing/tablero por query param | Lee `cliente` con `URLSearchParams`, pero no está referenciado por páginas actuales (componente huérfano hoy). |

## 3) Capa de datos
| path | tipo: mock/api/store | notas |
|---|---|---|
| `astro/src/lib/vertice360_orquestador_mock/data.js` | `mock` | Fuente principal de datos del demo: ads, KPIs y 24 conversaciones generadas (`createConversation`), con estados y timestamps hardcodeados. |
| `astro/src/components/demo/vertice360-orquestador/OrquestadorApp.svelte` | `store local` (estado en componente) | Clona mock en `conversations` y muta en memoria para acciones (`visit`, `confirm`, `reschedule`, `view`). Persistencia nula. |
| `astro/src/components/demo/vertice360-orquestador/LeadDetailModal.svelte` | `mock local` | Genera mensajes sintéticos por lead/proyecto; no consume backend. |
| `astro/src/components/demo/vertice360-orquestador/VisitProposalModal.svelte` | `mock local` | Emite payload al padre por callback, sin llamada HTTP. |
| `astro/src/config/api.ts` | `api base` global del proyecto | Existe `API_BASE_URL = "http://localhost:7062"`, pero el demo `vertice360-orquestador` no lo usa hoy. |

## 4) Lógica de "cliente"
- `astro/src/pages/demo/vertice360-orquestador/index.astro`: lee `new URLSearchParams(window.location.search).get("cliente")`; si tiene valor, muestra `#app` y oculta `#intro`; si no, muestra landing y dispara `orquestador:reset-ui`.
- `astro/src/components/demo/vertice360-orquestador/OrquestadorApp.svelte`: vuelve a leer `cliente` desde URL (`readClienteFromUrl`/`syncClienteFromUrl`) y sincroniza estado en `popstate`.
- `astro/src/components/demo/vertice360-orquestador/OrquestadorApp.svelte`: cuando falta `cliente`, muestra alerta y botón "Usar cliente demo"; ese botón setea `?cliente=5491100000000` con `history.replaceState`.
- `astro/src/components/demo/vertice360-orquestador/OrquestadorShell.svelte`: implementa el mismo patrón (query param -> landing/app), pero no está conectado en páginas activas.
- Comportamiento visible actual: `cliente` funciona como flag de modo UX (landing vs tablero), no como filtro de datos reales ni control de acceso.

## 5) Endpoints backend disponibles
| método | path | qué devuelve/espera |
|---|---|---|
| `GET` | `/api/demo/vertice360-orquestador/bootstrap` | Devuelve bootstrap para UI: `whatsapp_demo_phone`, `projects`, `marketing_assets`, `users`. |
| `GET` | `/api/demo/vertice360-orquestador/dashboard?cliente=...` | Devuelve `kpis`, `tickets`, `cliente_activo`; `cliente` es opcional y prioriza coincidencias por teléfono/nombre en ordenado. |
| `POST` | `/api/demo/vertice360-orquestador/ingest_message` | Espera `phone`, `text`, opcionales `project_code`/`source`; crea/actualiza lead+conversation+ticket+message+event y devuelve ids + flags `*_created`. |
| `POST` | `/api/demo/vertice360-orquestador/visit/propose` | Espera `ticket_id`, `message_out`, opcionales `advisor_name`, `option1..3`, `mode`; crea proposal + message + event y setea stage `Esperando confirmación`. |
| `POST` | `/api/demo/vertice360-orquestador/visit/confirm` | Espera `proposal_id`, `confirmed_option(1..3)`, `confirmed_by`; confirma propuesta, registra confirmación/evento y setea stage `Visita confirmada`. |
| `POST` | `/api/demo/vertice360-orquestador/visit/reschedule` | Espera `ticket_id`, `message_out`, opcionales `advisor_name`, `option1..3`; supersede propuestas activas y crea nueva propuesta en modo reprogramación. |
| `POST` | `/api/demo/vertice360-orquestador/supervisor/send` | Espera `ticket_id`, `target(client/advisor)`, `text`; inserta mensaje supervisor + evento `supervisor.message.sent`. |

Archivos backend involucrados:
- `backend/routes/demo_vertice360_orquestador.py` (router + mapping de errores HTTP 400/404/503/500).
- `backend/modules/vertice360_orquestador_demo/schemas.py` (contratos de request).
- `backend/modules/vertice360_orquestador_demo/services.py` (reglas de negocio y shape de respuestas).
- `backend/modules/vertice360_orquestador_demo/repo.py` (SQL contra tablas reales).
- `backend/modules/vertice360_orquestador_demo/db.py` (conexión/transacción/pool psycopg).
- `backend/ls_iMotorSoft_Srv01_demo.py` (wiring del router en app demo).

## 6) Riesgos y dependencias
- Frontend actual de orquestador está 100% desacoplado de backend: no hay `fetch` a `/api/demo/vertice360-orquestador/*`.
- Hay duplicación de lógica de modo `cliente` entre `index.astro`, `OrquestadorApp.svelte` y `OrquestadorShell.svelte` (riesgo de divergencia).
- `OrquestadorShell.svelte` no se usa hoy; puede confundir sobre el entrypoint oficial.
- La UI muta datos mock en memoria; al recargar se pierde todo estado operativo.
- Se usan valores hardcodeados de demo (teléfonos, copy, timestamps), útiles para diseño pero no para operación live.
- Dependencias de UI: Tailwind + DaisyUI (`astro/tailwind.config.cjs`, `astro/package.json`) y layout base común (`astro/src/layouts/BaseLayout.astro`).
- Dependencias backend live: `DB_PG_V360_URL` + `psycopg` + conectividad a Postgres `v360`; sin eso la funcionalidad live no está disponible.
- El router orquestador está cableado en launcher demo (`backend/ls_iMotorSoft_Srv01_demo.py`), no en entrypoint de producción.

## 7) Recomendación y próximos pasos
### Opción 1: 1 componente UI + 2 providers (mock/live) + 2 rutas
Ventaja principal: minimiza duplicación y mantiene una sola fuente visual para DESIGN/PROD.

Cambios mínimos requeridos:
1. Crear capa `provider` del orquestador en `astro/src/lib/vertice360_orquestador/` con interfaz única (`loadBootstrap`, `loadDashboard`, `ingest`, `propose`, `confirm`, `reschedule`, `supervisorSend`).
2. Implementar `mockProvider` (wrapping de `vertice360_orquestador_mock/data.js`) y `liveProvider` (fetch a `/api/demo/vertice360-orquestador/*`).
3. Refactorizar `OrquestadorApp.svelte` para no importar mock directo; recibir provider por props/context y mover side-effects UI->provider.
4. Dejar dos rutas Astro explícitas: `.../design` usa `mockProvider`; `.../prod` usa `liveProvider`.
5. Consolidar lectura de `cliente` en un solo punto (route-level o shell) y pasarlo como prop normalizada al app.

### Opción 2: duplicar solo páginas (design/prod) y reusar subcomponentes + lib común
Ventaja principal: transición más incremental con menor riesgo inmediato sobre wireframe actual.

Cambios mínimos requeridos:
1. Mantener `OrquestadorApp.svelte` actual como base DESIGN (sin romper demo vigente).
2. Crear `OrquestadorAppLive.svelte` para conexión real, reusando `VisitProposalModal.svelte` y `LeadDetailModal.svelte` (o variantes mínimas).
3. Extraer utilidades compartidas (normalización cliente, badges/estado, formatos fecha) a `astro/src/lib/vertice360_orquestador/common.js`.
4. Definir dos páginas separadas: `.../index.astro` design congelado y `.../prod.astro` live.
5. Agregar una lib API dedicada `astro/src/lib/vertice360_orquestador/api.js` para concentrar contratos backend y manejo de errores.

Comparación rápida:
- Opción 1: mejor mantenibilidad a mediano plazo, requiere refactor inicial más disciplinado.
- Opción 2: menor impacto inmediato, pero con mayor costo de mantenimiento si las dos apps divergen.

Recomendación práctica: iniciar con Opción 1 si el objetivo es producto continuo; usar Opción 2 solo si se necesita congelar el wireframe de diseño de forma urgente y con bajo riesgo de tocar lo actual.
