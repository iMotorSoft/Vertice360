# 1. Resumen
- MVP de proveedor Meta WhatsApp (Cloud API) integrado en Vertice360.
- Funciona hoy: outbound, inbound, SSE global y UX event log en el lab.
- Falta: validacion de statuses end-to-end, persistencia, endpoints v1 y numero prod verificado.

# 2. Stack y contexto del proyecto
- Backend: Litestar + Uvicorn.
- Stream global SSE: `GET /api/agui/stream`.
- Messaging hub: AG-UI SSE global (eventos `messaging.*`).
- Frontend UX lab: Astro + Svelte 5 runes.
- Pagina de prueba: `http://localhost:3062/demo/messaging/providers/meta/whatsapp`.

## Arquitectura actual
- Outbound: UX -> `POST /api/demo/messaging/meta/whatsapp/send` -> Meta Cloud API -> respuesta `wamid` -> SSE `messaging.outbound`.
- Inbound: Meta Webhook -> `POST /webhooks/messaging/meta/whatsapp` -> mapper -> SSE `messaging.inbound` -> UX event log.
- Status: Meta Webhook -> mapper -> SSE `messaging.status` (pendiente validacion end-to-end).

# 3. Estructura de carpetas relevante (solo lo necesario)
- `backend/routes/messaging.py`: endpoints demo, webhook y emision SSE.
- `backend/modules/messaging/providers/meta/whatsapp/client.py`: cliente HTTP a Graph API.
- `backend/modules/messaging/providers/meta/whatsapp/mapper.py`: parseo de `messages` y `statuses`.
- `backend/modules/agui_stream/routes.py`: stream SSE global y CORS.
- `astro/src/pages/demo/messaging/providers/meta/whatsapp/index.astro`: pagina del lab.
- `astro/src/components/demo/messaging/providers/meta/whatsapp/MetaWhatsAppLab.svelte`: UI de envio y event log.
- `astro/src/lib/messaging/sse.js`: utilidades `connectSSE` y `parseSseData`.

# 4. Variables de entorno (globalVar.py)
Se leen desde `backend/globalVar.py` via `os.environ`. No es obligatorio usar `~/.bashrc`; pueden venir de `.env`, shell, systemd, docker, etc.

UX (Astro): variables globales en `astro/src/components/global.js`.

| Variable | Proposito |
| --- | --- |
| `META_VERTICE360_WABA_TOKEN` | Bearer token para enviar mensajes via Graph API. |
| `META_VERTICE360_WABA_ID` | WABA ID para consultas administrativas (subscribed apps). |
| `META_VERTICE360_PHONE_NUMBER_ID` | Phone Number ID usado en el endpoint `/messages`. |
| `META_VERTICE360_VERIFY_TOKEN` | Token para el handshake del webhook (GET hub.challenge). |
| `META_APP_SECRET_IMOTORSOFT` | App secret para validar firma `X-Hub-Signature-256`. |

Nota: el backend usa `META_GRAPH_VERSION` con default `v20.0`.

# 5. Configuracion en Meta (paso a paso)
1) Configurar Callback URL del webhook:
   - `https://<tu-tunnel>/webhooks/messaging/meta/whatsapp`
2) Definir Verify Token (debe coincidir con `META_VERTICE360_VERIFY_TOKEN`).
3) Suscribir el campo `messages` en Webhooks.
4) Verificar apps suscritas al WABA:
   ```bash
   curl -s -H "Authorization: Bearer $META_VERTICE360_WABA_TOKEN" \
     "https://graph.facebook.com/v20.0/$META_VERTICE360_WABA_ID/subscribed_apps"
   ```
5) Allowed list / modo test:
   - Error tipico `(#131030) Recipient phone number not in allowed list`.
   - Solucion: agregar el numero destinatario en la lista de pruebas y verificarlo con el codigo enviado por WhatsApp.
6) Diferencia de numeros:
   - Test Number `NOT_VERIFIED`: solo permite numeros en allowed list.
   - Numero real `VERIFIED`: habilita uso publico/produccion.

# 6. Endpoints backend implementados (tabla)
| Metodo | Ruta | Proposito | Notas |
| --- | --- | --- | --- |
| POST | `/api/demo/messaging/meta/whatsapp/send` | Envio outbound via Meta Cloud API. | Prefijo demo, no CRM. |
| GET | `/webhooks/messaging/meta/whatsapp` | Verificacion del webhook (hub.challenge). | Valida `META_VERTICE360_VERIFY_TOKEN`. |
| POST | `/webhooks/messaging/meta/whatsapp` | Inbound y status updates. | Valida HMAC si hay app secret. |
| GET | `/api/agui/stream` | SSE global de AG-UI. | Handshake `: connected` + keep-alive. |

Nota: `/api/v1/messaging` existe como placeholder, sin endpoints productivos aun.

# 7. Formato de eventos SSE (AG-UI CustomEvent)
- El broadcaster envia eventos SSE con `event:` y `data:`.
- Tipo principal para inbound: `messaging.inbound`.
- Estructura `CustomEvent`:
  ```text
  event: messaging.inbound
  data: {"type":"CUSTOM","timestamp":1710000000000,"name":"messaging.inbound","value":{...},"correlationId":"wamid..."}
  ```
- Ejemplo real (recortado):
  ```text
  event: messaging.inbound
  data: {"type":"CUSTOM","timestamp":1710000000000,"name":"messaging.inbound","value":{"provider":"meta","service":"whatsapp","wa_id":"54911...","from":"54911...","text":"Hola","timestamp":"1710000000","message_id":"wamid.HBg..."},"correlationId":"wamid.HBg..."}
  ```
- Handshake inicial: `: connected`.
- Keep-alive: `: ping` cada ~20s cuando no hay eventos.

# 8. Pruebas reproducibles (copy/paste)
Flujo end-to-end probado (local + tunnel + UX):
- Backend activo en `http://localhost:7062`.
- Tunnel publico apuntando al backend (`cloudflared`).
- Webhook de Meta apuntando a `/webhooks/messaging/meta/whatsapp`.
- SSE abierto en la UX lab y en `curl -N`.
- Envio de mensaje real al numero del WABA y visualizacion en el event log.

Abrir SSE (ver handshake y pings):
```bash
curl -N http://localhost:7062/api/agui/stream
```

Verificar webhook challenge (local):
```bash
curl "http://localhost:7062/webhooks/messaging/meta/whatsapp?hub.mode=subscribe&hub.verify_token=$META_VERTICE360_VERIFY_TOKEN&hub.challenge=12345"
```

Verificar webhook challenge (via tunnel):
```bash
curl "https://<tu-tunnel>/webhooks/messaging/meta/whatsapp?hub.mode=subscribe&hub.verify_token=$META_VERTICE360_VERIFY_TOKEN&hub.challenge=12345"
```

Enviar outbound (demo):
```bash
curl -X POST http://localhost:7062/api/demo/messaging/meta/whatsapp/send \
  -H "Content-Type: application/json" \
  -d '{"to":"54911XXXXXXX","text":"Prueba Meta WA Vertice360"}'
```

Error allowed list (ejemplo esperado):
```json
{
  "error": {
    "message": "(#131030) Recipient phone number not in allowed list",
    "type": "OAuthException",
    "code": 131030
  }
}
```

Que esperar en logs del backend:
- `DEBUG: SIG OK`
- `DEBUG: Inbound messages found: 1`
- `DEBUG: Broadcasting inbound message from ...`

Prueba UX:
- Abrir `http://localhost:3062/demo/messaging/providers/meta/whatsapp`.
- Enviar mensaje desde la UI y observar `messaging.outbound`.
- Mandar mensaje al numero del WABA y ver `messaging.inbound` en el event log.

# 9. Cloudflared tunnel (dev)
Comando utilizado:
```bash
cloudflared tunnel --url http://localhost:7062 --protocol http2 --edge-ip-version 4
```
Notas:
- En `trycloudflare` la URL cambia cuando se reinicia el tunnel.
- La URL publica debe apuntar a `/webhooks/messaging/meta/whatsapp` en Meta.

# 10. Estado actual (hoy)
- [x] outbound ok (wamid)
- [x] inbound ok (messages) -> SSE -> UX event log
- [x] firma HMAC ok (X-Hub-Signature-256)
- [ ] status updates (statuses) -> SSE `messaging.status` (pendiente validar end-to-end)
- [ ] persistencia (DB)
- [ ] v1 produccion

# 11. Proximos pasos recomendados (orden)
1) Completar validacion end-to-end de `statuses[]` y emitir `messaging.status` en flujo real.
2) UI: representar status de entrega/lectura en el lab.
3) Implementar endpoints productivos `/api/v1/messaging`.
4) Migrar de Test Number `NOT_VERIFIED` a numero real `VERIFIED`.

# Troubleshooting
- 403 en GET webhook: `hub.verify_token` no coincide con `META_VERTICE360_VERIFY_TOKEN`.
- 403 en POST webhook: `X-Hub-Signature-256` invalida; revisar `META_APP_SECRET_IMOTORSOFT` y que el body llegue sin alterar.
- Error `(#131030)`: destinatario fuera de allowed list; agregar y verificar el numero en modo test.
- No llegan webhooks: WABA sin app suscrita; revisar `subscribed_apps` y suscripcion al campo `messages`.
- URL publica cambio: tunnel reiniciado; actualizar Callback URL en Meta.
- SSE no conecta en UX: CORS; revisar `FRONTEND_ORIGINS` en `backend/globalVar.py`.
- SSE conecta pero sin eventos: confirmar que el webhook recibe `messages` y que la UI escucha `messaging.inbound`.
- Respuesta 401/403 en outbound: token o phone number id invalidos; revisar env vars.
