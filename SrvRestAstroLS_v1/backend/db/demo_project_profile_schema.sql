-- Additive schema for project/unit conversational profiles in v360 demo

create table if not exists demo_project_profile (
    project_code text primary key,
    workspace_id text not null,
    inventory_scope_type text not null,
    inventory_scope_label text,
    units_total integer,
    available_units integer,
    reserved_units integer,
    unavailable_units integer,
    inventory_is_complete boolean not null default false,
    inventory_as_of timestamptz,
    children_suitable boolean,
    pets_allowed boolean,
    pets_restrictions_text text,
    pool_safety text,
    raw_status_breakdown_jsonb jsonb not null default '{}'::jsonb,
    child_safety_warnings_jsonb jsonb not null default '[]'::jsonb,
    usage_warnings_jsonb jsonb not null default '[]'::jsonb,
    recommended_profiles_jsonb jsonb not null default '[]'::jsonb,
    source_urls jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint fk_demo_project_profile_project_code
        foreign key (project_code)
        references demo_project_facts (project_code)
        on delete cascade,
    constraint chk_demo_project_profile_inventory_scope_type
        check (inventory_scope_type in ('project', 'building', 'condominium')),
    constraint chk_demo_project_profile_pool_safety
        check (pool_safety is null or pool_safety in ('safe', 'unsafe', 'not_applicable', 'unknown')),
    constraint chk_demo_project_profile_units_total_nonnegative
        check (units_total is null or units_total >= 0),
    constraint chk_demo_project_profile_available_units_nonnegative
        check (available_units is null or available_units >= 0),
    constraint chk_demo_project_profile_reserved_units_nonnegative
        check (reserved_units is null or reserved_units >= 0),
    constraint chk_demo_project_profile_unavailable_units_nonnegative
        check (unavailable_units is null or unavailable_units >= 0),
    constraint chk_demo_project_profile_raw_status_breakdown_object
        check (jsonb_typeof(raw_status_breakdown_jsonb) = 'object'),
    constraint chk_demo_project_profile_child_safety_warnings_array
        check (jsonb_typeof(child_safety_warnings_jsonb) = 'array'),
    constraint chk_demo_project_profile_usage_warnings_array
        check (jsonb_typeof(usage_warnings_jsonb) = 'array'),
    constraint chk_demo_project_profile_recommended_profiles_array
        check (jsonb_typeof(recommended_profiles_jsonb) = 'array'),
    constraint chk_demo_project_profile_source_urls_array
        check (jsonb_typeof(source_urls) = 'array')
);

create table if not exists demo_unit_profile (
    workspace_id text not null,
    project_code text not null,
    unit_id text not null,
    orientation text,
    exposure text,
    view_text text,
    sun_morning boolean,
    sun_afternoon boolean,
    natural_light text,
    cross_ventilation boolean,
    thermal_comfort_notes text,
    balcony_protection text,
    children_suitable boolean,
    pets_allowed boolean,
    pets_restrictions_text text,
    has_garage boolean,
    has_storage boolean,
    has_patio boolean,
    has_garden boolean,
    child_safety_warnings_jsonb jsonb not null default '[]'::jsonb,
    usage_warnings_jsonb jsonb not null default '[]'::jsonb,
    commercial_features_jsonb jsonb not null default '{}'::jsonb,
    recommended_profiles_jsonb jsonb not null default '[]'::jsonb,
    source_urls jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (workspace_id, project_code, unit_id),
    constraint fk_demo_unit_profile_demo_unit
        foreign key (workspace_id, project_code, unit_id)
        references demo_units (workspace_id, project_code, unit_id)
        on delete cascade,
    constraint chk_demo_unit_profile_natural_light
        check (natural_light is null or natural_light in ('low', 'medium', 'high')),
    constraint chk_demo_unit_profile_balcony_protection
        check (
            balcony_protection is null
            or balcony_protection in ('protected', 'unprotected', 'partial', 'not_applicable', 'unknown')
        ),
    constraint chk_demo_unit_profile_child_safety_warnings_array
        check (jsonb_typeof(child_safety_warnings_jsonb) = 'array'),
    constraint chk_demo_unit_profile_usage_warnings_array
        check (jsonb_typeof(usage_warnings_jsonb) = 'array'),
    constraint chk_demo_unit_profile_commercial_features_object
        check (jsonb_typeof(commercial_features_jsonb) = 'object'),
    constraint chk_demo_unit_profile_recommended_profiles_array
        check (jsonb_typeof(recommended_profiles_jsonb) = 'array'),
    constraint chk_demo_unit_profile_source_urls_array
        check (jsonb_typeof(source_urls) = 'array')
);

create index if not exists idx_demo_unit_profile_project_code
    on demo_unit_profile (project_code);

create index if not exists idx_demo_unit_profile_unit_id
    on demo_unit_profile (unit_id);

create index if not exists idx_demo_unit_profile_children_suitable
    on demo_unit_profile (children_suitable);

create index if not exists idx_demo_unit_profile_pets_allowed
    on demo_unit_profile (pets_allowed);

create index if not exists idx_demo_unit_profile_has_garden
    on demo_unit_profile (has_garden);

create index if not exists idx_demo_unit_profile_has_patio
    on demo_unit_profile (has_patio);

comment on table demo_project_profile is
    'Complementary 1:1 project profile for additive conversational facts.';

comment on column demo_project_profile.inventory_scope_type is
    'Allowed values: project, building, condominium.';

comment on column demo_project_profile.pool_safety is
    'Allowed values: safe, unsafe, not_applicable, unknown.';

comment on table demo_unit_profile is
    'Complementary 1:1 unit profile for additive conversational facts.';

comment on column demo_unit_profile.natural_light is
    'Allowed values: low, medium, high.';

comment on column demo_unit_profile.balcony_protection is
    'Allowed values: protected, unprotected, partial, not_applicable, unknown.';
