# Status WhatsApp Pipeline Hardening

- Fecha/hora local: 2026-02-12 23:06
- Fecha/hora UTC: 2026-02-13 02:06:27Z

## Contexto
Se investigaron demoras y faltantes de respuesta en el flujo de WhatsApp (Gupshup inbound webhook + outbound send) con foco en idempotencia, latencia y carreras por mensajes seguidos.

## Hallazgos clave
- Había ramas de `accepted inbound` sin outbound esperado por diseño:
  - `DUPLICATE_INBOUND_IGNORED`
  - `HANDOFF_WAITING_OPERATOR`
  - `OUTBOUND_DEDUPED`
- El webhook de Gupshup ejecutaba puente AI antes del procesamiento de ticket/respuesta, agregando latencia en ráfagas.

## Cambios aplicados
- Logging estructurado con correlación por mensaje y decisiones del estado:
  - `INBOUND_ACCEPTED`, `INBOUND_STATE`, `INBOUND_DECISION`, `INBOUND_RESULT`.
- Métricas de tiempo en ms:
  - `db_ticket_load_ms`, `db_ticket_save_ms`, `llm_ms`, `outbound_send_ms`, `total_ms`.
- Fast-path para saludos:
  - Si faltan slots y llega saludo corto (`hola/hi/...`), responde por camino determinístico sin LLM.
- Guard para zona inválida:
  - Si no reconoce barrio/CABA/GBA, responde:
    - `¿Buscás en CABA/GBA? Decime un barrio (ej: Palermo, Almagro...)`
  - No avanza estado hasta zona válida.
- Parser de zona endurecido:
  - Solo acepta zonas conocidas (gazetteer + aliases CABA/GBA) en fallback regex.
- Webhook Gupshup:
  - Se removió el AI bridge previo para priorizar respuesta rápida.
  - Se agregaron logs de `GUPSHUP_WEBHOOK_RECEIVED`, `GUPSHUP_INBOUND_ACCEPTED`, `GUPSHUP_INBOUND_PROCESSED`.
- Outbound Gupshup:
  - Métrica `GUPSHUP_HTTP_SEND ... duration_ms`.
- Config de workers:
  - Nuevo env `VERTICE360_UVICORN_WORKERS` y arranque con `workers>1` cuando aplica.

## Archivos tocados (principal)
- `modules/vertice360_workflow_demo/services.py`
- `modules/vertice360_workflow_demo/commercial_memory.py`
- `routes/messaging.py`
- `modules/messaging/providers/gupshup/whatsapp/client.py`
- `globalVar.py`
- `ls_iMotorSoft_Srv01.py`
- `ls_iMotorSoft_Srv01_demo.py`
- `tests/test_gupshup_webhook_filters.py`
- `tests/test_inbound_fastpath_and_invalid_zona.py`

## Validación ejecutada
- `pytest -q tests/test_gupshup_webhook_filters.py tests/test_inbound_fastpath_and_invalid_zona.py tests/test_inbound_idempotency.py`
- Resultado: `7 passed`
- `python3 -m py_compile ...` en archivos modificados: OK

## Patch unificado
- `/tmp/gupshup_pipeline_hardening.patch`
