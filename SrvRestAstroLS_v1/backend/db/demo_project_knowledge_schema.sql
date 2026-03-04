-- Demo project knowledge schema (idempotent) for v360

create table if not exists demo_project_bundles (
    id bigserial primary key,
    workspace_id text not null,
    project_code text not null,
    schema_version text not null,
    bundle_jsonb jsonb not null,
    source_urls jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (workspace_id, project_code)
);

alter table demo_project_bundles add column if not exists workspace_id text;
alter table demo_project_bundles add column if not exists project_code text;
alter table demo_project_bundles add column if not exists schema_version text;
alter table demo_project_bundles add column if not exists bundle_jsonb jsonb;
alter table demo_project_bundles add column if not exists source_urls jsonb;
alter table demo_project_bundles add column if not exists created_at timestamptz;
alter table demo_project_bundles add column if not exists updated_at timestamptz;
alter table demo_project_bundles alter column source_urls set default '[]'::jsonb;
alter table demo_project_bundles alter column created_at set default now();
alter table demo_project_bundles alter column updated_at set default now();

create index if not exists idx_demo_project_bundles_project_code
    on demo_project_bundles (project_code);


create table if not exists demo_project_facts (
    project_code text primary key,
    workspace_id text not null,
    location_jsonb jsonb,
    amenities_jsonb jsonb,
    construction_jsonb jsonb,
    financing_jsonb jsonb,
    tags_jsonb jsonb,
    unit_types_jsonb jsonb,
    description text,
    source_urls jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table demo_project_facts add column if not exists project_code text;
alter table demo_project_facts add column if not exists workspace_id text;
alter table demo_project_facts add column if not exists location_jsonb jsonb;
alter table demo_project_facts add column if not exists amenities_jsonb jsonb;
alter table demo_project_facts add column if not exists construction_jsonb jsonb;
alter table demo_project_facts add column if not exists financing_jsonb jsonb;
alter table demo_project_facts add column if not exists tags_jsonb jsonb;
alter table demo_project_facts add column if not exists unit_types_jsonb jsonb;
alter table demo_project_facts add column if not exists description text;
alter table demo_project_facts add column if not exists source_urls jsonb;
alter table demo_project_facts add column if not exists created_at timestamptz;
alter table demo_project_facts add column if not exists updated_at timestamptz;
alter table demo_project_facts alter column source_urls set default '[]'::jsonb;
alter table demo_project_facts alter column created_at set default now();
alter table demo_project_facts alter column updated_at set default now();

create index if not exists idx_demo_project_facts_workspace_project
    on demo_project_facts (workspace_id, project_code);


create table if not exists demo_units (
    id bigserial primary key,
    workspace_id text not null,
    project_code text not null,
    unit_id text not null,
    unit_code text,
    typology text,
    rooms_label text,
    rooms_count integer,
    bedrooms integer,
    bathrooms numeric(6,2),
    surface_total_m2 numeric(10,2),
    surface_covered_m2 numeric(10,2),
    currency text,
    list_price numeric(14,2),
    availability_status text not null default 'unknown',
    features_jsonb jsonb not null default '[]'::jsonb,
    source_url text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (workspace_id, project_code, unit_id)
);

alter table demo_units add column if not exists workspace_id text;
alter table demo_units add column if not exists project_code text;
alter table demo_units add column if not exists unit_id text;
alter table demo_units add column if not exists unit_code text;
alter table demo_units add column if not exists typology text;
alter table demo_units add column if not exists rooms_label text;
alter table demo_units add column if not exists rooms_count integer;
alter table demo_units add column if not exists bedrooms integer;
alter table demo_units add column if not exists bathrooms numeric(6,2);
alter table demo_units add column if not exists surface_total_m2 numeric(10,2);
alter table demo_units add column if not exists surface_covered_m2 numeric(10,2);
alter table demo_units add column if not exists currency text;
alter table demo_units add column if not exists list_price numeric(14,2);
alter table demo_units add column if not exists availability_status text;
alter table demo_units add column if not exists features_jsonb jsonb;
alter table demo_units add column if not exists source_url text;
alter table demo_units add column if not exists created_at timestamptz;
alter table demo_units add column if not exists updated_at timestamptz;
alter table demo_units alter column availability_status set default 'unknown';
alter table demo_units alter column features_jsonb set default '[]'::jsonb;
alter table demo_units alter column created_at set default now();
alter table demo_units alter column updated_at set default now();

create index if not exists idx_demo_units_project_code
    on demo_units (project_code);
create index if not exists idx_demo_units_project_rooms
    on demo_units (project_code, rooms_count);
create index if not exists idx_demo_units_project_status
    on demo_units (project_code, availability_status);
create index if not exists idx_demo_units_price
    on demo_units (project_code, currency, list_price);
