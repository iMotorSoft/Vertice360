# Informe de estado backend (Vertice360)

Fecha/hora local: 2026-02-22 22:04:37 -03  
Fecha/hora UTC: 2026-02-23 01:04:37 UTC

## 1) Resumen de lo implementado

### 1.1 Orquestador DEMO (copy Vera + flujo inbound/outbound)
- Endpoint objetivo: `/api/demo/vertice360-orquestador/ingest_message`.
- Se implementó selección de copy:
  - Primer contacto (`lead_created` OR `conversation_created` OR `ticket_created`) => Mensaje 1 onboarding con link tablero.
  - No primer contacto + proyecto inferido => Mensaje 2 por proyecto.
  - Sin proyecto => fallback corto con opciones de proyecto.
- Se agregó helper para tablero con `?cliente=<digits>`.
- Se mantuvo identidad textual "Vera" y sin menciones a AI/bot.
- Persistencia en v360:
  - inbound/outbound en `messages`.
  - eventos en `events` incluyendo `orq.message.outbound` y `orq.message.outbound.error`.
- Si falla provider outbound: `vera_send_ok=false` sin romper el procesamiento inbound.
- Respuesta incluye `vera_reply_text` y `vera_send_ok` sin romper contrato.

### 1.2 Pool psycopg_pool (warning deprecación)
- Se ajustó creación de pool a patrón explícito recomendado:
  - `ConnectionPool(..., open=False)`.
- Se abrió/cerró pool explícitamente en startup/shutdown del app demo.
- Servicios/repos siguen usando el pool compartido.

### 1.3 Gupshup env aliasing canónico
- Se consolidó el patrón canónico en backend:
  - `GUPSHUP_APP_NAME`
  - `GUPSHUP_API_KEY`
  - `GUPSHUP_WA_SENDER`
- Se documentó aliasing externo (bashrc/script) para mapear `*_DEV/*_PRO` hacia canónicas.
- Se mantuvo regla: lectura de entorno solo en `globalVar.py`.

### 1.4 Webhook Gupshup: soporte inbound para `user-event`
- Endpoint: `POST /webhooks/messaging/gupshup/whatsapp`.
- Cambio principal:
  - Si `event_type == "user-event"` y se puede extraer `sender + text`, se procesa como inbound real vía orquestador (`source="gupshup"`).
  - Respuesta: `{"ok": true, "handled": "inbound_user_event"}`.
  - Si parse falla: se ignora best-effort y loggea `reason=parse_failed` + keys presentes.
- Logging DEV sanitizado agregado para payloads raros (sin secretos).

## 2) Archivos tocados (estado git actual)

Modificados:
- `globalVar.py`
- `ls_iMotorSoft_Srv01_demo.py`
- `modules/vertice360_ai_workflow_demo/langgraph_flow.py`
- `modules/vertice360_orquestador_demo/db.py`
- `modules/vertice360_orquestador_demo/services.py`
- `modules/vertice360_workflow_demo/commercial_memory.py`
- `modules/vertice360_workflow_demo/services.py`
- `modules/vertice360_workflow_demo/store.py`
- `routes/demo_vertice360_orquestador.py`
- `routes/messaging.py`
- `tests/test_gupshup_webhook_filters.py`

Nuevos:
- `docs/gupshup_env_aliasing.md`
- `tests/test_globalvar_gupshup_env_mapping.py`
- `tests/test_vertice360_orquestador_demo_ingest_copy.py`

## 3) Validación ejecutada

### 3.1 Tests automáticos
- `pytest -q` => **86 passed, 5 skipped**.
- Test específico webhook Gupshup:
  - `pytest -q tests/test_gupshup_webhook_filters.py` => **4 passed**.

### 3.2 Prueba manual local (E2E webhook user-event)
- Server demo levantado en `VERTICE360_PORT=7070` con alias canónicos Gupshup activos.
- Request manual:
  - `type="user-event"`, `sender`, `text="hi"`.
- Resultado HTTP:
  - `{"ok":true,"handled":"inbound_user_event"}`.
- Logs observados:
  - `GUPSHUP_WEBHOOK inbound parsed ...`
  - `ORQ_INGEST_MESSAGE ...` con creación de entidades en primer contacto.
  - `GUPSHUP_HTTP_SEND ... status=202 ...`
  - `vera_send_ok=True` en flujo exitoso.

## 4) Estado actual

- Webhook Gupshup ya procesa inbound en `user-event` cuando trae `sender+text`.
- Flujo orquestador DEMO responde con copy Vera según primer contacto/proyecto.
- Persistencia inbound/outbound + eventos operativa en v360.
- Manejo de falla outbound sin romper inbound implementado.
- Pool de DB en patrón explícito (`open=False`) y lifecycle controlado por startup/shutdown.
- Documentación de aliasing canónico Gupshup disponible.

## 5) Observaciones operativas

- Para entorno DEV con tus variables de bashrc (`*_DEV`), se debe mapear a canónicas antes de arrancar (según `docs/gupshup_env_aliasing.md`).
- En boot logs, evitar interpretar `db=...` (fallback general) como fuente de v360: el orquestador usa la config v360 validada (`db_v360_configured/db_v360_valid`).

