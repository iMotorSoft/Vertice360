# Informe Tecnico: Gupshup + AI Workflow Studio (Desarrollo)
**Fecha**: 2026-02-09
**Ambiente**: Desarrollo local (`http://localhost:7062`) + tunnel Cloudflare
**Objetivo**: Asegurar flujo end-to-end correcto entre webhook Gupshup, backend, SSE y envio desde la UI Studio.

## 1) Resumen Ejecutivo
Se validaron y corrigieron varios desajustes en el flujo de desarrollo:

1. El webhook de Gupshup podia llegar con formatos `message-event`/payload anidado que no siempre se clasificaban correctamente como inbound.
2. La UI Studio estaba enviando por endpoint unificado, pero en algunos casos terminaba ruteando como `meta` por normalizacion insuficiente.
3. El endpoint unificado `/api/demo/messaging/whatsapp/send` tenia un bug de implementacion para el camino Gupshup y devolvia `500`.
4. Se confirmo que eventos `billing-event` de Gupshup no representan mensaje inbound del usuario (solo facturacion).

Resultado final: envio unificado funcionando por Gupshup y validado por `curl` con respuesta:
- `{"ok":true,"provider":"gupshup",...}`

---

## 2) Causas Raiz Detectadas

### 2.1 Ruta/provider incorrecto desde Studio
Evidencia en logs:
- `POST /api/demo/messaging/whatsapp/send`
- `Meta WhatsApp send mapped ...`

Esto probaba que el request del Studio terminaba en proveedor Meta para esos intentos.

### 2.2 Bug del endpoint unificado (500)
Al usar `provider=gupshup` o `provider=gupshup_whatsapp`, el endpoint unificado devolvia `500`.

Causa tecnica:
- El endpoint unificado llamaba internamente a un handler decorado con `@post(...)` como si fuera metodo interno.
- Eso dispara comportamiento no esperado en Litestar y warning de sync callable.

### 2.3 Payloads Gupshup live con estructura variable
Se observaron formatos `message-event` y payloads anidados (`payload.payload.text`, `payload.id`, etc.).
Si no se mapean bien, el inbound no alimenta correctamente el flujo UI/SSE.

### 2.4 Interpretacion de eventos no inbound
Webhook recibido:
- `type: "billing-event"`

Ese tipo no es mensaje de usuario. Por eso puede haber webhook 201 sin que aparezca nuevo inbound en Studio.

---

## 3) Cambios Aplicados

### 3.1 Parser Gupshup robusto para live payloads
**Archivo**: `modules/messaging/providers/gupshup/whatsapp/mapper.py`

Mejoras:
- Extraccion de `from`, `to`, `message_id`, `timestamp` en niveles anidados.
- Extraccion de texto en `payload.payload.text` y variantes.
- Filtrado de `message-event` wrapper como status artificial cuando en realidad contiene mensaje.
- Separacion mas clara entre status real (`delivered/read/failed`) y wrappers de transporte.

### 3.2 Normalizacion de provider (aliases)
**Archivo**: `modules/messaging/providers/registry.py`

Se agrego soporte a aliases:
- Gupshup: `gupshup`, `gupshup_whatsapp`, `gs`
- Meta: `meta`, `meta_whatsapp`, `wa_meta`

Normaliza a canonicos: `gupshup` o `meta`.

### 3.3 Studio API: provider normalizado antes de enviar
**Archivo**: `../astro/src/lib/vertice360_ai_workflow_studio/api.js`

- `sendReply(...)` ahora normaliza provider en cliente antes de POST.
- Evita que variantes de nombre terminen cayendo en default `meta`.

### 3.4 Studio RunInspector: autodeteccion de provider por contexto
**Archivo**: `../astro/src/lib/vertice360_ai_workflow_studio/ui/RunInspector.svelte`

- Detecta provider segun el ultimo evento del ticket (`messaging.inbound/outbound`).
- Auto-setea select de provider en UI (`meta`/`gupshup`).
- Mantiene override manual del usuario (lock por ticket para no pisar seleccion manual).

### 3.5 Fix del endpoint unificado (error 500)
**Archivo**: `routes/messaging.py`

Refactor:
- Nuevo helper interno async: `_send_gupshup_whatsapp(to, text)`.
- `POST /api/demo/messaging/whatsapp/send` usa helper para rama gupshup.
- `POST /api/demo/messaging/gupshup/whatsapp/send` reutiliza el mismo helper.

Con esto se elimina la invocacion interna indebida de un handler decorado.

---

## 4) Validaciones Ejecutadas

### 4.1 Tests
Comandos corridos y resultado:

- `uv run pytest -q tests/test_gupshup_whatsapp_mapper.py -q` -> OK
- `uv run pytest -q tests/test_demo_whatsapp_unified_send.py -q` -> OK
- `uv run pytest -q tests/test_gupshup_demo_error_shape.py -q` -> OK
- `uv run pytest -q tests/test_vertice360_workflow_smoke.py::test_meta_webhook_best_effort tests/test_vertice360_workflow_smoke.py::test_engine_inbound_hello_creates_events -q` -> OK

### 4.2 E2E webhook local/public
Comando:
- `python scripts/verify_gupshup_webhook_e2e.py`

Resultado: `RESULT=PASS`
- local health: OK
- public health: OK
- local webhook post: OK (201)
- public webhook post: OK (201)

### 4.3 Validacion manual endpoint unificado (final)
Comando:
```bash
curl -i -X POST "http://localhost:7062/api/demo/messaging/whatsapp/send" \
  -H "Content-Type: application/json" \
  -d '{"provider":"gupshup_whatsapp","to":"5491130946950","text":"Prueba Studio via Gupshup"}'
```

Resultado:
- `HTTP/1.1 200 OK`
- body con `"provider":"gupshup"` y `"status":"submitted"` en `raw`.

---

## 5) Configuracion de Desarrollo Recomendada

### 5.1 URL publica de webhook
- `VERTICE360_PUBLIC_BASE_URL_DEV` debe apuntar al tunnel activo.
- URL Gupshup final:
  - `https://resolved-cruise-california-derby.trycloudflare.com/webhooks/messaging/gupshup/whatsapp`

Verificar con:
```bash
python scripts/print_public_webhook_urls.py
```

### 5.2 Reinicio obligatorio tras cambios
Cada cambio en backend requiere reiniciar `ls_iMotorSoft_Srv01_demo.py`.
Si no, el comportamiento observado puede ser de codigo viejo.

### 5.3 Variables clave para Gupshup
Confirmar en shell:
- `GUPSHUP_API_KEY_DEV`
- `GUPSHUP_SRC_NUMBER_DEV`
- `GUPSHUP_APP_NAME_PRO` (hoy `GUPSHUP_APP_NAME` toma este valor en `globalVar.py`)

### 5.4 Provider consistency
Para pruebas confiables:
- inbound webhook: Gupshup
- outbound endpoint: Gupshup
- verificacion logs: Gupshup

Evitar mezclar proveedor en una misma corrida de pruebas.

---

## 6) Lectura de Logs: Que Buscar

### 6.1 Inbound real de usuario
Esperado en backend:
- `POST /webhooks/messaging/gupshup/whatsapp`
- `DEBUG: Gupshup Webhook POST received ...`
- `Raw Body` con evento de mensaje (no solo billing)

### 6.2 Envio correcto desde Studio por Gupshup
Esperado:
- `POST /api/demo/messaging/whatsapp/send`
- Sin logs de `Meta WhatsApp send mapped ...`

Si aparece `Meta WhatsApp send mapped ...`, el request sigue yendo por Meta.

### 6.3 Eventos que no deben tomarse como inbound de chat
- `billing-event` (facturacion) no significa mensaje del cliente.

---

## 7) Comandos Utiles de Diagnostico

### 7.1 Verificar webhook URLs generadas
```bash
python scripts/print_public_webhook_urls.py
```

### 7.2 Verificar reachability local+public
```bash
python scripts/verify_gupshup_webhook_e2e.py
```

### 7.3 Simular webhook local Gupshup
```bash
python modules/messaging/providers/gupshup/snippets/test_webhook_post_local.py
```

### 7.4 Observar SSE en vivo
```bash
curl -N http://localhost:7062/api/agui/stream
```

### 7.5 Envio unificado por Gupshup
```bash
curl -X POST "http://localhost:7062/api/demo/messaging/whatsapp/send" \
  -H "Content-Type: application/json" \
  -d '{"provider":"gupshup","to":"5491130946950","text":"Prueba Gupshup"}'
```

---

## 8) Checklist de Desarrollo (Anti-Regresion)

Antes de testear UI:
1. Backend reiniciado con cambios recientes.
2. Tunnel activo y URL actualizada en Gupshup.
3. `verify_gupshup_webhook_e2e.py` en PASS.
4. Studio conectado a `http://localhost:7062`.

Durante pruebas:
1. Confirmar POST webhook en logs al enviar WhatsApp real.
2. Confirmar provider de envio desde Studio (`gupshup`).
3. Confirmar que el endpoint unificado responde 200/502, nunca 500.

Despues de cambios:
1. Correr tests de mapper + unified send.
2. Hacer smoke manual por curl del endpoint unificado.
3. Revisar que no reaparezca ruta Meta cuando el provider es Gupshup.

---

## 9) Riesgos / Consideraciones Pendientes

1. Gupshup puede introducir nuevos formatos de webhook live; mantener tests con fixtures reales actualizados.
2. Eventos no conversacionales (`billing-event`) pueden confundir diagnostico si no se filtran en analisis operativo.
3. Hay cambios no relacionados en el working tree; al hacer PR/merge conviene aislar estos fixes por commit tematico.
4. Recomendable agregar logging explicito del provider resuelto en `send_whatsapp_unified_demo` para trazabilidad inmediata.

---

## 10) Estado Final
El flujo de desarrollo queda operativo con Gupshup de punta a punta:
- webhook entrante validado
- mapeo inbound robustecido
- routing de proveedor corregido en Studio y backend
- endpoint unificado estable (sin 500)
- envio validado con respuesta `provider=gupshup`
