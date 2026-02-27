# Status Inbound Router Orquestador

- Fecha/hora local: 2026-02-23 23:37:54 -03
- Fecha/hora UTC: 2026-02-24 02:37:54 UTC

## Objetivo aplicado

- Webhook inbound de Gupshup ahora enruta por defecto al Orquestador (DB v360 + copy Vera).
- `vertice360_workflow_demo` se conserva para pruebas internas, pero no es default del webhook.

## Cambios implementados

1. Config canónica de routing inbound
- Archivo: `backend/globalVar.py`
- Se agrego `V360_INBOUND_ROUTER_MODE` con valores validos `orquestador|workflow`.
- Default y fallback por valor invalido: `orquestador`.
- Se mantiene alias legacy `V360_INBOUND_MODE` para compatibilidad.
- Boot log actualizado con `inbound_router_mode=<...>`.

2. Routing webhook Gupshup
- Archivo: `backend/routes/messaging.py`
- `POST /webhooks/messaging/gupshup/whatsapp` ahora decide ruta con `V360_INBOUND_ROUTER_MODE`.
- Si `orquestador`: usa `modules.vertice360_orquestador_demo.services.ingest_from_provider(...)`.
- Si `workflow`: mantiene `process_inbound_message(...)` para pruebas.

3. Adaptador inbound Orquestador
- Archivo: `backend/modules/vertice360_orquestador_demo/services.py`
- `ingest_from_provider(...)` actualizado a contrato:
  - `provider`
  - `user_phone`
  - `text`
  - `provider_message_id`
  - `provider_meta`
- Normaliza telefono a E164 dentro del orquestador.
- Reusa flujo existente de `ingest_message` (persist inbound/outbound/events, reply Vera, tolerancia a falla outbound con `vera_send_ok=false`).
- Retorno corto:
  - `{ ok, routed, ticket_id, lead_id, conversation_id, vera_send_ok }`

4. Respuesta canónica del webhook
- Exito:
  - `{"ok": true, "routed": "orquestador", "vera_send_ok": true|false}`
  - `{"ok": true, "routed": "workflow"}` (cuando aplica opt-in)
- Parse failed (best-effort):
  - `{"ok": true, "ignored": true, "reason": "parse_failed"}`

5. Documentacion
- Nuevo archivo: `backend/docs/inbound_router_mode.md`
- Define:
  - default inbound router = `orquestador`
  - opt-in de pruebas con `V360_INBOUND_ROUTER_MODE=workflow`

## Tests

Nuevos tests:
- `backend/tests/test_inbound_router_orquestador_default.py`
- `backend/tests/test_inbound_router_workflow_optin.py`

Tests ajustados por contrato/flag nuevo:
- `backend/tests/test_messaging_gupshup_routes_to_orquestador.py`
- `backend/tests/test_gupshup_webhook_filters.py`
- `backend/tests/test_vertice360_orquestador_demo_ingest_copy.py`

Resultado de validacion:
- `pytest -q` => `93 passed, 5 skipped`

## Notas de compatibilidad

- No se elimino `workflow_demo`.
- Endpoints demo internos de workflow siguen disponibles.
- El default operativo del webhook inbound queda en Orquestador.
