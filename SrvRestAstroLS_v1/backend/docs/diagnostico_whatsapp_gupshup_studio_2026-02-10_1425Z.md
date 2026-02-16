# Diagnostico WhatsApp Flow (Gupshup + Studio)

- Fecha UTC: 2026-02-10 14:25:43Z
- Alcance: analisis read-only (sin aplicar fixes)
- Contexto: comportamiento observado en chat real

## Evidencia reportada

- [11:11] User: "hi"
- [11:11] Bot: "¿Para qué fecha estimás la mudanza?"
- [11:11] User: "abril 2026"
- [11:11] Bot: "Gracias. Tengo: zona Almagro, 2 ambientes, presupuesto 120000 USD, mudanza abril 2026. ¿Querés coordinar visita?..."
- [11:12] User: "busco depto"
- [11:12] Bot: "¿Para qué fecha estimás la mudanza?"

## Hallazgos tecnicos (con referencias)

1) Punto exacto de decision (pregunta vs resumen)
- Entrada principal: `modules/vertice360_workflow_demo/services.py:909`
- Pregunta siguiente slot: `modules/vertice360_workflow_demo/services.py:1160`
- Resumen al completar slots: `modules/vertice360_workflow_demo/services.py:1170`
- Texto resumen: `modules/vertice360_workflow_demo/services.py:511`
- Orden de slots/preguntas: `modules/vertice360_workflow_demo/commercial_memory.py:391`

2) Estado de conversacion y reuso de ticket
- Store en memoria (`tickets`): `modules/vertice360_workflow_demo/store.py:242`
- Reuso por telefono si no viene `ticketId`: `modules/vertice360_workflow_demo/store.py:210`
- Match por `customer.from` y ticket no cerrado: `modules/vertice360_workflow_demo/store.py:168`
- Sin TTL de sesion en ese reuso.

3) Origen de valores "viejos" (zona/ambientes/presupuesto)
- Se leen de `ticket.commercial` persistido y se sincronizan en cada inbound:
  `modules/vertice360_workflow_demo/services.py:1014`
- `answered_fields` se marcan por "valor presente", no por "capturado en esta sesion":
  `modules/vertice360_workflow_demo/services.py:263`
- Resultado: si zona/tipologia/presupuesto ya estaban cargados, solo falta mudanza y se pregunta mudanza primero.

4) Handoff/pause en codigo actual
- Pausa por handoff: `modules/vertice360_workflow_demo/services.py:972`
- Activacion de handoff al enviar resumen: `modules/vertice360_workflow_demo/services.py:1179`
- En el source actual, tras resumen deberia pausar auto-reply (validado por test): `tests/test_handoff_pause.py:8`

5) Diferencia texto observado vs source actual
- El texto observado "¿Para qué fecha estimás la mudanza?" no aparece en source productivo actual.
- Texto actual en codigo: "¿Para qué mes y año estimás la mudanza?" (`modules/vertice360_workflow_demo/commercial_memory.py:411`).
- Esto sugiere posible mismatch de version runtime o flujo distinto al source inspeccionado.

## Reproduccion local de analisis

Se hizo simulacion local sin cambiar codigo productivo:
- ticket activo con estado previo: zona=Almagro, tipologia=2 ambientes, presupuesto=120000 USD, mudanza faltante.
- inbound "hi" => pregunta mudanza.
- inbound "abril 2026" => resumen con esos datos previos.

El patron coincide con el comportamiento reportado para los dos primeros mensajes.

## Root Cause Candidates (ranking)

1. Muy probable: reuso de ticket activo por telefono + slots previos persistidos.
2. Probable: mismatch entre version runtime y version inspeccionada.
3. Posible: inconsistencia de identidad `from` entre proveedores/formateos.

## Fixes minimos propuestos (NO implementados en este analisis)

1) Guard de "sesion nueva" al reusar ticket por telefono (crear ticket nuevo en condiciones de reinicio/conversacion nueva).
2) Gate de resumen por provenance de slots (no resumir si los slots no fueron recolectados en esta sesion/ticket actual).

## Validaciones ejecutadas

- `python -m compileall -q .` -> OK
- `python -m pytest -q` -> OK (60 passed)
- Tests focalizados de flujo/handoff/idempotencia -> OK

