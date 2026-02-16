#!/bin/bash
# Template Generator for Vertice360 Modules
# Usage: ./scripts/create_module.sh [module_name]

MODULE_NAME=$1

if [ -z "$MODULE_NAME" ]; then
    echo "Usage: ./create_module.sh [module_name]"
    echo "Example: ./create_module.sh notifications"
    exit 1
fi

# Convert to different cases
MODULE_SNAKE=$(echo "$MODULE_NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '_')
MODULE_CAMEL=$(echo "$MODULE_SNAKE" | sed -r 's/(^|_)([a-z])/\U\2/g')
MODULE_KEBAB=$(echo "$MODULE_SNAKE" | tr '_' '-')

echo "Creating module: $MODULE_SNAKE"

# Create backend structure
mkdir -p "backend/modules/${MODULE_SNAKE}"
mkdir -p "astro/src/lib/${MODULE_SNAKE}/ui"
mkdir -p "astro/src/pages/demo/${MODULE_KEBAB}"

echo "✓ Directories created"

# Backend: __init__.py
cat > "backend/modules/${MODULE_SNAKE}/__init__.py" << EOF
"""${MODULE_CAMEL} module for Vertice360."""

from .store import get_items, reset_store
from .services import process_item

__all__ = [
    "get_items",
    "reset_store",
    "process_item",
]
EOF

echo "✓ Backend __init__.py created"

# Backend: schemas.py
cat > "backend/modules/${MODULE_SNAKE}/schemas.py" << EOF
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

class ${MODULE_CAMEL}CreateRequest(BaseModel):
    """Request to create a new ${MODULE_NAME}."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    type: Literal["type_a", "type_b", "type_c"] = "type_a"
    
class ${MODULE_CAMEL}Response(BaseModel):
    """Response for ${MODULE_NAME} operations."""
    id: str
    name: str
    description: Optional[str]
    type: str
    status: Literal["pending", "active", "completed", "error"]
    created_at: datetime
    updated_at: Optional[datetime]
    metadata: dict = {}

class ${MODULE_CAMEL}ActionRequest(BaseModel):
    """Request to perform action on ${MODULE_NAME}."""
    action: Literal["activate", "pause", "complete", "cancel"]
    reason: Optional[str] = None
EOF

echo "✓ Backend schemas.py created"

# Backend: store.py
cat > "backend/modules/${MODULE_SNAKE}/store.py" << EOF
"""In-memory store for ${MODULE_NAME} (demo mode).
In production, replace with database operations."""

from typing import Any
from datetime import datetime
import uuid

# In-memory storage
_items: dict[str, dict[str, Any]] = {}

def _generate_id() -> str:
    """Generate unique ID."""
    return f"${MODULE_SNAKE[:3]}-{uuid.uuid4().hex[:12]}"

async def create_item(
    name: str,
    description: str | None = None,
    item_type: str = "type_a",
    metadata: dict | None = None
) -> dict[str, Any]:
    """Create a new item."""
    item_id = _generate_id()
    now = datetime.utcnow()
    
    item = {
        "id": item_id,
        "name": name,
        "description": description,
        "type": item_type,
        "status": "pending",
        "created_at": now,
        "updated_at": None,
        "metadata": metadata or {},
    }
    
    _items[item_id] = item
    return item

async def get_item(item_id: str) -> dict[str, Any] | None:
    """Get item by ID."""
    return _items.get(item_id)

async def get_items(
    status: str | None = None,
    item_type: str | None = None,
    limit: int = 50
) -> list[dict[str, Any]]:
    """Get items with optional filters."""
    items = list(_items.values())
    
    if status:
        items = [i for i in items if i["status"] == status]
    if item_type:
        items = [i for i in items if i["type"] == item_type]
    
    # Sort by created_at desc
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return items[:limit]

async def update_item(
    item_id: str,
    patch: dict[str, Any]
) -> dict[str, Any] | None:
    """Update item."""
    item = _items.get(item_id)
    if not item:
        return None
    
    for key, value in patch.items():
        if key in item and value is not None:
            item[key] = value
    
    item["updated_at"] = datetime.utcnow()
    return item

async def delete_item(item_id: str) -> bool:
    """Delete item."""
    if item_id in _items:
        del _items[item_id]
        return True
    return False

def reset_store() -> None:
    """Reset store (for testing)."""
    _items.clear()
EOF

echo "✓ Backend store.py created"

# Backend: services.py
cat > "backend/modules/${MODULE_SNAKE}/services.py" << EOF
"""Business logic for ${MODULE_NAME}."""

from . import store, events

async def process_item(
    name: str,
    description: str | None = None,
    item_type: str = "type_a",
    metadata: dict | None = None
) -> dict:
    """Process new item creation."""
    # Create item
    item = await store.create_item(
        name=name,
        description=description,
        item_type=item_type,
        metadata=metadata,
    )
    
    # Emit event
    await events.emit_${MODULE_SNAKE}_created(item)
    
    return item

async def perform_action(
    item_id: str,
    action: str,
    reason: str | None = None
) -> dict | None:
    """Perform action on item."""
    from datetime import datetime
    
    item = await store.get_item(item_id)
    if not item:
        return None
    
    # Map action to status
    status_map = {
        "activate": "active",
        "pause": "pending",
        "complete": "completed",
        "cancel": "error",
    }
    
    new_status = status_map.get(action)
    if not new_status:
        return None
    
    # Update item
    updated = await store.update_item(item_id, {
        "status": new_status,
        f"{action}_at": datetime.utcnow(),
        "action_reason": reason,
    })
    
    # Emit event
    await events.emit_${MODULE_SNAKE}_action(item_id, action, reason)
    
    return updated
EOF

echo "✓ Backend services.py created"

# Backend: events.py
cat > "backend/modules/${MODULE_SNAKE}/events.py" << EOF
"""AG-UI event publishing for ${MODULE_NAME}."""

import time
from backend.modules.agui_stream import broadcaster

async def emit_${MODULE_SNAKE}_created(item: dict) -> None:
    """Emit event when item is created."""
    await broadcaster.publish(
        "${MODULE_SNAKE}.created",
        {
            "type": "CUSTOM",
            "name": "${MODULE_SNAKE}.created",
            "timestamp": int(time.time() * 1000),
            "value": {
                "id": item["id"],
                "name": item["name"],
                "type": item["type"],
                "status": item["status"],
            },
            "correlationId": item["id"],
        }
    )

async def emit_${MODULE_SNAKE}_action(
    item_id: str,
    action: str,
    reason: str | None
) -> None:
    """Emit event when action is performed."""
    await broadcaster.publish(
        "${MODULE_SNAKE}.action",
        {
            "type": "CUSTOM",
            "name": "${MODULE_SNAKE}.action",
            "timestamp": int(time.time() * 1000),
            "value": {
                "id": item_id,
                "action": action,
                "reason": reason,
            },
            "correlationId": item_id,
        }
    )

async def emit_${MODULE_SNAKE}_updated(item: dict) -> None:
    """Emit event when item is updated."""
    await broadcaster.publish(
        "${MODULE_SNAKE}.updated",
        {
            "type": "CUSTOM",
            "name": "${MODULE_SNAKE}.updated",
            "timestamp": int(time.time() * 1000),
            "value": {
                "id": item["id"],
                "status": item["status"],
                "updatedAt": item["updated_at"],
            },
            "correlationId": item["id"],
        }
    )
EOF

echo "✓ Backend events.py created"

# Backend: routes
cat > "backend/routes/demo_${MODULE_SNAKE}.py" << EOF
"""Demo routes for ${MODULE_NAME}."""

from litestar import Controller, Router, get, post, delete
from litestar.exceptions import HTTPException

from backend.modules.${MODULE_SNAKE} import schemas, store, services


class ${MODULE_CAMEL}Controller(Controller):
    path = "/items"
    
    @get("")
    async def list_items(
        self,
        status: str | None = None,
        type: str | None = None,
        limit: int = 50
    ) -> list[dict]:
        """List items with optional filters."""
        return await store.get_items(status, type, limit)
    
    @get("/{item_id:str}")
    async def get_item(self, item_id: str) -> dict:
        """Get item by ID."""
        item = await store.get_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        return item
    
    @post("")
    async def create_item(self, data: schemas.${MODULE_CAMEL}CreateRequest) -> dict:
        """Create new item."""
        return await services.process_item(
            name=data.name,
            description=data.description,
            item_type=data.type,
        )
    
    @post("/{item_id:str}/action")
    async def perform_action(
        self,
        item_id: str,
        data: schemas.${MODULE_CAMEL}ActionRequest
    ) -> dict:
        """Perform action on item."""
        result = await services.perform_action(
            item_id=item_id,
            action=data.action,
            reason=data.reason,
        )
        if not result:
            raise HTTPException(status_code=404, detail="Item not found")
        return result
    
    @delete("/{item_id:str}")
    async def delete_item(self, item_id: str) -> dict:
        """Delete item."""
        success = await store.delete_item(item_id)
        if not success:
            raise HTTPException(status_code=404, detail="Item not found")
        return {"ok": True, "deleted": item_id}


@post("/reset")
async def reset_demo() -> dict:
    """Reset demo data."""
    store.reset_store()
    return {"ok": True}


router = Router(
    path="/api/demo/${MODULE_KEBAB}",
    route_handlers=[${MODULE_CAMEL}Controller, reset_demo],
)
EOF

echo "✓ Backend routes created"

# Frontend: types.js
cat > "astro/src/lib/${MODULE_SNAKE}/types.js" << EOF
/** @typedef {import('./types').${MODULE_CAMEL}Item} ${MODULE_CAMEL}Item */

export const ITEM_TYPES = {
  TYPE_A: 'type_a',
  TYPE_B: 'type_b', 
  TYPE_C: 'type_c',
};

export const ITEM_STATUSES = {
  PENDING: 'pending',
  ACTIVE: 'active',
  COMPLETED: 'completed',
  ERROR: 'error',
};

export const ITEM_ACTIONS = {
  ACTIVATE: 'activate',
  PAUSE: 'pause',
  COMPLETE: 'complete',
  CANCEL: 'cancel',
};

/**
 * Check if event is related to this module
 * @param {string} eventName
 * @returns {boolean}
 */
export function is${MODULE_CAMEL}Event(eventName) {
  return eventName?.startsWith('${MODULE_SNAKE}.');
}

/**
 * Get status badge color
 * @param {string} status
 * @returns {string}
 */
export function getStatusBadgeColor(status) {
  const colors = {
    pending: 'badge-warning',
    active: 'badge-success',
    completed: 'badge-info',
    error: 'badge-error',
  };
  return colors[status] || 'badge-ghost';
}
EOF

echo "✓ Frontend types.js created"

# Frontend: api.js
cat > "astro/src/lib/${MODULE_SNAKE}/api.js" << EOF
import { URL_REST } from '../../components/global.js';

const API_BASE = \`\${URL_REST}/api/demo/${MODULE_KEBAB}\`;

/**
 * @returns {Promise<{ok: boolean, data?: any, error?: string}>}
 */
export async function listItems(filters = {}) {
  const url = new URL(\`\${API_BASE}/items\`);
  Object.entries(filters).forEach(([key, value]) => {
    if (value) url.searchParams.set(key, value);
  });
  
  const response = await fetch(url);
  if (!response.ok) {
    return { ok: false, error: await response.text() };
  }
  return { ok: true, data: await response.json() };
}

/**
 * @param {string} itemId
 * @returns {Promise<{ok: boolean, data?: any, error?: string}>}
 */
export async function getItem(itemId) {
  const response = await fetch(\`\${API_BASE}/items/\${itemId}\`);
  if (!response.ok) {
    return { ok: false, error: await response.text() };
  }
  return { ok: true, data: await response.json() };
}

/**
 * @param {Object} data
 * @returns {Promise<{ok: boolean, data?: any, error?: string}>}
 */
export async function createItem(data) {
  const response = await fetch(\`\${API_BASE}/items\`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  
  if (!response.ok) {
    return { ok: false, error: await response.text() };
  }
  return { ok: true, data: await response.json() };
}

/**
 * @param {string} itemId
 * @param {string} action
 * @param {string} [reason]
 * @returns {Promise<{ok: boolean, data?: any, error?: string}>}
 */
export async function performAction(itemId, action, reason = null) {
  const response = await fetch(\`\${API_BASE}/items/\${itemId}/action\`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, reason }),
  });
  
  if (!response.ok) {
    return { ok: false, error: await response.text() };
  }
  return { ok: true, data: await response.json() };
}

/**
 * @param {string} itemId
 * @returns {Promise<{ok: boolean, error?: string}>}
 */
export async function deleteItem(itemId) {
  const response = await fetch(\`\${API_BASE}/items/\${itemId}\`, {
    method: 'DELETE',
  });
  
  if (!response.ok) {
    return { ok: false, error: await response.text() };
  }
  return { ok: true };
}

/**
 * @returns {Promise<{ok: boolean, error?: string}>}
 */
export async function resetDemo() {
  const response = await fetch(\`\${API_BASE}/reset\`, {
    method: 'POST',
  });
  
  if (!response.ok) {
    return { ok: false, error: await response.text() };
  }
  return { ok: true };
}
EOF

echo "✓ Frontend api.js created"

# Frontend: state.svelte.js
cat > "astro/src/lib/${MODULE_SNAKE}/state.svelte.js" << EOF
import * as api from './api.js';
import { ITEM_STATUSES } from './types.js';

const MAX_ITEMS = 100;

export function create${MODULE_CAMEL}State() {
  // Runes state
  let items = \$state([]);
  let selectedItemId = \$state(null);
  let loading = \$state(false);
  let error = \$state(null);
  let filters = \$state({ status: '', type: '' });
  
  // Getters
  const selectedItem = \$derived(
    selectedItemId ? items.find(i => i.id === selectedItemId) : null
  );
  
  const filteredItems = \$derived(() => {
    let result = [...items];
    if (filters.status) {
      result = result.filter(i => i.status === filters.status);
    }
    if (filters.type) {
      result = result.filter(i => i.type === filters.type);
    }
    return result;
  });
  
  // Actions
  async function loadItems() {
    loading = true;
    error = null;
    
    const result = await api.listItems(filters);
    
    if (!result.ok) {
      error = result.error;
      loading = false;
      return;
    }
    
    items = result.data.slice(0, MAX_ITEMS);
    loading = false;
  }
  
  async function create(data) {
    const result = await api.createItem(data);
    
    if (!result.ok) {
      error = result.error;
      return null;
    }
    
    // Optimistic update
    items = [result.data, ...items].slice(0, MAX_ITEMS);
    return result.data;
  }
  
  async function performAction(itemId, action, reason = null) {
    const result = await api.performAction(itemId, action, reason);
    
    if (!result.ok) {
      error = result.error;
      return false;
    }
    
    // Update local state
    const index = items.findIndex(i => i.id === itemId);
    if (index >= 0) {
      items[index] = result.data;
    }
    
    return true;
  }
  
  async function remove(itemId) {
    const result = await api.deleteItem(itemId);
    
    if (!result.ok) {
      error = result.error;
      return false;
    }
    
    items = items.filter(i => i.id !== itemId);
    if (selectedItemId === itemId) {
      selectedItemId = null;
    }
    
    return true;
  }
  
  async function reset() {
    const result = await api.resetDemo();
    
    if (!result.ok) {
      error = result.error;
      return false;
    }
    
    items = [];
    selectedItemId = null;
    return true;
  }
  
  function select(itemId) {
    selectedItemId = itemId;
  }
  
  function setFilters(newFilters) {
    filters = { ...filters, ...newFilters };
  }
  
  function applyEvent(evt) {
    // Handle SSE events
    if (evt.name === '${MODULE_SNAKE}.created') {
      const newItem = {
        id: evt.value?.id,
        name: evt.value?.name,
        type: evt.value?.type,
        status: evt.value?.status,
        created_at: new Date(evt.timestamp).toISOString(),
      };
      items = [newItem, ...items].slice(0, MAX_ITEMS);
    } else if (evt.name === '${MODULE_SNAKE}.action' || evt.name === '${MODULE_SNAKE}.updated') {
      // Reload to get updated state
      loadItems();
    }
  }
  
  return {
    get items() { return items; },
    get selectedItem() { return selectedItem; },
    get selectedItemId() { return selectedItemId; },
    get loading() { return loading; },
    get error() { return error; },
    get filters() { return filters; },
    get filteredItems() { return filteredItems; },
    loadItems,
    create,
    performAction,
    remove,
    reset,
    select,
    setFilters,
    applyEvent,
  };
}

export const ${MODULE_SNAKE}State = create${MODULE_CAMEL}State();
EOF

echo "✓ Frontend state.svelte.js created"

# Frontend: Main App Component
cat > "astro/src/lib/${MODULE_SNAKE}/ui/${MODULE_CAMEL}App.svelte" << EOF
<script>
  import { ${MODULE_SNAKE}State } from '../state.svelte.js';
  import { ITEM_TYPES, ITEM_STATUSES, ITEM_ACTIONS, getStatusBadgeColor } from '../types.js';
  
  // Load items on mount
  \$effect(() => {
    ${MODULE_SNAKE}State.loadItems();
  });
  
  let newItemName = \$state('');
  let newItemType = \$state(ITEM_TYPES.TYPE_A);
  
  async function handleCreate(e) {
    e.preventDefault();
    if (!newItemName.trim()) return;
    
    await ${MODULE_SNAKE}State.create({
      name: newItemName,
      type: newItemType,
    });
    
    newItemName = '';
  }
  
  async function handleAction(itemId, action) {
    await ${MODULE_SNAKE}State.performAction(itemId, action);
  }
</script>

<div class="container mx-auto px-4 py-6">
  <header class="mb-6">
    <h1 class="text-2xl md:text-3xl font-bold">${MODULE_CAMEL} Dashboard</h1>
    <p class="text-base-content/70">Manage your ${MODULE_NAME}</p>
  </header>
  
  <!-- Create Form -->
  <div class="card bg-base-200 mb-6">
    <div class="card-body">
      <h2 class="card-title text-lg">Create New</h2>
      <form onsubmit={handleCreate} class="flex flex-col sm:flex-row gap-2">
        <input
          type="text"
          bind:value={newItemName}
          placeholder="Enter name..."
          class="input input-bordered flex-1"
          required
        />
        <select bind:value={newItemType} class="select select-bordered">
          {#each Object.entries(ITEM_TYPES) as [key, value]}
            <option value={value}>{key}</option>
          {/each}
        </select>
        <button type="submit" class="btn btn-primary">Create</button>
      </form>
    </div>
  </div>
  
  <!-- Filters -->
  <div class="flex flex-wrap gap-2 mb-4">
    <select 
      class="select select-sm select-bordered"
      onchange={(e) => ${MODULE_SNAKE}State.setFilters({ status: e.target.value })}
    >
      <option value="">All Statuses</option>
      {#each Object.entries(ITEM_STATUSES) as [key, value]}
        <option value={value}>{key}</option>
      {/each}
    </select>
    
    <select 
      class="select select-sm select-bordered"
      onchange={(e) => ${MODULE_SNAKE}State.setFilters({ type: e.target.value })}
    >
      <option value="">All Types</option>
      {#each Object.entries(ITEM_TYPES) as [key, value]}
        <option value={value}>{key}</option>
      {/each}
    </select>
    
    <button 
      class="btn btn-sm btn-ghost"
      onclick={() => ${MODULE_SNAKE}State.loadItems()}
    >
      Refresh
    </button>
    
    <button 
      class="btn btn-sm btn-error btn-outline"
      onclick={() => ${MODULE_SNAKE}State.reset()}
    >
      Reset Demo
    </button>
  </div>
  
  <!-- Items List -->
  {#if ${MODULE_SNAKE}State.loading}
    <div class="flex justify-center py-12">
      <span class="loading loading-spinner loading-lg"></span>
    </div>
  {:else if ${MODULE_SNAKE}State.error}
    <div class="alert alert-error">
      <span>{${MODULE_SNAKE}State.error}</span>
    </div>
  {:else if ${MODULE_SNAKE}State.items.length === 0}
    <div class="text-center py-12 text-base-content/50">
      <p class="text-lg">No items found</p>
      <p class="text-sm">Create your first item above</p>
    </div>
  {:else}
    <div class="grid gap-4">
      {#each ${MODULE_SNAKE}State.filteredItems as item (item.id)}
        <div class="card bg-base-100 shadow-sm hover:shadow-md transition-shadow">
          <div class="card-body p-4">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-1">
                  <h3 class="font-semibold text-lg truncate">{item.name}</h3>
                  <span class="badge badge-sm {getStatusBadgeColor(item.status)}">
                    {item.status}
                  </span>
                </div>
                <p class="text-sm text-base-content/60">
                  {item.type} • {new Date(item.created_at).toLocaleString()}
                </p>
                {#if item.description}
                  <p class="text-sm mt-1">{item.description}</p>
                {/if}
              </div>
              
              <div class="flex flex-wrap gap-2">
                {#if item.status === ITEM_STATUSES.PENDING}
                  <button 
                    class="btn btn-xs btn-success"
                    onclick={() => handleAction(item.id, ITEM_ACTIONS.ACTIVATE)}
                  >
                    Activate
                  </button>
                {:else if item.status === ITEM_STATUSES.ACTIVE}
                  <button 
                    class="btn btn-xs btn-warning"
                    onclick={() => handleAction(item.id, ITEM_ACTIONS.PAUSE)}
                  >
                    Pause
                  </button>
                  <button 
                    class="btn btn-xs btn-info"
                    onclick={() => handleAction(item.id, ITEM_ACTIONS.COMPLETE)}
                  >
                    Complete
                  </button>
                {/if}
                
                <button 
                  class="btn btn-xs btn-error btn-outline"
                  onclick={() => ${MODULE_SNAKE}State.remove(item.id)}
                >
                  Delete
                </button>
              </div>
            </div>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
EOF

echo "✓ Frontend App component created"

# Frontend: Astro Page
cat > "astro/src/pages/demo/${MODULE_KEBAB}/index.astro" << EOF
---
import BaseLayout from '../../../layouts/BaseLayout.astro';
import ${MODULE_CAMEL}App from '../../../lib/${MODULE_SNAKE}/ui/${MODULE_CAMEL}App.svelte';
---

<BaseLayout title="${MODULE_CAMEL} Demo | Vertice360">
  <${MODULE_CAMEL}App client:load />
</BaseLayout>
EOF

echo "✓ Frontend page created"

echo ""
echo "=========================================="
echo "Module '$MODULE_SNAKE' created successfully!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Add to backend/ls_iMotorSoft_Srv01_demo.py:"
echo "   from routes.demo_${MODULE_SNAKE} import router as ${MODULE_SNAKE}_router"
echo "   route_handlers.append(${MODULE_SNAKE}_router)"
echo ""
echo "2. Add SSE handler in your app:"
echo "   import { is${MODULE_CAMEL}Event } from '../lib/${MODULE_SNAKE}/types.js';"
echo "   // In your SSE handler:"
echo "   if (is${MODULE_CAMEL}Event(evt.name)) {"
echo "     ${MODULE_SNAKE}State.applyEvent(evt);"
echo "   }"
echo ""
echo "3. Access demo at: http://localhost:3062/demo/${MODULE_KEBAB}"
echo ""
echo "4. Run tests: pytest backend/tests/test_${MODULE_SNAKE}*.py -v"
echo ""
