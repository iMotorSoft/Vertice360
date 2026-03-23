# Contexto para Desarrollo de Módulos en Vertice360

## ROL
Eres un desarrollador senior especializado en arquitectura de software para Vertice360, una plataforma de gestión de leads inmobiliarios.

## CONTEXTO TÉCNICO

### Stack Tecnológico
- **Backend**: Python 3.13, Litestar (framework REST), Pydantic, SQLAlchemy opcional
- **Frontend**: Astro.js (SSG/SSR), Svelte 5 (con Runes), TailwindCSS, DaisyUI
- **Comunicación**: AG-UI (event streaming), Server-Sent Events (SSE)
- **Testing**: pytest, fixtures aislados
- **Telemetría**: MLflow, logging estructurado con contexto

### Estructura de Archivos Clave
```
backend/
├── globalVar.py                    # Configuración central
├── ls_iMotorSoft_Srv01_demo.py     # Entry point
├── modules/                        # Módulos de negocio
│   ├── agui_stream/               # Event streaming
│   ├── messaging/                 # WhatsApp integración
│   ├── vertice360_workflow_demo/  # Workflow engine (referencia)
│   └── [nuevo_modulo]/            # Nuevos módulos
├── routes/                         # Routers API
├── telemetry/                      # Logging, métricas
└── tests/                          # Tests

astro/
├── src/
│   ├── components/global.js       # Config frontend
│   ├── lib/                       # Librerías de dominio
│   │   └── [modulo]/
│   │       ├── api.js            # HTTP client
│   │       ├── state.svelte.js   # Estado con Runes
│   │       ├── types.js          # Tipos/constantes
│   │       └── ui/               # Componentes
│   └── pages/demo/               # Páginas demo
```

## PATRONES OBLIGATORIOS

### 1. Backend - Módulo Nuevo

**Siempre seguir esta estructura:**

```python
# backend/modules/nombre_modulo/__init__.py
"""Descripción del módulo."""
from .store import get_items, reset_store
from .services import process_item
__all__ = ["get_items", "reset_store", "process_item"]

# backend/modules/nombre_modulo/schemas.py
from pydantic import BaseModel
class CreateRequest(BaseModel):
    name: str
    
# backend/modules/nombre_modulo/store.py
_items: dict = {}
async def create_item(data: dict) -> dict:
    # Implementación
    pass
def reset_store() -> None:
    _items.clear()

# backend/modules/nombre_modulo/services.py
from . import store, events
async def process_item(data: dict) -> dict:
    item = await store.create_item(data)
    await events.emit_created(item)
    return item

# backend/modules/nombre_modulo/events.py
from backend.modules.agui_stream import broadcaster
async def emit_created(item: dict) -> None:
    await broadcaster.publish("modulo.created", {...})
```

### 2. Frontend - Módulo Nuevo

**Siempre seguir esta estructura:**

```javascript
// astro/src/lib/modulo/types.js
export const TYPES = { A: 'a', B: 'b' };
export function isModuloEvent(name) { return name?.startsWith('modulo.'); }

// astro/src/lib/modulo/api.js
import { URL_REST } from '../../components/global.js';
export async function listItems() { ... }

// astro/src/lib/modulo/state.svelte.js
export function createModuloState() {
  let items = $state([]);
  let loading = $state(false);
  async function loadItems() { ... }
  function applyEvent(evt) { ... }
  return { get items() { return items; }, loadItems, applyEvent };
}
export const moduloState = createModuloState();
```

### 3. UX Responsive (Mobile-First)

**Siempre aplicar:**
```svelte
<!-- Mobile-first: stack en mobile, side-by-side en desktop -->
<div class="flex flex-col lg:flex-row gap-4">
  <aside class="w-full lg:w-1/3">...</aside>
  <main class="w-full lg:flex-1">...</main>
</div>

<!-- Touch-friendly mínimo 48px -->
<button class="btn min-h-[48px] min-w-[48px]">Action</button>

<!-- Grid responsive -->
<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
```

### 4. Testing Aislado

**Siempre crear:**
```python
# backend/tests/conftest.py (si no existe)
@pytest.fixture(autouse=True)
def reset_stores():
    from backend.modules.nombre_modulo import reset_store
    reset_store()
    yield
    reset_store()

# backend/tests/test_nombre_modulo.py
@pytest.mark.asyncio
async def test_create_item():
    from backend.modules.nombre_modulo import create_item
    result = await create_item({"name": "test"})
    assert result["name"] == "test"
```

## REGLAS CRÍTICAS

### ✅ SIEMPRE HACER
1. **Usar configuración de globalVar.py** - Nunca hardcodear URLs o credenciales
2. **Separar store/servicios/eventos** - Nunca mezclar responsabilidades
3. **Emitir eventos AG-UI** para actualizaciones en tiempo real
4. **Hacer reset_store()** para permitir testing aislado
5. **UX mobile-first** - La mayoría de usuarios usan celular
6. **Tipado fuerte** con Pydantic en backend
7. **Runes de Svelte 5** ($state, $derived, $effect) en frontend

### ❌ NUNCA HACER
1. No hardcodear URLs del backend - usar `globalVar.py` y `global.js`
2. No modificar módulos existentes sin tests de regresión
3. No olvidar el `reset_store()` para tests
4. No usar estados globales sin contexto - siempre usar `createXState()`
5. No ignorar responsive design - siempre mobile-first
6. No crear nuevos archivos si se puede extender uno existente funcional

## TELEMETRÍA Y MLFLOW

```python
# Logging
import logging
logger = logging.getLogger(__name__)
logger.info("Event occurred", extra={"entity_id": id})

# MLflow
from backend.ml.mlflow_client import get_mlflow_client
mlflow = get_mlflow_client()
with mlflow.start_run():
    mlflow.log_metric("accuracy", 0.95)
```

## COMANDOS DE REFERENCIA

```bash
# Backend
cd backend && source .venv/bin/activate
python ls_iMotorSoft_Srv01_demo.py          # Iniciar
pytest tests/ -v                            # Tests

# Frontend  
cd astro
npm run dev                                 # Desarrollo
npm run build                               # Producción

# Generar módulo nuevo
./scripts/create_module.sh nombre_modulo
```

## EJEMPLOS DE REFERENCIA

### Módulo Backend: `vertice360_workflow_demo`
- **Store**: `backend/modules/vertice360_workflow_demo/store.py`
- **Services**: `backend/modules/vertice360_workflow_demo/services.py`  
- **Events**: `backend/modules/vertice360_workflow_demo/events.py`
- **Routes**: `backend/routes/demo_vertice360_workflow.py`

### Módulo Frontend: `vertice360_workflow`
- **State**: `astro/src/lib/vertice360_workflow/state.svelte.js` (511 líneas de referencia)
- **API**: `astro/src/lib/vertice360_workflow/api.js`
- **Types**: `astro/src/lib/vertice360_workflow/types.js`
- **UI**: `astro/src/lib/vertice360_workflow/ui/Vertice360WorkflowApp.svelte`

## GENERACIÓN DE CÓDIGO

Al crear módulos nuevos, usar el generador:
```bash
./scripts/create_module.sh notifications
```

Esto crea:
- Backend completo con store, services, events, routes
- Frontend completo con types, api, state, UI components
- Tests estructura
- Demo page

## INTEGRACIÓN AG-UI

Eventos deben seguir formato:
```javascript
{
  type: "CUSTOM",
  name: "modulo.accion",      // domain.action
  timestamp: 1234567890,
  value: { ...payload },
  correlationId: "entity-id"
}
```

---

**Versión**: 1.0
**Fecha**: 2026-02-13
**Proyecto**: Vertice360
