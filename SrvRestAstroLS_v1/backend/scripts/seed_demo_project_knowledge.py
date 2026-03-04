from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import psycopg

from backend import globalVar

WORKSPACE_ID = "ws_demo_vertice360"
SCHEMA_VERSION = "v360.demo.project_bundle.v1"


def _conninfo() -> str:
    return globalVar.get_v360_db_url().replace("postgresql+psycopg://", "postgresql://")


def _schema_sql() -> str:
    path = Path(__file__).resolve().parents[1] / "db" / "demo_project_knowledge_schema.sql"
    return path.read_text(encoding="utf-8")


def _bundles() -> list[dict[str, Any]]:
    return [
        {
            "workspace_id": WORKSPACE_ID,
            "schema_version": SCHEMA_VERSION,
            "project": {
                "project_id": "prj_bulnes_966_2026",
                "project_code": "BULNES_966_ALMAGRO",
                "name": "Bulnes 966 — Almagro",
                "status": "activo",
                "description": (
                    "Edificio de 1 y 2 ambientes en preventa, con enfoque en primera vivienda e inversión "
                    "en el corredor Almagro/Palermo."
                ),
                "location": {
                    "address": "Bulnes 966",
                    "barrio": "Almagro",
                    "ciudad": "CABA",
                    "pais": "AR",
                },
                "tags": ["Almagro", "1 y 2 ambientes", "Solarium", "Bike parking", "Inversion"],
                "source_urls": [
                    "https://www.zonaprop.com.ar/propiedades/emprendimiento/ememvein-bulnes-966.-56328869.html",
                    "https://www.zonaprop.com.ar/propiedades/emprendimiento/ememvein-bulnes-966-almagro-almagro-capital-federal-57026242.html",
                ],
            },
            "building": {
                "name": "Bulnes 966",
                "amenities": ["Solarium", "Bike parking", "Local gastronomico PB"],
                "construction": {
                    "stage": "en_construccion",
                    "delivery_estimated_at": "2027-04-01",
                    "source_note": "Entrega publicada abril/marzo 2027 segun avisos de Zonaprop",
                },
                "financing": {
                    "headline": "Anticipo 40% + 20 cuotas",
                    "details": "Financiacion publicada en avisos de preventa.",
                },
            },
            "condominium": {
                "security": ["Acceso controlado"],
                "services": ["Agua caliente central"],
            },
            "units": [
                {
                    "unit_id": "bulnes_966_p6_d",
                    "unit_code": "6D",
                    "typology": "1_amb",
                    "rooms_label": "1 ambiente",
                    "rooms_count": 1,
                    "bedrooms": 0,
                    "bathrooms": 1,
                    "surface": {"covered_m2": 29, "total_m2": 32},
                    "pricing": {"currency": "USD", "list_price": 74900},
                    "availability": {"status": "available"},
                    "features": ["Balcon", "Contrafrente"],
                    "source_url": "https://www.zonaprop.com.ar/propiedades/emprendimiento/veunapin-venta-monoambiente-amplia-financiacion-57026250.html",
                },
                {
                    "unit_id": "bulnes_966_p6_b",
                    "unit_code": "6B",
                    "typology": "1_amb",
                    "rooms_label": "1 ambiente",
                    "rooms_count": 1,
                    "bedrooms": 0,
                    "bathrooms": 1,
                    "surface": {"covered_m2": 33, "total_m2": 37},
                    "pricing": {"currency": "USD", "list_price": 79000},
                    "availability": {"status": "available"},
                    "features": ["Balcon", "Frente"],
                    "source_url": "https://www.zonaprop.com.ar/propiedades/emprendimiento/veunapin-venta-monoambiente-amplia-financiacion-57026243.html",
                },
                {
                    "unit_id": "bulnes_966_p1_a",
                    "unit_code": "1A",
                    "typology": "2_amb",
                    "rooms_label": "2 ambientes",
                    "rooms_count": 2,
                    "bedrooms": 1,
                    "bathrooms": 1,
                    "surface": {"covered_m2": 45, "total_m2": 49},
                    "pricing": {"currency": "USD", "list_price": 101000},
                    "availability": {"status": "available"},
                    "features": ["Balcon", "Frente"],
                    "source_url": "https://www.zonaprop.com.ar/propiedades/clasificado/veclapin-departamento-2-ambientes-con-balcon-bulnes-966-almagro-56191460.html",
                },
            ],
        },
        {
            "workspace_id": WORKSPACE_ID,
            "schema_version": SCHEMA_VERSION,
            "project": {
                "project_id": "prj_gdr_3760_2026",
                "project_code": "GDR_3760_SAAVEDRA",
                "name": "Garcia del Rio 3760 — Saavedra",
                "status": "activo",
                "description": (
                    "Proyecto residencial de 3 ambientes configurables a 4, con balcones terraza y foco en "
                    "amplitud/luz natural en Saavedra."
                ),
                "location": {
                    "address": "Avenida Garcia del Rio 3760",
                    "barrio": "Saavedra",
                    "ciudad": "CABA",
                    "pais": "AR",
                },
                "tags": ["Saavedra", "3 a 4 ambientes", "Balcon terraza", "En construccion"],
                "source_urls": [
                    "https://www.zonaprop.com.ar/propiedades/emprendimiento/ememvein-garcia-del-rio-3760-56802375.html",
                ],
            },
            "building": {
                "name": "GDR3760",
                "amenities": ["Balcones generosos", "Balcones terraza", "Diseno flexible 3 a 4 ambientes"],
                "construction": {
                    "stage": "en_construccion",
                    "delivery_estimated_at": "2026-12-01",
                },
                "financing": None,
            },
            "condominium": {
                "security": [],
                "services": [],
            },
            "units": [
                {
                    "unit_id": "gdr_3760_p2_b",
                    "unit_code": "2B",
                    "typology": "3_amb_opcion_4",
                    "rooms_label": "3 ambientes (opcion 4)",
                    "rooms_count": 3,
                    "bedrooms": 2,
                    "bathrooms": 2,
                    "surface": {"covered_m2": 90, "total_m2": 113},
                    "pricing": {"currency": "USD", "list_price": 275700},
                    "availability": {"status": "available"},
                    "features": ["Balcón terraza", "2 dormitorios en suite", "Toilette"],
                    "source_url": "https://www.zonaprop.com.ar/propiedades/emprendimiento/veunapin-venta-3-amb-opcion-4-amb-balcon-terraza-saavedra-56802381.html",
                },
                {
                    "unit_id": "gdr_3760_p3_b",
                    "unit_code": "3B",
                    "typology": "3_amb_opcion_4",
                    "rooms_label": "3 ambientes (opcion 4)",
                    "rooms_count": 3,
                    "bedrooms": 2,
                    "bathrooms": 2,
                    "surface": {"covered_m2": 90, "total_m2": 113},
                    "pricing": {"currency": "USD", "list_price": 297600},
                    "availability": {"status": "available"},
                    "features": ["Balcón terraza", "2 dormitorios en suite", "Toilette"],
                    "source_url": "https://www.zonaprop.com.ar/propiedades/emprendimiento/veunapin-venta-3-ambientes-con-balcon-terraza-en-saavedra-56802376.html",
                },
                {
                    "unit_id": "gdr_3760_p4_a",
                    "unit_code": "4A",
                    "typology": "3_amb_opcion_4",
                    "rooms_label": "3 ambientes (opcion 4)",
                    "rooms_count": 3,
                    "bedrooms": 2,
                    "bathrooms": 2,
                    "surface": {"covered_m2": 79, "total_m2": 137},
                    "pricing": {"currency": "USD", "list_price": 326800},
                    "availability": {"status": "available"},
                    "features": ["Balcón terraza", "2 dormitorios en suite", "Toilette"],
                    "source_url": "https://www.zonaprop.com.ar/propiedades/emprendimiento/veunapin-venta-3-ambientes-con-balcon-terraza-en-saavedra-56802379.html",
                },
            ],
        },
        {
            "workspace_id": WORKSPACE_ID,
            "schema_version": SCHEMA_VERSION,
            "project": {
                "project_id": "prj_manzanares_3277_2026",
                "project_code": "MANZANARES_3277",
                "name": "Manzanares 3277 — Saavedra",
                "status": "activo",
                "description": (
                    "Desarrollo de 2 y 3 ambientes con foco en seguridad, domotica y eficiencia, "
                    "a pasos de Parque Saavedra."
                ),
                "location": {
                    "address": "Manzanares 3277",
                    "address_alt": "Manzanares 3200",
                    "barrio": "Saavedra",
                    "ciudad": "CABA",
                    "pais": "AR",
                },
                "tags": ["Saavedra", "2 y 3 ambientes", "Seguridad", "Domotica", "Entrega 2027"],
                "source_urls": [
                    "https://www.zonaprop.com.ar/propiedades/emprendimiento/ememvein-manzanares-3277-57226433.html",
                ],
            },
            "building": {
                "name": "Manzanares 3277",
                "amenities": [
                    "Acceso biometrico",
                    "Sistema de camaras",
                    "Portero visor inteligente con wifi",
                    "Domotica smartwifi",
                    "Paneles solares en espacios comunes",
                ],
                "construction": {
                    "stage": "en_construccion",
                    "delivery_estimated_at": "2027-03-01",
                    "price_from": {"currency": "USD", "amount": 90900},
                },
                "financing": {
                    "headline": "Opciones de financiacion segun avance de obra",
                },
            },
            "condominium": {
                "security": ["Acceso biometrico", "Camaras de seguridad"],
                "services": ["Autogeneracion solar", "Portero visor wifi"],
            },
            "units": [
                {
                    "unit_id": "manzanares_3277_p4_c",
                    "unit_code": "4C",
                    "typology": "2_amb",
                    "rooms_label": "2 ambientes",
                    "rooms_count": 2,
                    "bedrooms": 1,
                    "bathrooms": 1,
                    "surface": {"covered_m2": 34, "total_m2": 39},
                    "pricing": {"currency": "USD", "list_price": 98000},
                    "availability": {"status": "available"},
                    "features": ["Balcón"],
                    "source_url": "https://www.zonaprop.com.ar/propiedades/emprendimiento/veunapin-venta-2-ambientes-con-balcon-en-saavedra-57226441.html",
                },
                {
                    "unit_id": "manzanares_3277_p3_c",
                    "unit_code": "3C",
                    "typology": "2_amb",
                    "rooms_label": "2 ambientes",
                    "rooms_count": 2,
                    "bedrooms": 1,
                    "bathrooms": 1,
                    "surface": {"covered_m2": 34, "total_m2": 39},
                    "pricing": {"currency": "USD", "list_price": 93000},
                    "availability": {"status": "available"},
                    "features": ["Balcón"],
                    "source_url": "https://www.zonaprop.com.ar/propiedades/emprendimiento/veunapin-venta-2-ambientes-con-balcon-en-saavedra-57226439.html",
                },
                {
                    "unit_id": "manzanares_3277_p6_a",
                    "unit_code": "6A",
                    "typology": "3_amb",
                    "rooms_label": "3 ambientes",
                    "rooms_count": 3,
                    "bedrooms": 2,
                    "bathrooms": 1,
                    "surface": {"covered_m2": 51, "total_m2": 96},
                    "pricing": {"currency": "USD", "list_price": 226000},
                    "availability": {"status": "available"},
                    "features": ["Jardin"],
                    "source_url": "https://www.zonaprop.com.ar/propiedades/emprendimiento/veunapna-venta-3-ambientes-con-jardin-en-saavedra-57226436.html",
                },
                {
                    "unit_id": "manzanares_3277_p6_a_terraza",
                    "unit_code": "6A-TRZ",
                    "typology": "3_amb",
                    "rooms_label": "3 ambientes",
                    "rooms_count": 3,
                    "bedrooms": 2,
                    "bathrooms": 2,
                    "surface": {"covered_m2": 64, "total_m2": 92},
                    "pricing": {"currency": "USD", "list_price": 229500},
                    "availability": {"status": "available"},
                    "features": ["Balcón terraza", "Dormitorio en suite", "Toilette"],
                    "source_url": "https://www.zonaprop.com.ar/propiedades/emprendimiento/veunapin-venta-3-ambientes-con-balcon-terraza-en-saavedra-57226438.html",
                },
            ],
        },
    ]


def _project_id_by_code(conn: Any, project_code: str) -> str | None:
    row = conn.execute(
        """
        select id
        from projects
        where upper(code) = upper(%s)
        limit 1
        """,
        (project_code,),
    ).fetchone()
    return str(row[0]) if row else None


def _default_developer_id(conn: Any) -> str | None:
    row = conn.execute("select id from developers order by created_at asc limit 1").fetchone()
    return str(row[0]) if row else None


def _upsert_project(conn: Any, bundle: dict[str, Any], developer_id: str | None) -> str:
    project = bundle.get("project") if isinstance(bundle, dict) else {}
    code = str((project or {}).get("project_code") or "").strip()
    if not code:
        raise ValueError("project.project_code is required")

    name = str((project or {}).get("name") or code).strip()
    description = str((project or {}).get("description") or "").strip()
    status = str((project or {}).get("status") or "activo").strip() or "activo"
    location = (project or {}).get("location")
    tags = (project or {}).get("tags")
    location_json = json.dumps(location if isinstance(location, dict) else {}, ensure_ascii=False)
    tags_array = [str(item) for item in tags] if isinstance(tags, list) else []

    current_id = _project_id_by_code(conn, code)
    if current_id:
        conn.execute(
            """
            update projects
            set name = %s,
                description = %s,
                status = %s,
                location_jsonb = %s::jsonb,
                tags = %s,
                updated_at = now()
            where id = %s
            """,
            (name, description, status, location_json, tags_array, current_id),
        )
        return current_id

    row = conn.execute(
        """
        insert into projects (developer_id, code, name, description, location_jsonb, tags, status, updated_at)
        values (%s, %s, %s, %s, %s::jsonb, %s, %s, now())
        returning id
        """,
        (developer_id, code, name, description, location_json, tags_array, status),
    ).fetchone()
    if not row:
        raise RuntimeError(f"cannot insert project {code}")
    return str(row[0])


def _upsert_marketing_asset(conn: Any, project_id: str, bundle: dict[str, Any]) -> None:
    project = bundle.get("project") if isinstance(bundle, dict) else {}
    building = bundle.get("building") if isinstance(bundle, dict) else {}
    code = str((project or {}).get("project_code") or "").strip()
    short_copy = str((project or {}).get("description") or "").strip()
    chips = []
    if isinstance((project or {}).get("tags"), list):
        chips.extend([str(item) for item in (project or {}).get("tags")])
    if isinstance((building or {}).get("amenities"), list):
        for amenity in (building or {}).get("amenities"):
            text = str(amenity)
            if text not in chips:
                chips.append(text)

    prefill = f"Hola, me interesa {code}. ¿Podés compartir disponibilidad y condiciones actualizadas?"
    row = conn.execute(
        """
        select id
        from marketing_assets
        where project_id = %s and channel = 'meta_ads'::channel_type
        order by sort_order asc, created_at asc
        limit 1
        """,
        (project_id,),
    ).fetchone()
    if row:
        conn.execute(
            """
            update marketing_assets
            set title = %s,
                short_copy = %s,
                chips = %s,
                whatsapp_prefill = %s,
                is_active = true
            where id = %s
            """,
            (code, short_copy, chips, prefill, row[0]),
        )
        return

    conn.execute(
        """
        insert into marketing_assets (
            project_id, channel, title, short_copy, chips, whatsapp_prefill, is_active, sort_order
        )
        values (%s, 'meta_ads'::channel_type, %s, %s, %s, %s, true, 10)
        """,
        (project_id, code, short_copy, chips, prefill),
    )


def _upsert_bundle_row(conn: Any, bundle: dict[str, Any], source_urls: list[str]) -> None:
    project = bundle.get("project") if isinstance(bundle, dict) else {}
    code = str((project or {}).get("project_code") or "").strip()
    conn.execute(
        """
        insert into demo_project_bundles (
            workspace_id, project_code, schema_version, bundle_jsonb, source_urls, updated_at
        )
        values (%s, %s, %s, %s::jsonb, %s::jsonb, now())
        on conflict (workspace_id, project_code)
        do update set
            schema_version = excluded.schema_version,
            bundle_jsonb = excluded.bundle_jsonb,
            source_urls = excluded.source_urls,
            updated_at = now()
        """,
        (
            str(bundle.get("workspace_id") or WORKSPACE_ID),
            code,
            str(bundle.get("schema_version") or SCHEMA_VERSION),
            json.dumps(bundle, ensure_ascii=False),
            json.dumps(source_urls, ensure_ascii=False),
        ),
    )


def _upsert_facts(conn: Any, bundle: dict[str, Any], source_urls: list[str]) -> None:
    project = bundle.get("project") if isinstance(bundle, dict) else {}
    building = bundle.get("building") if isinstance(bundle, dict) else {}
    code = str((project or {}).get("project_code") or "").strip()
    unit_types = []
    for unit in bundle.get("units") or []:
        if not isinstance(unit, dict):
            continue
        typology = str(unit.get("typology") or "").strip()
        rooms_label = str(unit.get("rooms_label") or "").strip()
        if typology:
            unit_types.append(typology)
        elif rooms_label:
            unit_types.append(rooms_label)
    dedup_types = []
    for item in unit_types:
        if item and item not in dedup_types:
            dedup_types.append(item)

    conn.execute(
        """
        insert into demo_project_facts (
            project_code,
            workspace_id,
            location_jsonb,
            amenities_jsonb,
            construction_jsonb,
            financing_jsonb,
            tags_jsonb,
            unit_types_jsonb,
            description,
            source_urls,
            updated_at
        )
        values (
            %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s::jsonb, now()
        )
        on conflict (project_code)
        do update set
            workspace_id = excluded.workspace_id,
            location_jsonb = excluded.location_jsonb,
            amenities_jsonb = excluded.amenities_jsonb,
            construction_jsonb = excluded.construction_jsonb,
            financing_jsonb = excluded.financing_jsonb,
            tags_jsonb = excluded.tags_jsonb,
            unit_types_jsonb = excluded.unit_types_jsonb,
            description = excluded.description,
            source_urls = excluded.source_urls,
            updated_at = now()
        """,
        (
            code,
            str(bundle.get("workspace_id") or WORKSPACE_ID),
            json.dumps((project or {}).get("location") or {}, ensure_ascii=False),
            json.dumps((building or {}).get("amenities") or [], ensure_ascii=False),
            json.dumps((building or {}).get("construction") or {}, ensure_ascii=False),
            json.dumps((building or {}).get("financing"), ensure_ascii=False),
            json.dumps((project or {}).get("tags") or [], ensure_ascii=False),
            json.dumps(dedup_types, ensure_ascii=False),
            str((project or {}).get("description") or "").strip(),
            json.dumps(source_urls, ensure_ascii=False),
        ),
    )


def _replace_units(conn: Any, bundle: dict[str, Any]) -> int:
    project = bundle.get("project") if isinstance(bundle, dict) else {}
    code = str((project or {}).get("project_code") or "").strip()
    workspace_id = str(bundle.get("workspace_id") or WORKSPACE_ID)
    conn.execute(
        "delete from demo_units where workspace_id = %s and project_code = %s",
        (workspace_id, code),
    )

    inserted = 0
    for unit in bundle.get("units") or []:
        if not isinstance(unit, dict):
            continue
        surface = unit.get("surface") if isinstance(unit.get("surface"), dict) else {}
        pricing = unit.get("pricing") if isinstance(unit.get("pricing"), dict) else {}
        availability = (
            unit.get("availability") if isinstance(unit.get("availability"), dict) else {}
        )
        conn.execute(
            """
            insert into demo_units (
                workspace_id,
                project_code,
                unit_id,
                unit_code,
                typology,
                rooms_label,
                rooms_count,
                bedrooms,
                bathrooms,
                surface_total_m2,
                surface_covered_m2,
                currency,
                list_price,
                availability_status,
                features_jsonb,
                source_url,
                updated_at
            )
            values (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, now()
            )
            """,
            (
                workspace_id,
                code,
                str(unit.get("unit_id") or ""),
                str(unit.get("unit_code") or "") or None,
                str(unit.get("typology") or "") or None,
                str(unit.get("rooms_label") or "") or None,
                unit.get("rooms_count"),
                unit.get("bedrooms"),
                unit.get("bathrooms"),
                surface.get("total_m2"),
                surface.get("covered_m2"),
                str(pricing.get("currency") or "") or None,
                pricing.get("list_price"),
                str(availability.get("status") or "unknown"),
                json.dumps(unit.get("features") or [], ensure_ascii=False),
                str(unit.get("source_url") or "") or None,
            ),
        )
        inserted += 1
    return inserted


def run_seed(*, apply_ddl: bool = True) -> dict[str, Any]:
    bundles = _bundles()
    conninfo = _conninfo()

    result: dict[str, Any] = {"projects": 0, "units": 0}
    with psycopg.connect(conninfo, autocommit=False) as conn:
        if apply_ddl:
            conn.execute(_schema_sql())
        developer_id = _default_developer_id(conn)

        for bundle in bundles:
            project = bundle.get("project") if isinstance(bundle, dict) else {}
            source_urls = []
            if isinstance((project or {}).get("source_urls"), list):
                source_urls = [str(item) for item in (project or {}).get("source_urls")]
            for unit in bundle.get("units") or []:
                if isinstance(unit, dict) and unit.get("source_url"):
                    source_url = str(unit.get("source_url"))
                    if source_url not in source_urls:
                        source_urls.append(source_url)

            project_id = _upsert_project(conn, bundle, developer_id)
            _upsert_marketing_asset(conn, project_id, bundle)
            _upsert_bundle_row(conn, bundle, source_urls)
            _upsert_facts(conn, bundle, source_urls)
            result["units"] += _replace_units(conn, bundle)
            result["projects"] += 1

        conn.commit()

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo project knowledge into v360 DB.")
    parser.add_argument(
        "--skip-ddl",
        action="store_true",
        help="Do not execute idempotent DDL before seeding.",
    )
    args = parser.parse_args()

    outcome = run_seed(apply_ddl=not args.skip_ddl)
    print(json.dumps(outcome, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
