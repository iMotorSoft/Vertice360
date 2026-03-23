# Vertice360 - Guía de Arquitectura y Contexto para Módulos Nuevos

## 1. VISIÓN GENERAL DEL PROYECTO

**Vertice360** es una plataforma de gestión de leads y workflow para inmobiliarias, construida con:
- **Backend**: Python 3.13 + Litestar (REST API)
- **Frontend**: Astro.js + Svelte 5 (Runes) + TailwindCSS + DaisyUI
- **Comunicación**: AG-UI (Event streaming), SSE, WebSockets
- **Telemetría**: MLflow, logging estructurado, tracing
- **Testing**: pytest con fixtures aislados

## 2. ESTRUCTURA DE DIRECTORIOS

```
Vertice360/SrvRestAstroLS_v1/
├── backend/                          # Backend Python
│   ├── globalVar.py                  # Configuración centralizada
│   ├── ls_iMotorSoft_Srv01_demo.py   # Entry point demo
│   ├── ls_iMotorSoft_Srv01.py        # Entry point producción
│   ├── middleware/                   # Middlewares (CORS, tenant, telemetría)
│   ├── telemetry/                    # Logging, métricas, tracing
│   ├── modules/                      # Módulos de negocio
│   │   ├── agui_stream/             # AG-UI streaming
│   │   ├── messaging/               # WhatsApp/Meta/Gupshup
│   │   ├── crm_demo/                # CRM demo
│   │   ├── vertice360_workflow_demo/ # Workflow engine
│   │   └── [nuevo_modulo]/          # NUEVOS MÓDULOS AQUÍ
│   ├── routes/                       # Routers API
│   ├── services/                     # Servicios compartidos
│   ├── models/                       # Modelos Pydantic/SQLAlchemy
│   ├── tests/                        # Tests unitarios e integración
│   └── ml/                          # MLflow client
│
├── astro/                            # Frontend Astro.js
│   ├── src/
│   │   ├── components/              # Componentes Svelte reutilizables
│   │   │   ├── global.js           # Configuración global
│   │   │   └── [Componentes UI]
│   │   ├── lib/                    # Librerías de dominio
│   │   │   ├── [modulo]/
│   │   │   │   ├── api.js          # Llamadas API
│   │   │   │   ├── state.svelte.js # Estado (Runes)
│   │   │   │   ├── sse.js          # Event streaming
│   │   │   │   ├── types.js        # Tipos/constantes
│   │   │   │   └── ui/             # Componentes UI
│   │   ├── pages/                  # Rutas Astro
│   │   └── layouts/                # Layouts Astro
│   └── package.json
│
└── doc/                             # Documentación
```

## 3. CONFIGURACIÓN CENTRALIZADA

### Backend (`backend/globalVar.py`)
```python
# Variables de entorno obligatorias
ENVIRONMENT: Literal["dev", "stg", "prod"]
DEBUG: bool = RUN_ENV != "prod"

# API
HOST: str = "0.0.0.0"
PORT: int = 7062

# CORS
FRONTEND_ORIGINS: list[str] = [
    "http://localhost:3062",
    "http://127.0.0.1:3062",
]

# MLflow
MLFLOW_TRACKING_URI: str
MLFLOW_ENABLED: bool

# OpenAI
OpenAI_Key: Optional[str]
OpenAI_Model: str
```

### Frontend (`astro/src/components/global.js`)
```javascript
// URLs del backend
const URL_REST_DEV = 'http://localhost:7062';
const URL_REST_PRO = 'https://demo.vertice360.imotorsoft.com';
export const URL_REST = URL_REST_DEV; // Cambiar a PRO para producción

// SSE endpoint
export const URL_SSE = `${URL_REST}/api/agui/stream`;
```

## 4. PATRÓN PARA NUEVOS MÓDULOS BACKEND

### Estructura de Módulo

```python
backend/modules/[nombre_modulo]/
├── __init__.py          # Exports públicos
├── schemas.py           # Pydantic models
├── store.py            # Estado/almacenamiento
├── services.py         # Lógica de negocio
├── events.py           # Eventos AG-UI
└── [feature].py        # Funcionalidades específicas
```

### Ejemplo: Nuevo Módulo de Analytics

**`backend/modules/analytics/__init__.py`**
```python
"""Analytics module for Vertice360."""

from .store import get_metrics, reset_metrics
from .services import track_event, generate_report

__all__ = [
    "get_metrics",
    "reset_metrics", 
    "track_event",
    "generate_report",
]
```

**`backend/modules/analytics/schemas.py`**
```python
from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime

class EventTrackRequest(BaseModel):
    event_type: str
    entity_id: Optional[str] = None
    metadata: dict = {}
    timestamp: Optional[datetime] = None

class MetricSummary(BaseModel):
    event_type: str
    count: int
    last_occurrence: Optional[datetime]
    
class ReportResponse(BaseModel):
    period: Literal["day", "week", "month"]
    generated_at: datetime
    metrics: list[MetricSummary]
```

**`backend/modules/analytics/store.py`**
```python
"""In-memory store para demo. En producción usar DB."""

from typing import Any
from datetime import datetime

_metrics: dict[str, dict[str, Any]] = {}

async def track_event(
    event_type: str,
    entity_id: str | None = None,
    metadata: dict | None = None
) -> None:
    """Track an analytics event."""
    if event_type not in _metrics:
        _metrics[event_type] = {
            "count": 0,
            "events": [],
            "last_occurrence": None,
        }
    
    _metrics[event_type]["count"] += 1
    _metrics[event_type]["events"].append({
        "entity_id": entity_id,
        "metadata": metadata or {},
        "timestamp": datetime.utcnow(),
    })
    _metrics[event_type]["last_occurrence"] = datetime.utcnow()

async def get_metrics(event_type: str | None = None) -> dict:
    """Get metrics, optionally filtered by event type."""
    if event_type:
        return {event_type: _metrics.get(event_type, {})}
    return dict(_metrics)

def reset_metrics() -> None:
    """Reset all metrics (para tests)."""
    _metrics.clear()
```

**`backend/modules/analytics/events.py`**
```python
"""Event publishing for AG-UI integration."""

from backend.modules.agui_stream import broadcaster

async def emit_analytics_event_tracked(
    event_type: str,
    entity_id: str | None,
    metadata: dict
) -> None:
    """Emit event when analytics event is tracked."""
    await broadcaster.publish(
        "analytics.event_tracked",
        {
            "type": "CUSTOM",
            "name": "analytics.event_tracked",
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
            "value": {
                "eventType": event_type,
                "entityId": entity_id,
                "metadata": metadata,
            },
            "correlationId": entity_id,
        }
    )
```

**`backend/routes/demo_analytics.py`**
```python
"""Demo routes for analytics module."""

from litestar import Controller, Router, get, post
from backend.modules.analytics import schemas, store, events

class AnalyticsController(Controller):
    path = "/events"
    
    @post("")
    async def track_event(self, data: schemas.EventTrackRequest) -> dict:
        """Track a new analytics event."""
        await store.track_event(
            event_type=data.event_type,
            entity_id=data.entity_id,
            metadata=data.metadata,
        )
        await events.emit_analytics_event_tracked(
            data.event_type, data.entity_id, data.metadata
        )
        return {"ok": True, "eventType": data.event_type}
    
    @get("")
    async def get_metrics(self, event_type: str | None = None) -> dict:
        """Get analytics metrics."""
        return await store.get_metrics(event_type)
    
    @get("/report")
    async def generate_report(self, period: str = "day") -> schemas.ReportResponse:
        """Generate analytics report."""
        # Implementation here
        pass

router = Router(
    path="/api/demo/analytics",
    route_handlers=[AnalyticsController],
)
```

### Registro en la App Principal

**`backend/ls_iMotorSoft_Srv01_demo.py`**
```python
from routes.demo_analytics import router as analytics_router

route_handlers = [
    # ... existing routers
    analytics_router,
]
```

## 5. PATRÓN PARA NUEVOS MÓDULOS FRONTEND

### Estructura de Módulo

```
astro/src/lib/[nombre_modulo]/
├── types.js              # Tipos y constantes
├── api.js               # Llamadas HTTP al backend
├── state.svelte.js      # Estado con Runes
├── sse.js              # Suscripción a eventos
└── ui/                 # Componentes Svelte
    ├── [Component].svelte
    └── [Modulo]App.svelte
```

### Ejemplo: Módulo de Analytics Frontend

**`astro/src/lib/analytics/types.js`**
```javascript
export const EVENT_TYPES = {
  TICKET_CREATED: 'ticket.created',
  TICKET_CLOSED: 'ticket.closed',
  MESSAGE_SENT: 'message.sent',
  USER_LOGIN: 'user.login',
};

export const PERIODS = ['day', 'week', 'month'];

export function isAnalyticsEvent(eventName) {
  return eventName?.startsWith('analytics.');
}
```

**`astro/src/lib/analytics/api.js`**
```javascript
import { URL_REST } from '../../components/global.js';

const API_BASE = `${URL_REST}/api/demo/analytics`;

export async function trackEvent(eventType, entityId = null, metadata = {}) {
  const response = await fetch(`${API_BASE}/events`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ event_type: eventType, entity_id: entityId, metadata }),
  });
  
  if (!response.ok) {
    return { ok: false, error: await response.text() };
  }
  
  return { ok: true, data: await response.json() };
}

export async function getMetrics(eventType = null) {
  const url = new URL(`${API_BASE}/events`);
  if (eventType) url.searchParams.set('event_type', eventType);
  
  const response = await fetch(url);
  
  if (!response.ok) {
    return { ok: false, error: await response.text() };
  }
  
  return { ok: true, data: await response.json() };
}
```

**`astro/src/lib/analytics/state.svelte.js`**
```javascript
import * as api from './api';

const MAX_EVENTS = 100;

export function createAnalyticsState() {
  // Runes state
  let metrics = $state({});
  let events = $state([]);
  let loading = $state(false);
  let error = $state(null);
  
  async function loadMetrics(eventType = null) {
    loading = true;
    error = null;
    
    const result = await api.getMetrics(eventType);
    
    if (!result.ok) {
      error = result.error;
      loading = false;
      return;
    }
    
    metrics = result.data;
    loading = false;
  }
  
  async function track(eventType, entityId = null, metadata = {}) {
    const result = await api.trackEvent(eventType, entityId, metadata);
    
    if (!result.ok) {
      error = result.error;
      return false;
    }
    
    // Add to local events
    events = [
      { eventType, entityId, metadata, timestamp: Date.now() },
      ...events,
    ].slice(0, MAX_EVENTS);
    
    return true;
  }
  
  function applyEvent(evt) {
    // Handle incoming SSE events
    if (evt.name === 'analytics.event_tracked') {
      events = [
        {
          eventType: evt.value?.eventType,
          entityId: evt.value?.entityId,
          metadata: evt.value?.metadata,
          timestamp: evt.timestamp,
        },
        ...events,
      ].slice(0, MAX_EVENTS);
    }
  }
  
  return {
    get metrics() { return metrics; },
    get events() { return events; },
    get loading() { return loading; },
    get error() { return error; },
    loadMetrics,
    track,
    applyEvent,
  };
}

export const analytics = createAnalyticsState();
```

**`astro/src/lib/analytics/sse.js`**
```javascript
import { analytics } from './state.svelte.js';
import { isAnalyticsEvent } from './types.js';

export function handleAnalyticsEvent(evt) {
  if (isAnalyticsEvent(evt.name)) {
    analytics.applyEvent(evt);
  }
}
```

**`astro/src/lib/analytics/ui/AnalyticsDashboard.svelte`**
```svelte
<script>
  import { analytics } from '../state.svelte.js';
  
  let selectedPeriod = $state('day');
  
  $effect(() => {
    analytics.loadMetrics();
  });
</script>

<div class="p-4">
  <h1 class="text-2xl font-bold mb-4">Analytics Dashboard</h1>
  
  {#if analytics.loading}
    <div class="loading loading-spinner loading-lg"></div>
  {:else if analytics.error}
    <div class="alert alert-error">{analytics.error}</div>
  {:else}
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      {#each Object.entries(analytics.metrics) as [type, data]}
        <div class="card bg-base-200 shadow-xl">
          <div class="card-body">
            <h2 class="card-title text-lg capitalize">{type.replace('_', ' ')}</h2>
            <p class="text-4xl font-bold">{data.count || 0}</p>
            <p class="text-sm opacity-70">
              Last: {data.last_occurrence ? new Date(data.last_occurrence).toLocaleString() : 'Never'}
            </p>
          </div>
        </div>
      {/each}
    </div>
    
    <div class="mt-8">
      <h2 class="text-xl font-bold mb-2">Recent Events</h2>
      <div class="space-y-2">
        {#each analytics.events.slice(0, 10) as event}
          <div class="flex items-center gap-2 p-2 bg-base-200 rounded">
            <span class="badge badge-primary">{event.eventType}</span>
            <span class="text-sm">{event.entityId || 'N/A'}</span>
            <span class="text-xs opacity-60 ml-auto">
              {new Date(event.timestamp).toLocaleTimeString()}
            </span>
          </div>
        {/each}
      </div>
    </div>
  {/if}
</div>
```

## 6. INTEGRACIÓN AG-UI (EVENT STREAMING)

### Backend: Publicar Eventos

```python
from backend.modules.agui_stream import broadcaster

async def emit_custom_event(event_name: str, payload: dict):
    """Emit event to all connected clients."""
    await broadcaster.publish(
        event_name,
        {
            "type": "CUSTOM",
            "name": event_name,
            "timestamp": int(time.time() * 1000),
            "value": payload,
            "correlationId": payload.get("entityId"),
        }
    )
```

### Frontend: Suscripción SSE

```javascript
// astro/src/lib/shared/sse.js
import { URL_SSE } from '../../components/global.js';

export function createSSEConnection(handlers = {}) {
  let eventSource = null;
  let reconnectAttempts = 0;
  const MAX_RECONNECT = 5;
  
  function connect() {
    eventSource = new EventSource(URL_SSE);
    
    eventSource.onopen = () => {
      console.log('[SSE] Connected');
      reconnectAttempts = 0;
      handlers.onConnect?.();
    };
    
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handlers.onMessage?.(data);
      } catch (e) {
        console.error('[SSE] Parse error:', e);
      }
    };
    
    eventSource.onerror = (error) => {
      console.error('[SSE] Error:', error);
      handlers.onError?.(error);
      
      if (reconnectAttempts < MAX_RECONNECT) {
        reconnectAttempts++;
        setTimeout(connect, Math.min(1000 * reconnectAttempts, 5000));
      }
    };
  }
  
  function disconnect() {
    eventSource?.close();
    eventSource = null;
  }
  
  return { connect, disconnect };
}
```

## 7. TELEMETRÍA Y MLFLOW

### Logging Estructurado

```python
import logging
from backend.telemetry.context import get_request_id, get_correlation_id

logger = logging.getLogger(__name__)

# Automáticamente incluye request_id y correlation_id
logger.info("Processing ticket", extra={
    "ticket_id": ticket_id,
    "action": "assign",
})
```

### MLflow Tracking

```python
from backend.ml.mlflow_client import get_mlflow_client

mlflow = get_mlflow_client()

with mlflow.start_run(experiment_id="vertice360"):
    mlflow.log_param("model_type", "workflow_ai")
    mlflow.log_metric("accuracy", 0.95)
    mlflow.log_artifact("results.json")
```

## 8. TESTING AISLADO

### Fixtures en `backend/tests/conftest.py`

```python
import pytest
from backend.modules.analytics import store as analytics_store

@pytest.fixture(autouse=True)
def reset_analytics_store():
    """Reset analytics store before each test."""
    analytics_store.reset_metrics()
    yield
    analytics_store.reset_metrics()

@pytest.fixture
def mock_broadcaster(monkeypatch):
    """Mock AG-UI broadcaster for testing."""
    published = []
    
    async def mock_publish(event_type, payload):
        published.append({"type": event_type, "payload": payload})
    
    monkeypatch.setattr("backend.modules.agui_stream.broadcaster.publish", mock_publish)
    return published
```

### Test Unitario

```python
# backend/tests/test_analytics.py
import pytest
from backend.modules.analytics import store, schemas

@pytest.mark.asyncio
async def test_track_event(mock_broadcaster):
    await store.track_event("test.event", "entity-123", {"foo": "bar"})
    
    metrics = await store.get_metrics("test.event")
    assert metrics["test.event"]["count"] == 1
    assert len(mock_broadcaster) == 0  # Event emission tested separately
```

## 9. UX RESPONSIVE (MOBILE-FIRST)

### Patrones Svelte 5

```svelte
<!-- Mobile-first responsive design -->
<div class="container mx-auto px-4">
  <!-- Stack on mobile, side-by-side on desktop -->
  <div class="flex flex-col lg:flex-row gap-4">
    <aside class="w-full lg:w-1/3">
      <!-- Sidebar content -->
    </aside>
    <main class="w-full lg:flex-1">
      <!-- Main content -->
    </main>
  </div>
  
  <!-- Responsive grid -->
  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
    {#each items as item}
      <Card {item} />
    {/each}
  </div>
</div>

<!-- Touch-friendly buttons -->
<button class="btn btn-primary min-h-[48px] min-w-[48px] text-lg">
  Action
</button>

<!-- Responsive typography -->
<h1 class="text-xl md:text-2xl lg:text-3xl font-bold">
  Title
</h1>
```

### DaisyUI Components

```svelte
<!-- Modal responsive -->
<dialog class="modal modal-bottom sm:modal-middle">
  <div class="modal-box">
    <h3 class="font-bold text-lg">Title</h3>
    <p class="py-4">Content</p>
    <div class="modal-action">
      <button class="btn">Close</button>
    </div>
  </div>
</dialog>

<!-- Drawer responsive -->
<div class="drawer lg:drawer-open">
  <input id="my-drawer" type="checkbox" class="drawer-toggle" />
  <div class="drawer-content">
    <!-- Page content -->
  </div>
  <div class="drawer-side">
    <!-- Sidebar -->
  </div>
</div>
```

## 10. CONVENCIONES DE NOMENCLATURA

### Backend (Python)
- **Módulos**: `snake_case` (ej: `vertice360_workflow_demo`)
- **Clases**: `PascalCase` (ej: `WorkflowController`)
- **Funciones**: `snake_case` (ej: `track_event`)
- **Constantes**: `UPPER_SNAKE_CASE` (ej: `MAX_EVENTS`)
- **Tests**: `test_[feature]_[scenario].py`

### Frontend (JavaScript/Svelte)
- **Componentes**: `PascalCase.svelte` (ej: `AnalyticsDashboard.svelte`)
- **Funciones**: `camelCase` (ej: `trackEvent`)
- **Estado**: `create[Name]State` (ej: `createAnalyticsState`)
- **Archivos**: `kebab-case.js` (ej: `state.svelte.js`)

### Eventos AG-UI
- **Formato**: `[domain].[action]` (ej: `analytics.event_tracked`)
- **Dominios**: `ticket`, `messaging`, `workflow`, `analytics`

## 11. CHECKLIST PARA NUEVOS MÓDULOS

### Backend
- [ ] Crear estructura en `backend/modules/[nombre]/`
- [ ] Definir schemas Pydantic
- [ ] Implementar store (in-memory para demo)
- [ ] Implementar servicios
- [ ] Agregar eventos AG-UI
- [ ] Crear router en `backend/routes/`
- [ ] Registrar router en `ls_iMotorSoft_Srv01_demo.py`
- [ ] Agregar tests en `backend/tests/`
- [ ] Documentar en `doc/`

### Frontend
- [ ] Crear estructura en `astro/src/lib/[nombre]/`
- [ ] Definir tipos y constantes
- [ ] Implementar API client
- [ ] Implementar estado con Runes
- [ ] Crear componentes UI (responsive)
- [ ] Agregar manejador SSE
- [ ] Crear página demo en `astro/src/pages/demo/`
- [ ] Actualizar navegación

### Integración
- [ ] Verificar CORS configurado
- [ ] Probar flujo end-to-end
- [ ] Verificar eventos SSE llegan al frontend
- [ ] Probar en mobile (responsive)
- [ ] Ejecutar tests: `pytest backend/tests/`

## 12. EJEMPLOS DE REFERENCIA

### Módulos Backend Implementados
1. **`vertice360_workflow_demo/`** - Workflow de tickets
2. **`vertice360_ai_workflow_demo/`** - Workflow con AI
3. **`messaging/`** - Integración WhatsApp (Meta/Gupshup)
4. **`crm_demo/`** - CRM básico
5. **`agui_stream/`** - Event streaming

### Módulos Frontend Implementados
1. **`vertice360_workflow/`** - UI de workflow
2. **`vertice360_ai_workflow_studio/`** - Studio de workflow AI
3. **`crm/`** - UI de CRM
4. **`messaging/`** - UI de mensajería

## 13. COMANDOS ÚTILES

```bash
# Backend
cd backend
source .venv/bin/activate
python ls_iMotorSoft_Srv01_demo.py        # Iniciar servidor
pytest tests/ -v                          # Ejecutar tests
pytest tests/test_analytics.py -v         # Tests específicos

# Frontend
cd astro
npm run dev                               # Desarrollo
npm run build                             # Build producción
npm run preview                           # Preview build

# MLflow
mlflow ui --backend-store-uri file:///path/to/mlruns_vertice360
```

---

**Nota**: Este documento es vivo. Actualizarlo cuando se agreguen nuevos patrones o mejores prácticas.

**Fecha**: 2026-02-13
**Versión**: 1.0
