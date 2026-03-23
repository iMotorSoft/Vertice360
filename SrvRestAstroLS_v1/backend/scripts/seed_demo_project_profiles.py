from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg

try:
    from backend import globalVar
except ImportError:  # pragma: no cover - script fallback when run from backend/
    import globalVar  # type: ignore[no-redef]


KNOWN_AVAILABLE_STATUSES = {"available"}
KNOWN_RESERVED_STATUSES = {"reserved", "hold", "on_hold"}
KNOWN_UNAVAILABLE_STATUSES = {"unavailable", "sold", "paused", "withdrawn"}

PROJECT_OVERRIDES: dict[str, dict[str, Any]] = {
    "BULNES_966_ALMAGRO": {
        "children_suitable": None,
        "pets_allowed": None,
        "pets_restrictions_text": None,
        "recommended_profiles_jsonb": ["first_home", "investment"],
    },
    "GDR_3760_SAAVEDRA": {
        "children_suitable": True,
        "pets_allowed": None,
        "pets_restrictions_text": None,
        "recommended_profiles_jsonb": ["family"],
    },
    "MANZANARES_3277": {
        "children_suitable": True,
        "pets_allowed": True,
        "pets_restrictions_text": (
            "Confirmar reglamento de copropiedad, tamano de mascota y normas de convivencia."
        ),
        "recommended_profiles_jsonb": ["family", "pets", "first_home"],
    },
}

UNIT_OVERRIDES: dict[str, dict[str, Any]] = {
    "bulnes_966_p1_a": {
        "children_suitable": True,
        "recommended_profiles_jsonb": ["first_home"],
    },
    "bulnes_966_p6_b": {
        "children_suitable": False,
        "recommended_profiles_jsonb": ["first_home", "investment"],
    },
    "bulnes_966_p6_d": {
        "children_suitable": False,
        "recommended_profiles_jsonb": ["first_home", "investment"],
    },
    "gdr_3760_p2_b": {
        "children_suitable": True,
        "recommended_profiles_jsonb": ["family"],
    },
    "gdr_3760_p3_b": {
        "children_suitable": True,
        "recommended_profiles_jsonb": ["family"],
    },
    "gdr_3760_p4_a": {
        "children_suitable": True,
        "recommended_profiles_jsonb": ["family"],
    },
    "manzanares_3277_p3_c": {
        "children_suitable": True,
        "pets_allowed": None,
        "pets_restrictions_text": None,
        "recommended_profiles_jsonb": ["first_home"],
    },
    "manzanares_3277_p4_c": {
        "children_suitable": True,
        "pets_allowed": None,
        "pets_restrictions_text": None,
        "recommended_profiles_jsonb": ["first_home"],
    },
    "manzanares_3277_p6_a": {
        "children_suitable": True,
        "pets_allowed": True,
        "pets_restrictions_text": (
            "Confirmar reglamento de copropiedad y cerramientos del jardin para convivencia segura."
        ),
        "recommended_profiles_jsonb": ["family", "pets"],
    },
    "manzanares_3277_p6_a_terraza": {
        "children_suitable": True,
        "pets_allowed": True,
        "pets_restrictions_text": (
            "Confirmar reglamento de copropiedad y protecciones del balcon terraza."
        ),
        "recommended_profiles_jsonb": ["family", "pets"],
    },
}


def _conninfo() -> str:
    return globalVar.get_v360_db_url().replace("postgresql+psycopg://", "postgresql://")


def _schema_sql() -> str:
    path = (
        Path(__file__).resolve().parents[1] / "db" / "demo_project_profile_schema.sql"
    )
    return path.read_text(encoding="utf-8")


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    return []


def _status_counts(units: list[dict[str, Any]]) -> tuple[dict[str, int], int, int, int]:
    counter: Counter[str] = Counter()
    available = reserved = unavailable = 0
    for unit in units:
        raw_status = str(unit.get("availability_status") or "unknown").strip().lower()
        counter[raw_status] += 1
        if raw_status in KNOWN_AVAILABLE_STATUSES:
            available += 1
        elif raw_status in KNOWN_RESERVED_STATUSES:
            reserved += 1
        elif raw_status in KNOWN_UNAVAILABLE_STATUSES:
            unavailable += 1
        else:
            unavailable += 1
    return dict(counter), available, reserved, unavailable


def _has_feature(unit: dict[str, Any], *needles: str) -> bool:
    features = _as_list(unit.get("features_jsonb"))
    normalized = [feature.casefold() for feature in features]
    return any(needle.casefold() in feature for needle in needles for feature in normalized)


def _has_feature_exact(unit: dict[str, Any], *values: str) -> bool:
    features = {feature.casefold() for feature in _as_list(unit.get("features_jsonb"))}
    return any(value.casefold() in features for value in values)


def _project_warning_arrays(units: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    child_warnings: list[str] = []
    usage_warnings = [
        "Inventario demo parcial cargado en v360; confirmar disponibilidad final y stock adicional con comercial."
    ]

    if any(_has_feature(unit, "balcon", "balcón", "terraza") for unit in units):
        child_warnings.append(
            "Varias unidades tienen balcon o expansion exterior; confirmar barandas y protecciones si habra ninos pequenos."
        )
    if any(_has_feature(unit, "jardin", "jardín") for unit in units):
        child_warnings.append(
            "Las unidades con jardin requieren confirmar cerramientos perimetrales si habra ninos pequenos."
        )

    return child_warnings, usage_warnings


def _project_profile(
    project_code: str,
    workspace_id: str,
    units: list[dict[str, Any]],
    facts: dict[str, Any],
) -> dict[str, Any]:
    status_breakdown, available_units, reserved_units, unavailable_units = _status_counts(units)
    child_warnings, usage_warnings = _project_warning_arrays(units)
    overrides = PROJECT_OVERRIDES.get(project_code, {})
    inventory_as_of = max(
        (unit.get("updated_at") for unit in units if unit.get("updated_at") is not None),
        default=datetime.now(timezone.utc),
    )
    source_urls = _as_list(facts.get("source_urls"))

    return {
        "project_code": project_code,
        "workspace_id": workspace_id,
        "inventory_scope_type": "project",
        "inventory_scope_label": "Inventario demo actualmente cargado en v360; no implica stock completo del edificio.",
        "units_total": len(units),
        "available_units": available_units,
        "reserved_units": reserved_units,
        "unavailable_units": unavailable_units,
        "inventory_is_complete": False,
        "inventory_as_of": inventory_as_of,
        "children_suitable": overrides.get("children_suitable"),
        "pets_allowed": overrides.get("pets_allowed"),
        "pets_restrictions_text": overrides.get("pets_restrictions_text"),
        "pool_safety": "not_applicable",
        "raw_status_breakdown_jsonb": status_breakdown,
        "child_safety_warnings_jsonb": child_warnings,
        "usage_warnings_jsonb": usage_warnings,
        "recommended_profiles_jsonb": overrides.get("recommended_profiles_jsonb", []),
        "source_urls": source_urls,
    }


def _balcony_protection(unit: dict[str, Any]) -> str:
    if _has_feature(unit, "balcon", "balcón", "terraza"):
        return "unknown"
    return "not_applicable"


def _exposure(unit: dict[str, Any]) -> str | None:
    if _has_feature_exact(unit, "Contrafrente"):
        return "contrafrente"
    if _has_feature_exact(unit, "Frente"):
        return "frente"
    return None


def _view_text(unit: dict[str, Any]) -> str | None:
    if _has_feature(unit, "contrafrente"):
        return "Al contrafrente con balcon."
    if _has_feature(unit, "frente"):
        return "Al frente con balcon."
    if _has_feature(unit, "balcon terraza", "balcón terraza"):
        return "Salida a balcon terraza."
    if _has_feature(unit, "jardin", "jardín"):
        return "Salida a jardin propio."
    if _has_feature(unit, "balcon", "balcón"):
        return "Salida a balcon."
    return None


def _natural_light(project_code: str, unit: dict[str, Any]) -> str | None:
    if project_code == "GDR_3760_SAAVEDRA":
        return "high"
    if _has_feature(unit, "jardin", "jardín", "balcon terraza", "balcón terraza"):
        return "high"
    if _has_feature_exact(unit, "Frente"):
        return "high"
    if _has_feature_exact(unit, "Contrafrente"):
        return "medium"
    if _has_feature(unit, "balcon", "balcón"):
        return "medium"
    return None


def _thermal_notes(project_code: str, unit: dict[str, Any]) -> str | None:
    if project_code == "GDR_3760_SAAVEDRA":
        return "La propuesta comercial destaca amplitud y luz natural; confirmar orientacion final para estimar asoleamiento."
    if project_code == "MANZANARES_3277" and (
        _has_feature(unit, "jardin", "jardín", "balcon", "balcón", "terraza")
    ):
        return "El proyecto comunica foco en eficiencia; confirmar orientacion final y carpinterias para estimar confort termico."
    return None


def _child_warnings_for_unit(unit: dict[str, Any]) -> list[str]:
    if _has_feature(unit, "balcon terraza", "balcón terraza"):
        return [
            "Balcon terraza: confirmar altura de barandas y protecciones si viviran ninos pequenos."
        ]
    if _has_feature(unit, "balcon", "balcón"):
        return [
            "Confirmar altura de barandas y protecciones del balcon si viviran ninos pequenos."
        ]
    if _has_feature(unit, "jardin", "jardín"):
        return [
            "Confirmar cerramientos y limites del jardin si lo usaran ninos pequenos."
        ]
    return []


def _usage_warnings_for_unit(unit: dict[str, Any]) -> list[str]:
    if _has_feature(unit, "balcon", "balcón", "terraza", "jardin", "jardín"):
        return [
            "La orientacion, el sol directo y la exposicion al viento no estan confirmados en la fuente; validar con plano o visita."
        ]
    return []


def _commercial_features(project_code: str, unit: dict[str, Any]) -> dict[str, Any]:
    features: dict[str, Any] = {}
    if _has_feature(unit, "balcon terraza", "balcón terraza"):
        features["balcony"] = True
        features["balcony_type"] = "terrace"
    elif _has_feature(unit, "balcon", "balcón"):
        features["balcony"] = True
        features["balcony_type"] = "standard"
    if _has_feature(unit, "jardin", "jardín"):
        features["garden"] = True
    if _has_feature(unit, "suite"):
        suite_count = 2 if project_code == "GDR_3760_SAAVEDRA" else 1
        features["suite_bedrooms"] = suite_count
    if _has_feature(unit, "toilette"):
        features["toilette"] = True
    if unit.get("typology") == "3_amb_opcion_4":
        features["flex_layout"] = "3_a_4_amb"
    exposure = _exposure(unit)
    if exposure:
        features["exposure_hint"] = exposure
    return features


def _base_unit_profile(
    project_profile: dict[str, Any],
    unit: dict[str, Any],
) -> dict[str, Any]:
    project_code = str(unit["project_code"])
    unit_id = str(unit["unit_id"])
    overrides = UNIT_OVERRIDES.get(unit_id, {})

    has_garden = True if _has_feature(unit, "jardin", "jardín") else None
    has_patio = True if _has_feature(unit, "patio") else None

    return {
        "workspace_id": str(unit["workspace_id"]),
        "project_code": project_code,
        "unit_id": unit_id,
        "orientation": None,
        "exposure": _exposure(unit),
        "view_text": _view_text(unit),
        "sun_morning": None,
        "sun_afternoon": None,
        "natural_light": _natural_light(project_code, unit),
        "cross_ventilation": None,
        "thermal_comfort_notes": _thermal_notes(project_code, unit),
        "balcony_protection": _balcony_protection(unit),
        "children_suitable": overrides.get(
            "children_suitable",
            True if int(unit.get("rooms_count") or 0) >= 2 else False,
        ),
        "pets_allowed": overrides.get("pets_allowed"),
        "pets_restrictions_text": overrides.get("pets_restrictions_text"),
        "has_garage": None,
        "has_storage": None,
        "has_patio": has_patio,
        "has_garden": has_garden,
        "child_safety_warnings_jsonb": _child_warnings_for_unit(unit),
        "usage_warnings_jsonb": _usage_warnings_for_unit(unit),
        "commercial_features_jsonb": _commercial_features(project_code, unit),
        "recommended_profiles_jsonb": overrides.get("recommended_profiles_jsonb", []),
        "source_urls": [str(unit["source_url"])] if unit.get("source_url") else project_profile["source_urls"],
    }


def _fetch_project_facts(conn: psycopg.Connection[Any]) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        select project_code, workspace_id, source_urls, updated_at
        from demo_project_facts
        order by project_code
        """
    ).fetchall()
    return {
        str(row[0]): {
            "project_code": str(row[0]),
            "workspace_id": str(row[1]),
            "source_urls": row[2],
            "updated_at": row[3],
        }
        for row in rows
    }


def _fetch_demo_units(conn: psycopg.Connection[Any]) -> dict[str, list[dict[str, Any]]]:
    rows = conn.execute(
        """
        select workspace_id, project_code, unit_id, unit_code, typology, rooms_label, rooms_count,
               bedrooms, bathrooms, surface_total_m2, surface_covered_m2, currency, list_price,
               availability_status, features_jsonb, source_url, updated_at
        from demo_units
        order by project_code, unit_id
        """
    ).fetchall()

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        unit = {
            "workspace_id": row[0],
            "project_code": row[1],
            "unit_id": row[2],
            "unit_code": row[3],
            "typology": row[4],
            "rooms_label": row[5],
            "rooms_count": row[6],
            "bedrooms": row[7],
            "bathrooms": row[8],
            "surface_total_m2": row[9],
            "surface_covered_m2": row[10],
            "currency": row[11],
            "list_price": row[12],
            "availability_status": row[13],
            "features_jsonb": row[14],
            "source_url": row[15],
            "updated_at": row[16],
        }
        grouped[str(row[1])].append(unit)
    return dict(grouped)


def _upsert_project_profile(conn: psycopg.Connection[Any], profile: dict[str, Any]) -> None:
    conn.execute(
        """
        insert into demo_project_profile (
            project_code,
            workspace_id,
            inventory_scope_type,
            inventory_scope_label,
            units_total,
            available_units,
            reserved_units,
            unavailable_units,
            inventory_is_complete,
            inventory_as_of,
            children_suitable,
            pets_allowed,
            pets_restrictions_text,
            pool_safety,
            raw_status_breakdown_jsonb,
            child_safety_warnings_jsonb,
            usage_warnings_jsonb,
            recommended_profiles_jsonb,
            source_urls,
            updated_at
        )
        values (
            %(project_code)s,
            %(workspace_id)s,
            %(inventory_scope_type)s,
            %(inventory_scope_label)s,
            %(units_total)s,
            %(available_units)s,
            %(reserved_units)s,
            %(unavailable_units)s,
            %(inventory_is_complete)s,
            %(inventory_as_of)s,
            %(children_suitable)s,
            %(pets_allowed)s,
            %(pets_restrictions_text)s,
            %(pool_safety)s,
            %(raw_status_breakdown_jsonb)s::jsonb,
            %(child_safety_warnings_jsonb)s::jsonb,
            %(usage_warnings_jsonb)s::jsonb,
            %(recommended_profiles_jsonb)s::jsonb,
            %(source_urls)s::jsonb,
            now()
        )
        on conflict (project_code)
        do update set
            workspace_id = excluded.workspace_id,
            inventory_scope_type = excluded.inventory_scope_type,
            inventory_scope_label = excluded.inventory_scope_label,
            units_total = excluded.units_total,
            available_units = excluded.available_units,
            reserved_units = excluded.reserved_units,
            unavailable_units = excluded.unavailable_units,
            inventory_is_complete = excluded.inventory_is_complete,
            inventory_as_of = excluded.inventory_as_of,
            children_suitable = excluded.children_suitable,
            pets_allowed = excluded.pets_allowed,
            pets_restrictions_text = excluded.pets_restrictions_text,
            pool_safety = excluded.pool_safety,
            raw_status_breakdown_jsonb = excluded.raw_status_breakdown_jsonb,
            child_safety_warnings_jsonb = excluded.child_safety_warnings_jsonb,
            usage_warnings_jsonb = excluded.usage_warnings_jsonb,
            recommended_profiles_jsonb = excluded.recommended_profiles_jsonb,
            source_urls = excluded.source_urls,
            updated_at = now()
        """,
        {
            **profile,
            "raw_status_breakdown_jsonb": json.dumps(
                profile["raw_status_breakdown_jsonb"], ensure_ascii=False
            ),
            "child_safety_warnings_jsonb": json.dumps(
                profile["child_safety_warnings_jsonb"], ensure_ascii=False
            ),
            "usage_warnings_jsonb": json.dumps(
                profile["usage_warnings_jsonb"], ensure_ascii=False
            ),
            "recommended_profiles_jsonb": json.dumps(
                profile["recommended_profiles_jsonb"], ensure_ascii=False
            ),
            "source_urls": json.dumps(profile["source_urls"], ensure_ascii=False),
        },
    )


def _upsert_unit_profile(conn: psycopg.Connection[Any], profile: dict[str, Any]) -> None:
    conn.execute(
        """
        insert into demo_unit_profile (
            workspace_id,
            project_code,
            unit_id,
            orientation,
            exposure,
            view_text,
            sun_morning,
            sun_afternoon,
            natural_light,
            cross_ventilation,
            thermal_comfort_notes,
            balcony_protection,
            children_suitable,
            pets_allowed,
            pets_restrictions_text,
            has_garage,
            has_storage,
            has_patio,
            has_garden,
            child_safety_warnings_jsonb,
            usage_warnings_jsonb,
            commercial_features_jsonb,
            recommended_profiles_jsonb,
            source_urls,
            updated_at
        )
        values (
            %(workspace_id)s,
            %(project_code)s,
            %(unit_id)s,
            %(orientation)s,
            %(exposure)s,
            %(view_text)s,
            %(sun_morning)s,
            %(sun_afternoon)s,
            %(natural_light)s,
            %(cross_ventilation)s,
            %(thermal_comfort_notes)s,
            %(balcony_protection)s,
            %(children_suitable)s,
            %(pets_allowed)s,
            %(pets_restrictions_text)s,
            %(has_garage)s,
            %(has_storage)s,
            %(has_patio)s,
            %(has_garden)s,
            %(child_safety_warnings_jsonb)s::jsonb,
            %(usage_warnings_jsonb)s::jsonb,
            %(commercial_features_jsonb)s::jsonb,
            %(recommended_profiles_jsonb)s::jsonb,
            %(source_urls)s::jsonb,
            now()
        )
        on conflict (workspace_id, project_code, unit_id)
        do update set
            orientation = excluded.orientation,
            exposure = excluded.exposure,
            view_text = excluded.view_text,
            sun_morning = excluded.sun_morning,
            sun_afternoon = excluded.sun_afternoon,
            natural_light = excluded.natural_light,
            cross_ventilation = excluded.cross_ventilation,
            thermal_comfort_notes = excluded.thermal_comfort_notes,
            balcony_protection = excluded.balcony_protection,
            children_suitable = excluded.children_suitable,
            pets_allowed = excluded.pets_allowed,
            pets_restrictions_text = excluded.pets_restrictions_text,
            has_garage = excluded.has_garage,
            has_storage = excluded.has_storage,
            has_patio = excluded.has_patio,
            has_garden = excluded.has_garden,
            child_safety_warnings_jsonb = excluded.child_safety_warnings_jsonb,
            usage_warnings_jsonb = excluded.usage_warnings_jsonb,
            commercial_features_jsonb = excluded.commercial_features_jsonb,
            recommended_profiles_jsonb = excluded.recommended_profiles_jsonb,
            source_urls = excluded.source_urls,
            updated_at = now()
        """,
        {
            **profile,
            "child_safety_warnings_jsonb": json.dumps(
                profile["child_safety_warnings_jsonb"], ensure_ascii=False
            ),
            "usage_warnings_jsonb": json.dumps(
                profile["usage_warnings_jsonb"], ensure_ascii=False
            ),
            "commercial_features_jsonb": json.dumps(
                profile["commercial_features_jsonb"], ensure_ascii=False
            ),
            "recommended_profiles_jsonb": json.dumps(
                profile["recommended_profiles_jsonb"], ensure_ascii=False
            ),
            "source_urls": json.dumps(profile["source_urls"], ensure_ascii=False),
        },
    )


def run_seed(*, apply_ddl: bool = False, dry_run: bool = False) -> dict[str, Any]:
    outcome: dict[str, Any] = {"projects": [], "units": []}
    with psycopg.connect(_conninfo(), autocommit=False) as conn:
        if apply_ddl:
            conn.execute(_schema_sql())

        project_facts = _fetch_project_facts(conn)
        units_by_project = _fetch_demo_units(conn)

        for project_code in sorted(units_by_project):
            units = units_by_project[project_code]
            facts = project_facts.get(project_code)
            if not facts:
                raise RuntimeError(f"demo_project_facts missing for {project_code}")

            project_profile = _project_profile(
                project_code=project_code,
                workspace_id=str(facts["workspace_id"]),
                units=units,
                facts=facts,
            )
            outcome["projects"].append(project_profile)
            print(
                "[project]"
                f" {project_code}"
                f" total={project_profile['units_total']}"
                f" available={project_profile['available_units']}"
                f" reserved={project_profile['reserved_units']}"
                f" unavailable={project_profile['unavailable_units']}"
                f" complete={project_profile['inventory_is_complete']}"
                f" children={project_profile['children_suitable']}"
                f" pets={project_profile['pets_allowed']}"
            )
            if not dry_run:
                _upsert_project_profile(conn, project_profile)

            for unit in units:
                unit_profile = _base_unit_profile(project_profile, unit)
                outcome["units"].append(unit_profile)
                print(
                    "[unit]"
                    f" {project_code}/{unit_profile['unit_id']}"
                    f" exposure={unit_profile['exposure']}"
                    f" light={unit_profile['natural_light']}"
                    f" children={unit_profile['children_suitable']}"
                    f" pets={unit_profile['pets_allowed']}"
                    f" garden={unit_profile['has_garden']}"
                    f" balcony={unit_profile['balcony_protection']}"
                )
                if not dry_run:
                    _upsert_unit_profile(conn, unit_profile)

        if dry_run:
            conn.rollback()
        else:
            conn.commit()

    return {
        "project_count": len(outcome["projects"]),
        "unit_count": len(outcome["units"]),
        "projects": outcome["projects"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed complementary demo project/unit profiles into v360 DB."
    )
    parser.add_argument(
        "--apply-ddl",
        action="store_true",
        help="Execute the idempotent profile schema before seeding.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute and log the seed without committing changes.",
    )
    args = parser.parse_args()

    result = run_seed(apply_ddl=args.apply_ddl, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
