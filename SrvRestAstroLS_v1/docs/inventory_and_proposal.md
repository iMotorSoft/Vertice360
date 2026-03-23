# Inventario de Funcionalidades y Propuesta de Arquitectura de Mensajería

## 1. Inventario Actual (Backend)

Basado en el análisis de `ls_iMotorSoft_Srv01_demo.py` y los módulos existentes.

### Endpoints (Rutas)
| Ruta Base | Descripción | Módulo |
| :--- | :--- | :--- |
| `/health` | Health check del servicio. | `routes.health` |
| `/version` | Información de versión y entorno. | `routes.version` |
| `/demo/codex` | API para CLI de Codex Demo. | `routes.demo_codex_vertice360` |
| `/demo/chat` | API para Demo de Chat. | `routes.demo_codex_chat` |
| `/api/demo/ag` | Endpoints para Demo Antigravity (AG-UI). | `routes.demo_ag_vertice360` |
| `/api/agui/stream` | Stream SSE para Antigravity UI. | `modules.agui_stream` |
| `/api/crm/demo` | Endpoints demo para CRM. | `modules.crm_demo` |
| `/api/demo/sse-test` | Test de conectividad SSE aislado. | `routes.demo_sse_test` |
| `/webhook` | **Router de Webhooks de Mensajería**. | `modules.messaging.webhooks` |
| &#9492; `/webhook/bird` | Callback de entrada para proveedor **Bird**. | `modules.messaging.webhooks.routes` |

### Módulos Principales
- **Messaging**: Infraestructura incipiente para mensajería.
    - `providers/bird`: Implementación de Bird con parseo de webhooks.
    - `providers/meta`: Estructura inicial (con snippets de prueba funcionales).
- **Telemetry**: Middleware y configuración de Logging/Metrics.
- **Middleware**: Manejo de Tenant Context y Telemetría.

---

## 2. Propuesta de Arquitectura: Mensajería Multi-Inquilino y Multi-Proveedor

Dado que el sistema manejará múltiples proveedores (Meta, Bird, Twilio, etc.) y múltiples productos/tenants, recomiendo una arquitectura centrada en la **abstracción del proveedor**.

### Estructura de Endpoints Sugerida

Recomiendo separar claramente los **Webhooks (Entrada Pública)** de la **API de Negocio (Uso Interno/Frontend)**.

#### A. Webhooks (Recepción de Mensajes)
Estos endpoints son públicos y reciben POSTs desde Meta, Bird, etc.
*Ruta Base recomendada: `/webhooks/messaging/{provider}`*

| Verbo | Ruta | Descripción |
| :--- | :--- | :--- |
| `POST` | `/webhooks/messaging/meta` | Recibe eventos de WhatsApp Cloud API. Valida firma SHA256. |
| `POST` | `/webhooks/messaging/bird` | Recibe eventos de Bird. Valida firma. |
| `POST` | `/webhooks/messaging/twilio` | (Futuro) Recibe eventos de Twilio. |
| `GET` | `/webhooks/messaging/meta` | **Importante:** Meta requiere un GET para verificar el token del webhook (`hub.verify_token`). |

**Flujo:**
1.  Webhook llega al endpoint específico del proveedor.
2.  El "Adapter" del proveedor normaliza el payload a un formato interno común (`UnifiedMessageEvent`).
3.  El evento normalizado se despacha al **Event Bus** o **Service Layer** para ser procesado (ej. guardar en DB, disparar bot, notificar al frontend vía SSE).

#### B. API de Envío (Salida)
Estos endpoints son usados por tu Frontend o servicios internos para enviar mensajes. **No deben exponer directamente al proveedor**.
*Ruta Base recomendada: `/api/v1/messaging`*

| Verbo | Ruta | Descripción |
| :--- | :--- | :--- |
| `POST` | `/api/v1/messaging/send` | Envío agnóstico. El backend decide el proveedor según configuración del Tenant. |
| `GET` | `/api/v1/messaging/history` | Obtener historial unificado (independiente del proveedor). |

**Ejemplo de Payload unificado para `/send`:**
```json
{
  "to": "5491130946950",
  "channel": "whatsapp",
  "type": "template",
  "content": {
    "template_name": "hola_mundo",
    "language": "es",
    "parameters": ["Juan"]
  },
  "tenant_id": "..." (o inferido del token)
}
```

### Estructura de Carpetas Recomendada (`backend/modules/messaging`)

Mantén la modularidad actual pero refuerza las interfaces:

```text
backend/modules/messaging/
├── domain/                  # Modelos Pydantic internos (UnifiedMessage, etc.)
├── services/
│   └── message_service.py   # Lógica de negocio. Decide qué provider usar.
├── providers/               # Implementaciones específicas
│   ├── base.py              # Clase Base abstracta (define métodos send(), parse_webhook())
│   ├── meta/
│   │   ├── client.py        # Lógica de envío (API de Meta)
│   │   ├── parser.py        # Normalización de webhooks de Meta
│   │   └── webhooks.py      # Endpoint (Controller) específico de Meta
│   └── bird/
│       ├── client.py
│       └── ...
└── webhooks/
    └── router.py            # Router principal que agrupa los routers de providers
```

### Próximos Pasos Sugeridos
1.  **Implementar el Webhook de Meta**: Crear `/webhooks/messaging/meta` (GET para verificación y POST para mensajes) en `backend/modules/messaging/providers/meta/webhooks.py`.
2.  **Definir la Interfaz de Proveedor**: Crear una clase base que obligue a implementar `send_message` y `normalize_webhook_payload`.
3.  **Endpoint de Envío Unificado**: Implementar `/api/v1/messaging/send` que delegue a la implementación correcta basada en variables de entorno o configuración de DB.
