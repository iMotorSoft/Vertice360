# Demo Vertice360 Orquestador - DB v360

## Variables de entorno

Configurar en shell (`~/.bashrc` o equivalente):

```bash
export DB_PG_V360_URL="postgresql+psycopg://USER:PASS@HOST:5432/v360"
# Seguro por defecto (no fallback):
export ALLOW_FALLBACK_V360_DB=false
```

## Validaciones aplicadas en `backend/globalVar.py`

- `DB_PG_V360_URL` debe usar esquema Postgres (`postgresql`, `postgresql+psycopg` o `postgres`).
- Debe apuntar a base `v360` (`/v360` o `?dbname=v360`).
- Si falta o es inválida, se loguea `WARNING`.
- Solo se usa fallback a `VERTICE360_DB_URL` cuando `ALLOW_FALLBACK_V360_DB=true`.

## Endpoints demo

Base path:

`/api/demo/vertice360-orquestador`

Incluye:

- `GET /bootstrap`
- `GET /dashboard`
- `POST /ingest_message`
- `POST /visit/propose`
- `POST /visit/confirm`
- `POST /visit/reschedule`
- `POST /supervisor/send`

## Estado actual DB / Resolver (2026-03-04 14:15:10 -03 | 2026-03-04 17:15:10 UTC)

### Cambios funcionales activos

- Se incorporó `Project Knowledge Resolver` en backend para responder consultas de proyecto usando solo DB local.
- Se agregó discovery de schema en runtime y mapa de capabilities.
- Se agregó trazabilidad QA:
  - eventos `orq.qa.requested` y `orq.qa.responded`
  - `summary_jsonb`: `last_intent`, `last_query`, `last_answer_brief`, `last_data_sources`
- Se mantiene guardrail de visita:
  - stage a `Pendiente de visita`
  - eventos `orq.stage.updated` y `orq.visit.requested`
  - Vera no propone horarios automáticos.

### Discovery real (schema `public`, base `v360`)

Tablas candidatas detectadas para conocimiento de proyecto:

- `projects`
  - `id`, `developer_id`, `code`, `name`, `description`, `location_jsonb`, `tags`, `status`, `created_at`, `updated_at`
- `marketing_assets`
  - `id`, `project_id`, `channel`, `title`, `short_copy`, `chips`, `whatsapp_prefill`, `is_active`, `sort_order`, `created_at`

### Capabilities detectadas

- `project_overview=true`
- `location=true`
- `amenities=true`
- `marketing_assets=true`
- `unit_types=false`
- `prices_by_rooms=false`
- `availability_by_rooms=false`
- `financing=false`
- `delivery_date=false`

### SQL ejecutadas por el resolver (trazabilidad)

- Discovery:
  - `select lower(table_name) as table_name, lower(column_name) as column_name from information_schema.columns where table_schema = current_schema() order by table_name asc, ordinal_position asc`
- Overview por proyecto:
  - `select p.* from "projects" p where upper(p."code"::text) = upper(%s) limit 1`
- Marketing assets por proyecto:
  - `select ma.* from "marketing_assets" ma join "projects" p on p."id" = ma."project_id" where upper(p."code"::text) = upper(%s) and coalesce(ma."is_active", true) = true order by ma."sort_order" asc, ma."created_at" asc limit 30`
- Delivery fallback (por estado en `projects`):
  - `select p."status" as status from "projects" p where upper(p."code"::text) = upper(%s) limit 1`

### Validación manual (MANZANARES_3277)

Mensajes probados:

1. `qué amenities tiene?` -> responde con datos de `marketing_assets/projects` (OK)
2. `dame precio de 2 ambientes` -> no inventa y pide moneda mínima faltante (OK)
3. `hay financiación?` -> deriva a asesor por falta de datos en DB (OK)
4. `cuándo entregan?` -> responde estado real cargado (OK)
5. `coordinamos una visita?` -> stage `Pendiente de visita` + eventos de visita (OK)

Persistencia verificada:

- eventos `orq.qa.*` guardados
- `summary_jsonb` actualizado con campos de trazabilidad QA

### Endpoint administrativo de capabilities (DEV)

- `GET /api/demo/vertice360-orquestador/knowledge/capabilities?force_refresh=true`
- Requiere header: `x-v360-admin-token`

---

## Estado post-seed demo bundles (2026-03-04 17:09:55 -03 | 2026-03-04 20:09:55 UTC)

### DDL idempotente aplicado

Archivo:

- `db/demo_project_knowledge_schema.sql`

Tablas nuevas:

- `demo_project_bundles`
- `demo_project_facts`
- `demo_units`

### Seed loader ejecutado

Script:

- `scripts/seed_demo_project_knowledge.py`

Comando:

```bash
PYTHONPATH=.. python scripts/seed_demo_project_knowledge.py
```

Resultado:

- `projects=3`
- `units=10`

### Datos cargados por proyecto (resumen)

- `BULNES_966_ALMAGRO`: facts de ubicación/amenities + 3 unidades (1 y 2 ambientes, USD).
- `GDR_3760_SAAVEDRA`: facts de ubicación/entrega + 3 unidades (3 ambientes opción 4, USD).
- `MANZANARES_3277`: facts de ubicación/amenities/financiación/entrega + 4 unidades (2 y 3 ambientes, USD).

### Fuentes públicas web usadas (para completar facts/unidades)

Bulnes:

- https://www.zonaprop.com.ar/propiedades/emprendimiento/ememvein-bulnes-966.-56328869.html
- https://www.zonaprop.com.ar/propiedades/clasificado/veclapin-departamento-2-ambientes-con-balcon-bulnes-966-almagro-56191460.html
- https://www.zonaprop.com.ar/propiedades/emprendimiento/veunapin-venta-monoambiente-amplia-financiacion-57026250.html
- https://www.zonaprop.com.ar/propiedades/emprendimiento/veunapin-venta-monoambiente-amplia-financiacion-57026243.html

GDR:

- https://www.zonaprop.com.ar/propiedades/emprendimiento/ememvein-garcia-del-rio-3760-56802375.html
- https://www.zonaprop.com.ar/propiedades/emprendimiento/veunapin-venta-3-amb-opcion-4-amb-balcon-terraza-saavedra-56802381.html
- https://www.zonaprop.com.ar/propiedades/emprendimiento/veunapin-venta-3-ambientes-con-balcon-terraza-en-saavedra-56802376.html
- https://www.zonaprop.com.ar/propiedades/emprendimiento/veunapin-venta-3-ambientes-con-balcon-terraza-en-saavedra-56802379.html

Manzanares:

- https://www.zonaprop.com.ar/propiedades/emprendimiento/ememvein-manzanares-3277-57226433.html
- https://www.zonaprop.com.ar/propiedades/emprendimiento/veunapin-venta-2-ambientes-con-balcon-en-saavedra-57226441.html
- https://www.zonaprop.com.ar/propiedades/emprendimiento/veunapin-venta-2-ambientes-con-balcon-en-saavedra-57226439.html
- https://www.zonaprop.com.ar/propiedades/emprendimiento/veunapna-venta-3-ambientes-con-jardin-en-saavedra-57226436.html
- https://www.zonaprop.com.ar/propiedades/emprendimiento/veunapin-venta-3-ambientes-con-balcon-terraza-en-saavedra-57226438.html

### Capabilities actuales (force_refresh=true)

- `project_overview=true`
- `location=true`
- `amenities=true`
- `marketing_assets=true`
- `unit_types=true`
- `prices_by_rooms=true`
- `availability_by_rooms=true`
- `financing=true`
- `delivery_date=true`

### Queries de verificación ejecutadas

```sql
select code,name,location_jsonb from projects order by code;
select project_code, count(*) from demo_units group by 1 order by 1;
select min(list_price), max(list_price)
from demo_units
where project_code = 'MANZANARES_3277'
  and (typology like '2%' or rooms_label ilike '2%');
```

### Endpoint admin adicional (debug)

- `GET /api/demo/vertice360-orquestador/knowledge/debug/project?code=MANZANARES_3277`
- Requiere header: `x-v360-admin-token`
