# Vertice360 - Guía Rápida de Desarrollo

## 🎯 Documentos Principales

1. **[ARQUITECTURA_MODULOS.md](./ARQUITECTURA_MODULOS.md)** - Guía completa de arquitectura
2. **[CONTEXT_DESARROLLO.md](./CONTEXT_DESARROLLO.md)** - Contexto para prompts de IA
3. **Plantilla de módulo**: `../scripts/create_module.sh`

## 🚀 Crear Nuevo Módulo (En 5 minutos)

```bash
cd Vertice360/SrvRestAstroLS_v1
./scripts/create_module.sh notifications
```

Esto genera automáticamente:
- ✅ Backend completo (store, services, events, routes)
- ✅ Frontend completo (types, api, state, UI)
- ✅ Tests estructura
- ✅ Página demo

## 📋 Checklist Rápido

### Backend
- [ ] Ejecutar `./scripts/create_module.sh nombre`
- [ ] Editar schemas según necesidad
- [ ] Agregar lógica de negocio en services.py
- [ ] Agregar router en `ls_iMotorSoft_Srv01_demo.py`
- [ ] Crear tests en `backend/tests/`

### Frontend
- [ ] Verificar types.js tiene constantes necesarias
- [ ] Implementar llamadas API en api.js
- [ ] Crear estado con Runes en state.svelte.js
- [ ] Diseñar UI responsive mobile-first
- [ ] Crear página en `astro/src/pages/demo/`

### Integración
- [ ] Agregar manejador SSE para eventos del módulo
- [ ] Verificar CORS permite llamadas desde Astro
- [ ] Probar en mobile (responsive)
- [ ] Ejecutar `pytest` - todos deben pasar

## 🏗️ Arquitectura

### Backend (Python 3.13 + Litestar)
```
backend/modules/[modulo]/
├── __init__.py       # Exports públicos
├── schemas.py        # Pydantic models
├── store.py          # Estado/almacenamiento
├── services.py       # Lógica de negocio
└── events.py         # Eventos AG-UI
```

### Frontend (Astro.js + Svelte 5)
```
astro/src/lib/[modulo]/
├── types.js          # Constantes y tipos
├── api.js            # HTTP client
├── state.svelte.js   # Estado con Runes
├── sse.js            # Event handler (opcional)
└── ui/               # Componentes Svelte
    └── [Modulo]App.svelte
```

## 📱 UX Responsive (Mobile-First)

```svelte
<!-- Siempre mobile-first -->
<div class="flex flex-col lg:flex-row">
  <aside class="w-full lg:w-1/3">...</aside>
  <main class="w-full lg:flex-1">...</main>
</div>

<!-- Touch-friendly -->
<button class="min-h-[48px] min-w-[48px]">Action</button>

<!-- Grid responsive -->
<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
```

## 🧪 Testing

```bash
# Todos los tests
cd backend && pytest tests/ -v

# Tests específicos
pytest tests/test_nombre_modulo.py -v

# Con cobertura
pytest tests/ --cov=backend/modules --cov-report=html
```

### Fixture Obligatorio
```python
# conftest.py
@pytest.fixture(autouse=True)
def reset_stores():
    from backend.modules.nombre_modulo import reset_store
    reset_store()
    yield
    reset_store()
```

## 🔧 Configuración

### Backend (`backend/globalVar.py`)
```python
ENVIRONMENT: Literal["dev", "stg", "prod"]
DEBUG: bool = RUN_ENV != "prod"
HOST: str = "0.0.0.0"
PORT: int = 7062
MLFLOW_TRACKING_URI: str
```

### Frontend (`astro/src/components/global.js`)
```javascript
const URL_REST_DEV = 'http://localhost:7062';
const URL_REST_PRO = 'https://demo.vertice360.imotorsoft.com';
export const URL_REST = URL_REST_DEV; // Cambiar para prod
export const URL_SSE = `${URL_REST}/api/agui/stream`;
```

## 📡 AG-UI (Event Streaming)

### Publicar Evento (Backend)
```python
from backend.modules.agui_stream import broadcaster

await broadcaster.publish(
    "modulo.evento",
    {
        "type": "CUSTOM",
        "name": "modulo.evento",
        "timestamp": int(time.time() * 1000),
        "value": {...},
        "correlationId": entity_id,
    }
)
```

### Suscribirse (Frontend)
```javascript
// En tu manejador SSE global
if (evt.name === 'modulo.evento') {
  moduloState.applyEvent(evt);
}
```

## 📊 Telemetría

```python
# Logging estructurado
import logging
logger = logging.getLogger(__name__)
logger.info("Evento", extra={"entity_id": id})

# MLflow
from backend.ml.mlflow_client import get_mlflow_client
mlflow = get_mlflow_client()
with mlflow.start_run():
    mlflow.log_metric("accuracy", 0.95)
```

## 🎯 Ejemplos de Referencia

### Módulos Backend Implementados
- `vertice360_workflow_demo/` - Workflow de tickets
- `vertice360_ai_workflow_demo/` - Workflow con AI
- `messaging/` - WhatsApp (Meta/Gupshup)
- `crm_demo/` - CRM básico

### Módulos Frontend Implementados
- `vertice360_workflow/` - UI de workflow
- `vertice360_ai_workflow_studio/` - Studio de workflow AI
- `crm/` - UI de CRM

## 💻 Comandos de Desarrollo

```bash
# Iniciar backend
cd backend && python ls_iMotorSoft_Srv01_demo.py

# Iniciar frontend
cd astro && npm run dev

# Tests
cd backend && pytest tests/ -v

# Build producción
cd astro && npm run build
```

## ⚠️ Reglas Importantes

### ✅ Siempre
- Usar configuración de `globalVar.py` y `global.js`
- Separar store/servicios/eventos
- Emitir eventos AG-UI para updates en tiempo real
- Mobile-first responsive design
- Tipado fuerte (Pydantic/Svelte Runes)
- Tests con `reset_store()`

### ❌ Nunca
- Hardcodear URLs o credenciales
- Modificar módulos existentes sin tests
- Ignorar mobile (mayoría usa celular)
- Crear archivos nuevos si se puede extender existente

## 📚 Documentación Adicional

- [ARQUITECTURA_MODULOS.md](./ARQUITECTURA_MODULOS.md) - Guía completa
- [CONTEXT_DESARROLLO.md](./CONTEXT_DESARROLLO.md) - Contexto para IA
- `../scripts/create_module.sh` - Generador de módulos

## 🤝 Soporte

Para dudas sobre arquitectura:
1. Revisar ejemplos existentes en `backend/modules/`
2. Consultar `ARQUITECTURA_MODULOS.md`
3. Usar el generador `./scripts/create_module.sh`

---

**Última actualización**: 2026-02-13
**Versión**: 1.0
