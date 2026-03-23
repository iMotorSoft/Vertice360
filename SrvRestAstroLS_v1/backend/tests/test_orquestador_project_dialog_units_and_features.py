from __future__ import annotations

from typing import Any

from backend.modules.vertice360_orquestador_demo import services


def _detail_for_project(project_code: str, project_name: str) -> dict[str, Any]:
    return {
        "project_code": project_code,
        "project_name": project_name,
        "summary_jsonb": {
            "selected_project": {
                "code": project_code,
                "name": project_name,
            }
        },
    }


def _patch_dialog_repo(
    monkeypatch,
    *,
    project_code: str = "MANZANARES_3277",
    project_name: str = "Manzanares 3277 — Saavedra",
    overview: dict[str, Any] | None = None,
    marketing_assets: list[dict[str, Any]] | None = None,
    unit_types: list[dict[str, Any]] | None = None,
    total_units: int | None = None,
    available_units: int | None = None,
    breakdown: dict[str, int] | None = None,
    full_inventory_known: bool = False,
    available_by_rooms: dict[int, int] | None = None,
    project_profile: dict[str, Any] | None = None,
    merged_units: list[dict[str, Any]] | None = None,
) -> None:
    base_overview = overview or {
        "code": project_code,
        "name": project_name,
        "description": "Desarrollo de 2 y 3 ambientes con foco en seguridad, domotica y eficiencia, a pasos de Parque Saavedra.",
        "location_jsonb": {"address": "Manzanares 3277", "neighborhood": "Saavedra", "city": "CABA"},
        "tags": ["Saavedra", "2 y 3 ambientes", "Seguridad", "Domotica"],
        "_source_table": "demo_project_facts",
    }
    base_assets = marketing_assets if marketing_assets is not None else [
        {
            "title": project_name,
            "short_copy": "Copy comercial de apoyo.",
            "chips": ["Saavedra", "2 y 3 ambientes", "Seguridad", "Domotica"],
            "_source_table": "marketing_assets",
        }
    ]
    base_unit_types = unit_types if unit_types is not None else [
        {"rooms": "2", "label": "2 ambientes", "_source_table": "demo_units"},
        {"rooms": "3", "label": "3 ambientes", "_source_table": "demo_units"},
    ]
    base_merged_units = merged_units if merged_units is not None else [
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": project_code,
            "project_name": project_name,
            "unit_id": "manzanares_3277_p3_c",
            "unit_code": "3C",
            "rooms_label": "2 ambientes",
            "rooms_count": 2,
            "surface_total_m2": 48.0,
            "currency": "USD",
            "list_price": 130000,
            "availability_status": "available",
            "features_jsonb": ["Balcón"],
            "children_suitable": True,
            "pets_allowed": None,
            "balcony_protection": "unknown",
            "natural_light": "medium",
            "recommended_profiles_jsonb": ["first_home"],
            "_source_table": "demo_units",
            "_profile_source_table": "demo_unit_profile",
        },
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": project_code,
            "project_name": project_name,
            "unit_id": "manzanares_3277_p6_a",
            "unit_code": "6A",
            "rooms_label": "3 ambientes",
            "rooms_count": 3,
            "surface_total_m2": 84.0,
            "currency": "USD",
            "list_price": 210000,
            "availability_status": "available",
            "features_jsonb": [],
            "children_suitable": True,
            "pets_allowed": True,
            "has_garden": True,
            "balcony_protection": "not_applicable",
            "natural_light": "high",
            "recommended_profiles_jsonb": ["family", "pets"],
            "_source_table": "demo_units",
            "_profile_source_table": "demo_unit_profile",
        },
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": project_code,
            "project_name": project_name,
            "unit_id": "manzanares_3277_p6_a_terraza",
            "unit_code": "6A-TRZ",
            "rooms_label": "3 ambientes",
            "rooms_count": 3,
            "surface_total_m2": 86.5,
            "currency": "USD",
            "list_price": 220000,
            "availability_status": "available",
            "features_jsonb": ["Balcón terraza"],
            "children_suitable": True,
            "pets_allowed": True,
            "balcony_protection": "unknown",
            "natural_light": "high",
            "recommended_profiles_jsonb": ["family", "pets"],
            "_source_table": "demo_units",
            "_profile_source_table": "demo_unit_profile",
        },
    ]
    base_breakdown = breakdown if breakdown is not None else (
        {"available": int(available_units or 0)} if available_units is not None else {}
    )
    base_project_profile = project_profile if project_profile is not None else {
        "project_code": project_code,
        "workspace_id": "ws_demo_vertice360",
        "units_total": total_units if total_units is not None else len(base_merged_units),
        "available_units": available_units if available_units is not None else len(base_merged_units),
        "reserved_units": int((base_breakdown or {}).get("reserved") or 0),
        "unavailable_units": int((base_breakdown or {}).get("unavailable") or 0),
        "inventory_is_complete": full_inventory_known,
        "raw_status_breakdown_jsonb": dict(base_breakdown),
        "children_suitable": True,
        "pets_allowed": True,
        "pets_restrictions_text": "Confirmar reglamento.",
        "child_safety_warnings_jsonb": ["Confirmar barandas y protecciones del balcón."],
        "usage_warnings_jsonb": ["Inventario demo parcial."],
        "recommended_profiles_jsonb": ["family", "pets", "first_home"],
        "_source_table": "demo_project_profile",
    }

    def fake_get_units_with_filters(  # noqa: PLR0913
        conn,
        *,
        project_code=None,
        rooms=None,
        currency=None,
        unit_id=None,
        unit_code=None,
        feature_key=None,
        children_suitable=None,
        pets_allowed=None,
        has_garden=None,
        has_patio=None,
        has_garage=None,
        has_storage=None,
        natural_light=None,
        balcony_protection=None,
        recommended_profile=None,
        min_surface_total_m2=None,
        max_surface_total_m2=None,
        availability=None,
    ):  # noqa: ANN001
        rows = [dict(row) for row in base_merged_units]
        filtered = []
        for row in rows:
            if project_code and str(row.get("project_code") or "").strip().upper() != str(project_code).strip().upper():
                continue
            if rooms is not None and int(row.get("rooms_count") or 0) != int(rooms):
                continue
            if unit_id and str(row.get("unit_id") or "").strip() != str(unit_id).strip():
                continue
            if unit_code and str(row.get("unit_code") or "").strip().upper() != str(unit_code).strip().upper():
                continue
            if isinstance(children_suitable, bool) and row.get("children_suitable") is not children_suitable:
                continue
            if isinstance(pets_allowed, bool) and row.get("pets_allowed") is not pets_allowed:
                continue
            if isinstance(has_garden, bool) and row.get("has_garden") is not has_garden:
                continue
            if isinstance(has_patio, bool) and row.get("has_patio") is not has_patio:
                continue
            if isinstance(has_garage, bool) and row.get("has_garage") is not has_garage:
                continue
            if isinstance(has_storage, bool) and row.get("has_storage") is not has_storage:
                continue
            if natural_light and str(row.get("natural_light") or "").strip().lower() != str(natural_light).strip().lower():
                continue
            if balcony_protection and str(row.get("balcony_protection") or "").strip().lower() != str(balcony_protection).strip().lower():
                continue
            if recommended_profile:
                if str(recommended_profile).strip().lower() not in [str(v).lower() for v in row.get("recommended_profiles_jsonb") or []]:
                    continue
            surface_total = row.get("surface_total_m2")
            if min_surface_total_m2 is not None and float(surface_total or 0) < float(min_surface_total_m2):
                continue
            if max_surface_total_m2 is not None and float(surface_total or 0) > float(max_surface_total_m2):
                continue
            current_availability = str(row.get("availability_status") or "").strip().lower()
            if availability and current_availability and current_availability != str(availability).strip().lower():
                continue
            if feature_key == "jardin" and row.get("has_garden") is not True:
                continue
            if feature_key == "patio" and row.get("has_patio") is not True:
                continue
            if feature_key == "cochera" and row.get("has_garage") is not True:
                continue
            if feature_key == "baulera" and row.get("has_storage") is not True:
                continue
            if feature_key == "mascotas" and row.get("pets_allowed") is not True:
                continue
            if feature_key == "balcon" and str(row.get("balcony_protection") or "").strip().lower() == "not_applicable":
                continue
            filtered.append(row)
        return filtered

    def fake_children_summary(conn, code):  # noqa: ANN001
        return {
            "project_code": code,
            "project_children_suitable": base_project_profile.get("children_suitable"),
            "warnings": list(base_project_profile.get("child_safety_warnings_jsonb") or []),
            "known_units_count": len([row for row in base_merged_units if isinstance(row.get("children_suitable"), bool)]),
            "suitable_units_count": len([row for row in base_merged_units if row.get("children_suitable") is True]),
            "suitable_units": [row for row in base_merged_units if row.get("children_suitable") is True],
            "family_units": [row for row in base_merged_units if "family" in [str(v).lower() for v in row.get("recommended_profiles_jsonb") or []]],
            "_source_tables": ["demo_project_profile", "demo_unit_profile"],
        }

    def fake_pets_summary(conn, code):  # noqa: ANN001
        return {
            "project_code": code,
            "project_pets_allowed": base_project_profile.get("pets_allowed"),
            "project_pets_restrictions_text": base_project_profile.get("pets_restrictions_text"),
            "allowed_units": [row for row in base_merged_units if row.get("pets_allowed") is True],
            "recommended_units": [row for row in base_merged_units if "pets" in [str(v).lower() for v in row.get("recommended_profiles_jsonb") or []]],
            "_source_tables": ["demo_project_profile", "demo_unit_profile"],
        }

    def fake_light_summary(conn, project_code=None, unit_id=None):  # noqa: ANN001
        rows = [row for row in base_merged_units if not project_code or row.get("project_code") == project_code]
        return {
            "project_code": project_code,
            "high_light_units": [row for row in rows if row.get("natural_light") == "high"],
            "medium_light_units": [row for row in rows if row.get("natural_light") == "medium"],
            "orientation_known_units": [row for row in rows if row.get("orientation")],
            "exposure_known_units": [row for row in rows if row.get("exposure")],
            "sun_morning_units": [row for row in rows if row.get("sun_morning") is True],
            "sun_afternoon_units": [row for row in rows if row.get("sun_afternoon") is True],
            "cross_ventilation_units": [row for row in rows if row.get("cross_ventilation") is True],
            "_source_tables": ["demo_unit_profile", "demo_units"],
        }

    monkeypatch.setattr(services.repo, "update_ticket_activity", lambda *args, **kwargs: None)
    monkeypatch.setattr(services.repo, "get_project_by_code", lambda conn, code: {"id": "prj-1", "code": code, "name": project_name})
    monkeypatch.setattr(
        services.repo,
        "list_projects",
        lambda conn: [
            {"id": "prj-b", "code": "BULNES_966_ALMAGRO", "name": "Bulnes 966 — Almagro"},
            {"id": "prj-g", "code": "GDR_3760_SAAVEDRA", "name": "GDR 3760 — Saavedra"},
            {"id": "prj-m", "code": "MANZANARES_3277", "name": "Manzanares 3277 — Saavedra"},
        ],
    )
    monkeypatch.setattr(services.repo, "get_project_overview", lambda conn, code: base_overview)
    monkeypatch.setattr(services.repo, "get_project_marketing_assets", lambda conn, code: base_assets)
    monkeypatch.setattr(services.repo, "get_unit_types", lambda conn, code: base_unit_types)
    monkeypatch.setattr(services.repo, "get_total_units_for_project", lambda conn, code: total_units)
    monkeypatch.setattr(services.repo, "get_available_units_count", lambda conn, code: available_units)
    monkeypatch.setattr(services.repo, "get_unit_status_breakdown", lambda conn, code: dict(breakdown or {}))
    monkeypatch.setattr(services.repo, "is_full_inventory_known", lambda conn, code: full_inventory_known)
    monkeypatch.setattr(services.repo, "get_project_profile", lambda conn, code: dict(base_project_profile))
    monkeypatch.setattr(
        services.repo,
        "get_project_inventory_summary",
        lambda conn, code: {
            "project_code": code,
            "units_total": base_project_profile.get("units_total"),
            "available_units": base_project_profile.get("available_units"),
            "reserved_units": base_project_profile.get("reserved_units"),
            "unavailable_units": base_project_profile.get("unavailable_units"),
            "inventory_is_complete": base_project_profile.get("inventory_is_complete"),
            "raw_status_breakdown_jsonb": dict(base_project_profile.get("raw_status_breakdown_jsonb") or {}),
            "_source_table": "demo_project_profile",
        },
    )
    monkeypatch.setattr(services.repo, "get_project_recommended_profiles", lambda conn, code: list(base_project_profile.get("recommended_profiles_jsonb") or []))
    monkeypatch.setattr(services.repo, "get_unit_profiles_for_project", lambda conn, code: [dict(row) for row in base_merged_units if row.get("project_code") == code])
    monkeypatch.setattr(
        services.repo,
        "get_unit_profile_by_unit_id",
        lambda conn, code, unit_id: next((dict(row) for row in base_merged_units if row.get("project_code") == code and row.get("unit_id") == unit_id), None),
    )
    monkeypatch.setattr(
        services.repo,
        "find_demo_unit_by_code",
        lambda conn, unit_code: next((dict(row) for row in base_merged_units if str(row.get("unit_code") or "").strip().upper() == str(unit_code).strip().upper()), None),
    )
    monkeypatch.setattr(
        services.repo,
        "list_demo_units",
        lambda conn, code, rooms=None, currency=None: [
            dict(row)
            for row in base_merged_units
            if str(row.get("project_code") or "").strip().upper() == str(code).strip().upper()
            and (rooms is None or int(row.get("rooms_count") or 0) == int(rooms))
            and (currency is None or str(row.get("currency") or "").strip().upper() == str(currency).strip().upper())
        ],
    )
    monkeypatch.setattr(
        services.repo,
        "list_all_demo_units",
        lambda conn, rooms=None, currency=None: [
            dict(row)
            for row in base_merged_units
            if (rooms is None or int(row.get("rooms_count") or 0) == int(rooms))
            and (currency is None or str(row.get("currency") or "").strip().upper() == str(currency).strip().upper())
        ],
    )
    monkeypatch.setattr(services.repo, "get_units_with_filters", fake_get_units_with_filters)
    monkeypatch.setattr(
        services.repo,
        "get_units_global_filtered",
        lambda conn, **kwargs: fake_get_units_with_filters(
            conn,
            project_code=None,
            rooms=kwargs.get("rooms_count"),
            feature_key=kwargs.get("feature_key"),
            min_surface_total_m2=kwargs.get("min_surface_total_m2"),
            max_surface_total_m2=kwargs.get("max_surface_total_m2"),
            availability=kwargs.get("availability"),
        ),
    )
    monkeypatch.setattr(services.repo, "get_children_suitability_summary", fake_children_summary)
    monkeypatch.setattr(services.repo, "get_pets_suitability_summary", fake_pets_summary)
    monkeypatch.setattr(services.repo, "get_light_orientation_summary", fake_light_summary)
    monkeypatch.setattr(
        services.repo,
        "get_prices_by_rooms",
        lambda conn, code, rooms=None, currency=None: [
            {"rooms": "2", "price": 130000, "currency": "USD", "_source_table": "demo_units"},
            {"rooms": "3", "price": 190000, "currency": "USD", "_source_table": "demo_units"},
        ],
    )
    monkeypatch.setattr(
        services.repo,
        "get_delivery_info",
        lambda conn, code: {"source_table": "projects", "items": [{"delivery_date": "2027-06-30", "status": "en obra"}]},
    )
    monkeypatch.setattr(
        services.repo,
        "get_financing_terms",
        lambda conn, code: {"source_table": "payment_plans", "items": [{"financing_data": "Anticipo 40% + 24 cuotas en USD"}]},
    )
    monkeypatch.setattr(services, "_extract_available_by_rooms", lambda conn, code: dict(available_by_rooms or {}))


def _resolve(
    question: str,
    *,
    monkeypatch,
    intent: str,
    overview: dict[str, Any] | None = None,
    marketing_assets: list[dict[str, Any]] | None = None,
    unit_types: list[dict[str, Any]] | None = None,
    total_units: int | None = None,
    available_units: int | None = None,
    breakdown: dict[str, int] | None = None,
    full_inventory_known: bool = False,
    available_by_rooms: dict[int, int] | None = None,
    project_profile: dict[str, Any] | None = None,
    merged_units: list[dict[str, Any]] | None = None,
    semantic_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    project_code = "MANZANARES_3277"
    project_name = "Manzanares 3277 — Saavedra"
    _patch_dialog_repo(
        monkeypatch,
        project_code=project_code,
        project_name=project_name,
        overview=overview,
        marketing_assets=marketing_assets,
        unit_types=unit_types,
        total_units=total_units,
        available_units=available_units,
        breakdown=breakdown,
        full_inventory_known=full_inventory_known,
        available_by_rooms=available_by_rooms,
        project_profile=project_profile,
        merged_units=merged_units,
    )
    return services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-1",
        detail=_detail_for_project(project_code, project_name),
        question=question,
        recent_messages=[],
        semantic_resolution={
            "intent": intent,
            "followup": False,
            "reason": "test_case",
            "chosen_project": None,
            "excluded_project_codes": [],
            **(semantic_overrides or {}),
        },
    )



def _patch_global_project_inventory_summaries(monkeypatch, summary_by_project: dict[str, dict[str, Any]]) -> None:
    project_rows = [
        {"id": "prj-b", "code": "BULNES_966_ALMAGRO", "name": "Bulnes 966 — Almagro"},
        {"id": "prj-g", "code": "GDR_3760_SAAVEDRA", "name": "GDR 3760 — Saavedra"},
        {"id": "prj-m", "code": "MANZANARES_3277", "name": "Manzanares 3277 — Saavedra"},
    ]

    monkeypatch.setattr(services.repo, "list_projects", lambda conn: list(project_rows))

    def fake_get_project_inventory_summary(conn, code):  # noqa: ANN001
        clean_code = str(code or "").strip().upper()
        payload = dict(summary_by_project.get(clean_code) or {})
        payload.setdefault("project_code", clean_code)
        payload.setdefault("_source_table", "demo_project_profile")
        return payload

    monkeypatch.setattr(services.repo, "get_project_inventory_summary", fake_get_project_inventory_summary)


def test_total_units_query_uses_units_total_not_available_count(monkeypatch) -> None:
    reply = _resolve(
        "cuantas unidades son",
        monkeypatch=monkeypatch,
        intent="TOTAL_UNITS",
        total_units=46,
        available_units=3,
        breakdown={"available": 3, "reserved": 1, "unavailable": 42},
        full_inventory_known=True,
    )

    assert "46 unidades en total" in reply["answer"]
    assert "3 disponibles" in reply["answer"]
    assert "inventario demo" not in reply["answer"].lower()


def test_total_units_with_partial_inventory_returns_honest_answer(monkeypatch) -> None:
    reply = _resolve(
        "entre ocupadas y disponibles cuantas unidades son",
        monkeypatch=monkeypatch,
        intent="TOTAL_UNITS",
        total_units=None,
        available_units=3,
    )

    assert "En el inventario demo que tengo cargado hoy" in reply["answer"]
    assert "todas disponibles" in reply["answer"]
    assert "No tengo cargado el total completo del proyecto" in reply["answer"]


def test_available_units_query_returns_available_count_only(monkeypatch) -> None:
    reply = _resolve(
        "cuantas hay disponibles",
        monkeypatch=monkeypatch,
        intent="AVAILABLE_UNITS",
        total_units=46,
        available_units=3,
        available_by_rooms={2: 2, 3: 1},
    )

    assert "3 disponibles" in reply["answer"]
    assert "46 unidades en total" not in reply["answer"]


def test_status_breakdown_query_returns_counts_by_status(monkeypatch) -> None:
    reply = _resolve(
        "desglose por estado",
        monkeypatch=monkeypatch,
        intent="UNIT_STATUS_BREAKDOWN",
        total_units=46,
        breakdown={"available": 3, "reserved": 1, "unavailable": 42},
        full_inventory_known=True,
    )

    assert "3 disponibles" in reply["answer"]
    assert "1 reservada" in reply["answer"]
    assert "42 no disponibles" in reply["answer"]
    assert "46 unidades en total" in reply["answer"]


def test_total_units_query_does_not_fallback_to_overview(monkeypatch) -> None:
    reply = _resolve(
        "cuantas unidades tiene el edificio",
        monkeypatch=monkeypatch,
        intent="TOTAL_UNITS",
        total_units=None,
        available_units=None,
        project_profile={
            "project_code": "MANZANARES_3277",
            "workspace_id": "ws_demo_vertice360",
            "units_total": None,
            "available_units": None,
            "reserved_units": None,
            "unavailable_units": None,
            "inventory_is_complete": False,
            "raw_status_breakdown_jsonb": {},
            "_source_table": "demo_project_profile",
        },
    )

    assert "No tengo cargado el total completo de unidades del proyecto" in reply["answer"]
    assert "Desarrollo de 2 y 3 ambientes" not in reply["answer"]
    assert "prefiero confirm" not in reply["answer"].lower()


def test_total_units_uses_demo_inventory_wording_when_inventory_incomplete(monkeypatch) -> None:
    reply = _resolve(
        "cuantas unidades son",
        monkeypatch=monkeypatch,
        intent="TOTAL_UNITS",
        total_units=4,
        available_units=4,
        breakdown={"available": 4},
        full_inventory_known=False,
    )

    assert "En el inventario demo que tengo cargado hoy" in reply["answer"]
    assert "veo 4 unidades" in reply["answer"]
    assert "No tengo cargado el total completo del proyecto" in reply["answer"]
    assert "tiene 4 unidades en total" not in reply["answer"]


def test_children_suitability_uses_project_profile(monkeypatch) -> None:
    reply = _resolve(
        "es apto para niños",
        monkeypatch=monkeypatch,
        intent="CHILDREN_SUITABILITY",
    )

    assert "familia con chicos" in reply["answer"].lower()
    assert "3c" in reply["answer"].lower() or "6a" in reply["answer"].lower()


def test_children_warning_response_when_warnings_exist(monkeypatch) -> None:
    reply = _resolve(
        "es seguro para chicos",
        monkeypatch=monkeypatch,
        intent="SAFETY_WARNINGS",
        project_profile={
            "project_code": "MANZANARES_3277",
            "workspace_id": "ws_demo_vertice360",
            "units_total": 4,
            "available_units": 4,
            "reserved_units": 0,
            "unavailable_units": 0,
            "inventory_is_complete": False,
            "raw_status_breakdown_jsonb": {"available": 4},
            "children_suitable": True,
            "pets_allowed": True,
            "pets_restrictions_text": "Confirmar reglamento.",
            "child_safety_warnings_jsonb": ["Confirmar altura de barandas y protecciones del balcón."],
            "usage_warnings_jsonb": ["Inventario demo parcial."],
            "recommended_profiles_jsonb": ["family"],
            "_source_table": "demo_project_profile",
        },
    )

    assert "hay algunos puntos a tener en cuenta" in reply["answer"].lower()
    assert "barandas" in reply["answer"].lower()


def test_pets_suitability_distinguishes_allowed_vs_recommended(monkeypatch) -> None:
    reply = _resolve(
        "sirve para mascotas",
        monkeypatch=monkeypatch,
        intent="PETS_SUITABILITY",
        project_profile={
            "project_code": "MANZANARES_3277",
            "workspace_id": "ws_demo_vertice360",
            "units_total": 4,
            "available_units": 4,
            "reserved_units": 0,
            "unavailable_units": 0,
            "inventory_is_complete": False,
            "raw_status_breakdown_jsonb": {"available": 4},
            "children_suitable": True,
            "pets_allowed": None,
            "pets_restrictions_text": "Confirmar reglamento del consorcio.",
            "recommended_profiles_jsonb": ["pets"],
            "_source_table": "demo_project_profile",
        },
    )

    assert "no tengo una confirmación general" in reply["answer"].lower()
    assert "sí veo" in reply["answer"].lower()
    assert "6a" in reply["answer"].lower()


def test_orientation_or_sunlight_unknown_returns_honest_no_info(monkeypatch) -> None:
    reply = _resolve(
        "le da el sol de mañana",
        monkeypatch=monkeypatch,
        intent="LIGHT_ORIENTATION",
    )

    assert "No tengo dato estructurado sobre sol de mañana" in reply["answer"]


def test_balcony_protection_unknown_returns_honest_answer(monkeypatch) -> None:
    reply = _resolve(
        "el balcón está protegido",
        monkeypatch=monkeypatch,
        intent="SAFETY_WARNINGS",
    )

    assert "protección del balcón" in reply["answer"].lower()
    assert "desconocida" in reply["answer"].lower()


def test_has_garden_query_uses_demo_unit_profile(monkeypatch) -> None:
    reply = _resolve(
        "hay unidades con jardín",
        monkeypatch=monkeypatch,
        intent="PROJECT_UNIT_SEARCH_BY_FEATURE",
        semantic_overrides={"feature_key": "jardin"},
    )

    assert "sí, en manzanares 3277" in reply["answer"].lower()
    assert "6a" in reply["answer"].lower()


def test_no_overclaim_when_project_profile_is_partial(monkeypatch) -> None:
    reply = _resolve(
        "cual es el total",
        monkeypatch=monkeypatch,
        intent="UNIT_STATUS_BREAKDOWN",
        total_units=4,
        available_units=4,
        breakdown={"available": 4},
        full_inventory_known=False,
    )

    assert "desglose es parcial" in reply["answer"].lower()
    assert "el proyecto tiene 4 unidades en total" not in reply["answer"].lower()


def test_detect_total_units_for_short_total_phrase() -> None:
    intent, followup, _ = services._detect_project_intent("cual es el total", summary=None)

    assert intent == "TOTAL_UNITS"
    assert followup is False


def test_detect_status_breakdown_for_available_reserved_phrase() -> None:
    intent, followup, _ = services._detect_project_intent("cuantas disponibles y cuantas reservadas", summary=None)

    assert intent == "UNIT_STATUS_BREAKDOWN"
    assert followup is False


def test_semantic_unit_specific_pets_query_extracts_unit_code() -> None:
    semantic = services._semantic_intent_resolver(
        "la 6A sirve para mascotas",
        detail=_detail_for_project("MANZANARES_3277", "Manzanares 3277 — Saavedra"),
        recent_messages=[],
        summary={},
    )

    assert semantic["intent"] == "PETS_SUITABILITY"
    assert semantic["unit_code"] == "6A"


def test_unit_specific_pets_query_uses_unit_profile(monkeypatch) -> None:
    reply = _resolve(
        "la 6A sirve para mascotas",
        monkeypatch=monkeypatch,
        intent="PETS_SUITABILITY",
        semantic_overrides={"unit_code": "6A"},
    )

    assert "unidad 6a" in reply["answer"].lower()
    assert "mascotas permitidas" in reply["answer"].lower()
    assert "jardín" in reply["answer"].lower()


def test_unit_specific_balcony_query_uses_unit_profile(monkeypatch) -> None:
    reply = _resolve(
        "la unidad 6A-TRZ tiene balcón protegido",
        monkeypatch=monkeypatch,
        intent="SAFETY_WARNINGS",
        semantic_overrides={"unit_code": "6A-TRZ"},
    )

    assert "unidad 6a-trz" in reply["answer"].lower()
    assert "no tengo confirmación estructurada" in reply["answer"].lower()


def test_surface_plural_query_resolves_to_filter_list_not_max(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch, project_code="GDR_3760_SAAVEDRA", project_name="GDR 3760 — Saavedra")
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-surface-filter",
        detail=_detail_for_project("GDR_3760_SAAVEDRA", "GDR 3760 — Saavedra"),
        question="me das departamentos mas grande que 60 mts cuadrados",
        recent_messages=[],
        semantic_resolution=None,
    )

    answer = reply["answer"].lower()
    assert reply["variant"] == "project_qa"
    assert "hoy veo estas unidades" in answer
    assert "más grande" not in answer
    assert "6a" in answer or "6a-trz" in answer


def test_surface_filter_query_returns_units_over_threshold(monkeypatch) -> None:
    merged_units = [
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "GDR_3760_SAAVEDRA",
            "project_name": "GDR 3760 — Saavedra",
            "unit_id": "gdr_p2",
            "unit_code": "P-2",
            "rooms_label": "2 ambientes",
            "rooms_count": 2,
            "surface_total_m2": 61.4,
            "currency": "USD",
            "list_price": 275700,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        },
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "GDR_3760_SAAVEDRA",
            "project_name": "GDR 3760 — Saavedra",
            "unit_id": "gdr_4a",
            "unit_code": "4A",
            "rooms_label": "3 ambientes",
            "rooms_count": 3,
            "surface_total_m2": 137.0,
            "currency": "USD",
            "list_price": 326800,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        },
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "GDR_3760_SAAVEDRA",
            "project_name": "GDR 3760 — Saavedra",
            "unit_id": "gdr_1b",
            "unit_code": "1B",
            "rooms_label": "2 ambientes",
            "rooms_count": 2,
            "surface_total_m2": 49.0,
            "currency": "USD",
            "list_price": 210000,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        },
    ]
    _patch_dialog_repo(
        monkeypatch,
        project_code="GDR_3760_SAAVEDRA",
        project_name="GDR 3760 — Saavedra",
        merged_units=merged_units,
    )
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-surface-threshold",
        detail=_detail_for_project("GDR_3760_SAAVEDRA", "GDR 3760 — Saavedra"),
        question="los que tengan mas de 60 m2",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert "4A" in reply["answer"]
    assert "P-2" in reply["answer"]
    assert "1B" not in reply["answer"]


def test_unit_list_result_set_saved_after_surface_filter_query(monkeypatch) -> None:
    merged_units = [
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "GDR_3760_SAAVEDRA",
            "project_name": "GDR 3760 — Saavedra",
            "unit_id": "gdr_p2",
            "unit_code": "2B",
            "rooms_label": "2 ambientes",
            "rooms_count": 2,
            "surface_total_m2": 113.0,
            "currency": "USD",
            "list_price": 275700,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        },
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "GDR_3760_SAAVEDRA",
            "project_name": "GDR 3760 — Saavedra",
            "unit_id": "gdr_3b",
            "unit_code": "3B",
            "rooms_label": "3 ambientes",
            "rooms_count": 3,
            "surface_total_m2": 113.0,
            "currency": "USD",
            "list_price": 297600,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        },
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "GDR_3760_SAAVEDRA",
            "project_name": "GDR 3760 — Saavedra",
            "unit_id": "gdr_4a",
            "unit_code": "4A",
            "rooms_label": "3 ambientes",
            "rooms_count": 3,
            "surface_total_m2": 137.0,
            "currency": "USD",
            "list_price": 326800,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        },
    ]
    _patch_dialog_repo(
        monkeypatch,
        project_code="GDR_3760_SAAVEDRA",
        project_name="GDR 3760 — Saavedra",
        merged_units=merged_units,
    )
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-result-set",
        detail=_detail_for_project("GDR_3760_SAAVEDRA", "GDR 3760 — Saavedra"),
        question="los que tengan mas de 60 m2",
        recent_messages=[],
        semantic_resolution=None,
    )

    summary_patch = reply["summary_patch"]
    assert summary_patch["last_subject_type"] == "unit_list"
    assert len(summary_patch["last_result_units"]) == 3
    assert summary_patch["last_result_project_code"] == "GDR_3760_SAAVEDRA"


def test_followup_por_precio_reorders_previous_unit_list(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch, project_code="GDR_3760_SAAVEDRA", project_name="GDR 3760 — Saavedra")
    detail = {
        "project_code": "GDR_3760_SAAVEDRA",
        "project_name": "GDR 3760 — Saavedra",
        "summary_jsonb": {
            "selected_project": {"code": "GDR_3760_SAAVEDRA", "name": "GDR 3760 — Saavedra"},
            "last_result_units": [
                {"project_code": "GDR_3760_SAAVEDRA", "project_name": "GDR 3760 — Saavedra", "unit_id": "gdr_4a", "unit_code": "4A", "rooms_label": "3 ambientes", "rooms_count": 3, "surface_total_m2": 137.0, "list_price": 326800, "currency": "USD", "availability_status": "available"},
                {"project_code": "GDR_3760_SAAVEDRA", "project_name": "GDR 3760 — Saavedra", "unit_id": "gdr_3b", "unit_code": "3B", "rooms_label": "3 ambientes", "rooms_count": 3, "surface_total_m2": 113.0, "list_price": 297600, "currency": "USD", "availability_status": "available"},
                {"project_code": "GDR_3760_SAAVEDRA", "project_name": "GDR 3760 — Saavedra", "unit_id": "gdr_2b", "unit_code": "2B", "rooms_label": "2 ambientes", "rooms_count": 2, "surface_total_m2": 113.0, "list_price": 275700, "currency": "USD", "availability_status": "available"},
            ],
        },
    }
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-sort-price",
        detail=detail,
        question="por precio",
        recent_messages=[],
        semantic_resolution=None,
    )

    answer = reply["answer"]
    assert reply["variant"] == "unit_list_followup"
    assert "Ordenadas por precio" in answer
    assert answer.index("2B") < answer.index("3B") < answer.index("4A")
    assert reply["summary_patch"]["last_subject_type"] == "unit_list"


def test_followup_por_metros_reorders_previous_unit_list(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch, project_code="GDR_3760_SAAVEDRA", project_name="GDR 3760 — Saavedra")
    detail = {
        "project_code": "GDR_3760_SAAVEDRA",
        "project_name": "GDR 3760 — Saavedra",
        "summary_jsonb": {
            "selected_project": {"code": "GDR_3760_SAAVEDRA", "name": "GDR 3760 — Saavedra"},
            "last_result_units": [
                {"project_code": "GDR_3760_SAAVEDRA", "project_name": "GDR 3760 — Saavedra", "unit_id": "gdr_2b", "unit_code": "2B", "rooms_label": "2 ambientes", "rooms_count": 2, "surface_total_m2": 113.0, "list_price": 275700, "currency": "USD", "availability_status": "available"},
                {"project_code": "GDR_3760_SAAVEDRA", "project_name": "GDR 3760 — Saavedra", "unit_id": "gdr_4a", "unit_code": "4A", "rooms_label": "3 ambientes", "rooms_count": 3, "surface_total_m2": 137.0, "list_price": 326800, "currency": "USD", "availability_status": "available"},
            ],
        },
    }
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-sort-surface",
        detail=detail,
        question="por metros",
        recent_messages=[],
        semantic_resolution=None,
    )

    answer = reply["answer"]
    assert "Ordenadas por metros" in answer
    assert answer.index("4A") < answer.index("2B")


def test_followup_cual_es_la_mas_grande_uses_previous_result_set(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch, project_code="GDR_3760_SAAVEDRA", project_name="GDR 3760 — Saavedra")
    detail = {
        "project_code": "GDR_3760_SAAVEDRA",
        "project_name": "GDR 3760 — Saavedra",
        "summary_jsonb": {
            "selected_project": {"code": "GDR_3760_SAAVEDRA", "name": "GDR 3760 — Saavedra"},
            "last_result_units": [
                {"project_code": "GDR_3760_SAAVEDRA", "project_name": "GDR 3760 — Saavedra", "unit_id": "gdr_2b", "unit_code": "2B", "rooms_label": "2 ambientes", "rooms_count": 2, "surface_total_m2": 113.0, "list_price": 275700, "currency": "USD", "availability_status": "available"},
                {"project_code": "GDR_3760_SAAVEDRA", "project_name": "GDR 3760 — Saavedra", "unit_id": "gdr_4a", "unit_code": "4A", "rooms_label": "3 ambientes", "rooms_count": 3, "surface_total_m2": 137.0, "list_price": 326800, "currency": "USD", "availability_status": "available"},
            ],
        },
    }
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-extreme-surface",
        detail=detail,
        question="y por metros cual es la mas grande",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["variant"] == "unit_list_followup"
    assert "la más grande del último listado es la 4a" in reply["answer"].lower()


def test_last_subject_unit_saved_after_extreme_answer(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch, project_code="GDR_3760_SAAVEDRA", project_name="GDR 3760 — Saavedra")
    detail = {
        "project_code": "GDR_3760_SAAVEDRA",
        "project_name": "GDR 3760 — Saavedra",
        "summary_jsonb": {
            "selected_project": {"code": "GDR_3760_SAAVEDRA", "name": "GDR 3760 — Saavedra"},
            "last_result_units": [
                {"project_code": "GDR_3760_SAAVEDRA", "project_name": "GDR 3760 — Saavedra", "unit_id": "gdr_2b", "unit_code": "2B", "rooms_label": "2 ambientes", "rooms_count": 2, "surface_total_m2": 113.0, "list_price": 275700, "currency": "USD", "availability_status": "available"},
                {"project_code": "GDR_3760_SAAVEDRA", "project_name": "GDR 3760 — Saavedra", "unit_id": "gdr_4a", "unit_code": "4A", "rooms_label": "3 ambientes", "rooms_count": 3, "surface_total_m2": 137.0, "list_price": 326800, "currency": "USD", "availability_status": "available"},
            ],
        },
    }
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-extreme-subject",
        detail=detail,
        question="cual es la mas grande",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["summary_patch"]["last_subject_type"] == "unit"
    assert reply["summary_patch"]["last_subject_unit_code"] == "4A"


def test_followup_cuantos_metros_uses_last_subject_unit(monkeypatch) -> None:
    reply = _resolve(
        "cuantos metros",
        monkeypatch=monkeypatch,
        intent="SURFACE_QUERY",
        semantic_overrides={"unit_code": "6A"},
    )

    assert reply["variant"] == "unit_detail_answer"
    assert "la unidad 6a tiene 84,0 m² totales" in reply["answer"].lower()


def test_no_project_fallback_for_result_set_followups(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch, project_code="GDR_3760_SAAVEDRA", project_name="GDR 3760 — Saavedra")
    detail = {
        "summary_jsonb": {
            "last_result_units": [
                {"project_code": "GDR_3760_SAAVEDRA", "project_name": "GDR 3760 — Saavedra", "unit_id": "gdr_2b", "unit_code": "2B", "rooms_label": "2 ambientes", "rooms_count": 2, "surface_total_m2": 113.0, "list_price": 275700, "currency": "USD", "availability_status": "available"},
                {"project_code": "GDR_3760_SAAVEDRA", "project_name": "GDR 3760 — Saavedra", "unit_id": "gdr_4a", "unit_code": "4A", "rooms_label": "3 ambientes", "rooms_count": 3, "surface_total_m2": 137.0, "list_price": 326800, "currency": "USD", "availability_status": "available"},
            ]
        },
    }
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-no-project-result-set",
        detail=detail,
        question="por precio",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["variant"] == "unit_list_followup"
    assert "sobre qué proyecto" not in reply["answer"].lower()


def test_project_comparison_query_overrides_unit_result_set_context() -> None:
    detail = _detail_for_active_balcony_result_set()

    semantic = services._semantic_intent_resolver(
        "de todos los proyectos cual es el proyecto con mas metros cuadrados construido",
        detail=detail,
        recent_messages=[],
        summary=detail["summary_jsonb"],
    )

    assert semantic["intent"] == "PROJECT_COMPARISON_BY_SURFACE"
    assert semantic["chosen_project"] is None
    assert semantic.get("search_scope") == "global"



def test_project_comparison_by_reserved_units_detected_from_cual_es() -> None:
    semantic = services._semantic_intent_resolver(
        "cual es el proyecto con mas reservas",
        detail=None,
        recent_messages=[],
        summary={},
    )

    assert semantic["intent"] == "PROJECT_COMPARISON_BY_METRIC"
    assert semantic.get("comparison_metric") == "reserved_units"
    assert semantic.get("search_scope") == "global"



def test_project_comparison_by_reserved_units_detected_from_que_proyecto() -> None:
    semantic = services._semantic_intent_resolver(
        "que proyecto tiene mas reservas",
        detail=None,
        recent_messages=[],
        summary={},
    )

    assert semantic["intent"] == "PROJECT_COMPARISON_BY_METRIC"
    assert semantic.get("comparison_metric") == "reserved_units"



def test_project_comparison_by_reserved_units_detected_from_de_todos_los_proyectos() -> None:
    semantic = services._semantic_intent_resolver(
        "de todos los proyectos cual tiene mas reservas",
        detail=None,
        recent_messages=[],
        summary={},
    )

    assert semantic["intent"] == "PROJECT_COMPARISON_BY_METRIC"
    assert semantic.get("comparison_metric") == "reserved_units"



def test_cual_proyecto_tiene_mas_metros_routes_to_surface_comparison() -> None:
    semantic = services._semantic_intent_resolver(
        "cual proyecto tiene mas metros",
        detail=None,
        recent_messages=[],
        summary={},
    )

    assert semantic["intent"] == "PROJECT_COMPARISON_BY_SURFACE"
    assert semantic.get("search_scope") == "global"



def test_explicit_project_reservations_query_does_not_go_global_comparison() -> None:
    semantic = services._semantic_intent_resolver(
        "cuantas reservas tiene Bulnes 966",
        detail=None,
        recent_messages=[],
        summary={},
    )

    assert semantic["intent"] == "PROJECT_METRIC_VALUE"
    assert semantic.get("comparison_metric") == "reserved_units"
    assert semantic.get("chosen_project") == "BULNES_966_ALMAGRO"



def test_project_comparison_by_reserved_units_returns_global_answer(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    _patch_global_project_inventory_summaries(
        monkeypatch,
        {
            "BULNES_966_ALMAGRO": {"reserved_units": 2},
            "GDR_3760_SAAVEDRA": {"reserved_units": 5},
            "MANZANARES_3277": {"reserved_units": 1},
        },
    )

    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-project-reserves-top",
        detail=_detail_for_project("MANZANARES_3277", "Manzanares 3277 — Saavedra"),
        question="cual es el proyecto con mas reservas",
        recent_messages=[],
        semantic_resolution={
            "intent": "PROJECT_COMPARISON_BY_METRIC",
            "followup": False,
            "reason": "test_case",
            "chosen_project": None,
            "excluded_project_codes": [],
            "search_scope": "global",
            "comparison_metric": "reserved_units",
        },
    )

    answer = reply["answer"].lower()
    assert reply["variant"] == "project_comparison_metric"
    assert "gdr 3760" in answer
    assert "5 reservas" in answer



def test_project_comparison_by_reserved_units_returns_zero_tie_when_all_projects_have_zero(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    _patch_global_project_inventory_summaries(
        monkeypatch,
        {
            "BULNES_966_ALMAGRO": {},
            "GDR_3760_SAAVEDRA": {},
            "MANZANARES_3277": {},
        },
    )

    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-project-reserves-zero-tie",
        detail=_detail_for_project("MANZANARES_3277", "Manzanares 3277 — Saavedra"),
        question="cual es el proyecto con mas reservas",
        recent_messages=[],
        semantic_resolution={
            "intent": "PROJECT_COMPARISON_BY_METRIC",
            "followup": False,
            "reason": "test_case",
            "chosen_project": None,
            "excluded_project_codes": [],
            "search_scope": "global",
            "comparison_metric": "reserved_units",
        },
    )

    answer = reply["answer"].lower()
    assert reply["variant"] == "project_comparison_metric"
    assert reply["found"] is True
    assert "0 reservas" in answer
    assert "no hay un proyecto con más reservas que otro" in answer



def test_project_comparison_by_reserved_units_ignores_previous_unit_result_set(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    _patch_global_project_inventory_summaries(
        monkeypatch,
        {
            "BULNES_966_ALMAGRO": {"reserved_units": 2},
            "GDR_3760_SAAVEDRA": {"reserved_units": 5},
            "MANZANARES_3277": {"reserved_units": 1},
        },
    )
    detail = _detail_for_active_balcony_result_set()

    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-project-reserves-no-unit-fallback",
        detail=detail,
        question="cual es el proyecto con mas reservas",
        recent_messages=[],
        semantic_resolution=None,
    )

    answer = reply["answer"].lower()
    assert reply["variant"] == "project_comparison_metric"
    assert "gdr 3760" in answer
    assert "balcon" not in answer
    assert "4a" not in answer
    assert reply["summary_patch"]["last_result_units"] == []



def test_project_reservations_followup_keeps_global_scope_from_previous_comparison() -> None:
    detail = _detail_for_project("MANZANARES_3277", "Manzanares 3277 — Saavedra")
    detail["summary_jsonb"].update(
        {
            "last_intent": "PROJECT_COMPARISON_BY_METRIC",
            "last_search_scope": "global",
            "last_result_slots": {"comparison_metric": "reserved_units", "comparison_mode": "leader"},
        }
    )

    semantic = services._semantic_intent_resolver(
        "y la cantidad de reservas",
        detail=detail,
        recent_messages=[],
        summary=detail["summary_jsonb"],
    )

    assert semantic["intent"] == "PROJECT_COMPARISON_BY_METRIC"
    assert semantic.get("comparison_metric") == "reserved_units"
    assert semantic.get("comparison_mode") == "breakdown"
    assert semantic.get("search_scope") == "global"
    assert semantic.get("chosen_project") is None



def test_project_reservations_followup_returns_global_breakdown(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    _patch_global_project_inventory_summaries(
        monkeypatch,
        {
            "BULNES_966_ALMAGRO": {},
            "GDR_3760_SAAVEDRA": {},
            "MANZANARES_3277": {},
        },
    )
    detail = _detail_for_project("MANZANARES_3277", "Manzanares 3277 — Saavedra")
    detail["summary_jsonb"].update(
        {
            "last_intent": "PROJECT_COMPARISON_BY_METRIC",
            "last_search_scope": "global",
            "last_result_slots": {"comparison_metric": "reserved_units", "comparison_mode": "leader"},
        }
    )

    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-project-reserves-followup-breakdown",
        detail=detail,
        question="y la cantidad de reservas",
        recent_messages=[],
        semantic_resolution=None,
    )

    answer = reply["answer"].lower()
    assert reply["variant"] == "project_comparison_metric"
    assert reply["followup"] is True
    assert "bulnes 966" in answer
    assert "gdr 3760" in answer
    assert "manzanares 3277" in answer
    assert answer.count("0 reservas") == 3
    assert "sobre qué proyecto" not in answer



def test_selected_project_reservations_query_uses_active_project(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch, breakdown={"available": 3, "reserved": 0})

    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-selected-project-reserves",
        detail=_detail_for_project("MANZANARES_3277", "Manzanares 3277 — Saavedra"),
        question="quiero saber la cantidad de reservas",
        recent_messages=[],
        semantic_resolution=None,
    )

    answer = reply["answer"].lower()
    assert reply["variant"] == "project_metric_value"
    assert reply["found"] is True
    assert "manzanares 3277" in answer
    assert "0 reservas" in answer
    assert "sobre qué proyecto" not in answer



def test_explicit_project_reservations_query_returns_project_metric_value(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    project_names = {
        "BULNES_966_ALMAGRO": "Bulnes 966 — Almagro",
        "GDR_3760_SAAVEDRA": "GDR 3760 — Saavedra",
        "MANZANARES_3277": "Manzanares 3277 — Saavedra",
    }
    inventory_by_project = {
        "BULNES_966_ALMAGRO": {"reserved_units": 2, "_source_table": "demo_project_profile"},
        "GDR_3760_SAAVEDRA": {"reserved_units": 0, "_source_table": "demo_project_profile"},
        "MANZANARES_3277": {"reserved_units": 0, "_source_table": "demo_project_profile"},
    }
    monkeypatch.setattr(
        services.repo,
        "get_project_by_code",
        lambda conn, code: {"id": f"prj-{code}", "code": code, "name": project_names[str(code).strip().upper()]},
    )
    monkeypatch.setattr(
        services.repo,
        "get_project_inventory_summary",
        lambda conn, code: {"project_code": code, **inventory_by_project[str(code).strip().upper()]},
    )

    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-explicit-project-reserves",
        detail=None,
        question="cuantas reservas tiene Bulnes 966",
        recent_messages=[],
        semantic_resolution=None,
    )

    answer = reply["answer"].lower()
    assert reply["variant"] == "project_metric_value"
    assert reply["found"] is True
    assert "bulnes 966" in answer
    assert "2 reservas" in answer
    assert "sobre qué proyecto" not in answer



def test_project_comparison_query_does_not_reuse_last_subject_unit() -> None:
    detail = {
        "summary_jsonb": {
            "last_subject_type": "unit",
            "last_subject_unit_id": "gdr_4a",
            "last_subject_unit_code": "4A",
            "last_subject_project_code": "GDR_3760_SAAVEDRA",
            "last_subject_project_name": "GDR 3760 — Saavedra",
            "last_subject_summary": "Unidad 4A con balcón",
        }
    }

    semantic = services._semantic_intent_resolver(
        "que proyecto tiene mas metros cuadrados construidos",
        detail=detail,
        recent_messages=[],
        summary=detail["summary_jsonb"],
    )

    assert semantic["intent"] == "PROJECT_COMPARISON_BY_SURFACE"
    assert not semantic.get("unit_code")



def test_project_entity_override_blocks_result_set_extreme_followup() -> None:
    detail = _detail_for_active_balcony_result_set()

    semantic = services._semantic_intent_resolver(
        "que proyecto es el mas grande en metros cuadrados",
        detail=detail,
        recent_messages=[],
        summary=detail["summary_jsonb"],
    )

    assert semantic["intent"] == "PROJECT_COMPARISON_BY_SURFACE"
    assert not semantic.get("result_set_extreme")



def test_de_todos_los_proyectos_resets_unit_result_set_priority(monkeypatch) -> None:
    merged_units = [dict(row) for row in _detail_for_active_balcony_result_set()["summary_jsonb"]["last_result_units"]]
    _patch_dialog_repo(monkeypatch, merged_units=merged_units)
    detail = _detail_for_active_balcony_result_set()

    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-project-scope-reset",
        detail=detail,
        question="de todos los proyectos cual es el proyecto con mas metros cuadrados construido",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["variant"] == "project_comparison_surface"
    assert reply["summary_patch"]["last_result_units"] == []
    assert reply["summary_patch"]["active_filter"] is None
    assert reply["summary_patch"]["last_search_scope"] == "global"



def test_project_with_more_constructed_m2_returns_honest_partial_or_no_info(monkeypatch) -> None:
    merged_units = [dict(row) for row in _detail_for_active_balcony_result_set()["summary_jsonb"]["last_result_units"]]
    reply = _resolve(
        "que proyecto tiene mas metros cuadrados construidos",
        monkeypatch=monkeypatch,
        intent="PROJECT_COMPARISON_BY_SURFACE",
        merged_units=merged_units,
        semantic_overrides={"search_scope": "global"},
    )

    answer = reply["answer"].lower()
    assert reply["variant"] == "project_comparison_surface"
    assert "tomando solo las unidades demo" in answer or "no tengo cargado el total de metros cuadrados construidos" in answer
    assert "inventario demo parcial" in answer or "no tengo cargado el total" in answer
    assert "gdr 3760" in answer



def test_project_comparison_does_not_fallback_to_previous_balcony_list(monkeypatch) -> None:
    merged_units = [dict(row) for row in _detail_for_active_balcony_result_set()["summary_jsonb"]["last_result_units"]]
    _patch_dialog_repo(monkeypatch, merged_units=merged_units)
    detail = _detail_for_active_balcony_result_set()

    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-project-comparison-no-balcony-fallback",
        detail=detail,
        question="de todos los proyectos cual es el proyecto con mas metros cuadrados construido",
        recent_messages=[],
        semantic_resolution=None,
    )

    answer = reply["answer"].lower()
    assert reply["variant"] == "project_comparison_surface"
    assert "ultimo listado" not in answer
    assert "balcon" not in answer
    assert "4a" not in answer
    assert "a-7c" not in answer



def test_global_scope_ack_cualquiera_after_global_search_does_not_require_project(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-global-ack",
        detail={
            "summary_jsonb": {
                "last_intent": "GLOBAL_UNIT_SEARCH_BY_FEATURE",
                "last_search_scope": "global",
            }
        },
        question="cualquiera",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["variant"] == "social_ack"
    assert "todos los proyectos" in reply["answer"].lower()


def test_out_of_scope_question_with_selected_project_returns_honest_sensitive_reply(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch, project_code="MANZANARES_3277", project_name="Manzanares 3277 — Saavedra")
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-out-of-scope",
        detail=_detail_for_project("MANZANARES_3277", "Manzanares 3277 — Saavedra"),
        question="expensas",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["variant"] == "project_sensitive"
    assert "prefiero confirmártelo" in reply["answer"].lower()


def test_pets_recommendation_query_resolves_to_pets_suitability(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch, project_code="MANZANARES_3277", project_name="Manzanares 3277 — Saavedra")
    semantic = services._semantic_intent_resolver(
        "cual recomendás para mascotas?",
        detail=_detail_for_project("MANZANARES_3277", "Manzanares 3277 — Saavedra"),
        recent_messages=[],
        summary={"selected_project": {"code": "MANZANARES_3277", "name": "Manzanares 3277 — Saavedra"}},
    )

    assert semantic["intent"] == "PETS_SUITABILITY"


def test_followup_que_precio_tiene_uses_last_unit_subject(monkeypatch) -> None:
    merged_units = [
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "GDR_3760_SAAVEDRA",
            "project_name": "GDR 3760 — Saavedra",
            "unit_id": "gdr_p2",
            "unit_code": "P-2",
            "rooms_label": "2 ambientes",
            "rooms_count": 2,
            "surface_total_m2": 61.4,
            "currency": "USD",
            "list_price": 275700,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        }
    ]
    _patch_dialog_repo(
        monkeypatch,
        project_code="GDR_3760_SAAVEDRA",
        project_name="GDR 3760 — Saavedra",
        merged_units=merged_units,
    )
    detail = {
        "project_code": "GDR_3760_SAAVEDRA",
        "project_name": "GDR 3760 — Saavedra",
        "summary_jsonb": {
            "selected_project": {"code": "GDR_3760_SAAVEDRA", "name": "GDR 3760 — Saavedra"},
            "last_subject_type": "unit",
            "last_subject_project_code": "GDR_3760_SAAVEDRA",
            "last_subject_unit_id": "gdr_p2",
            "last_subject_unit_code": "P-2",
            "last_subject_summary": "P-2 en GDR 3760 — Saavedra",
        },
    }
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-unit-price-followup",
        detail=detail,
        question="que precio tiene",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["variant"] == "unit_detail_answer"
    assert "unidad p-2" in reply["answer"].lower()
    assert "usd 275.700" in reply["answer"].lower()


def test_followup_unit_price_does_not_fallback_to_project_range(monkeypatch) -> None:
    merged_units = [
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "GDR_3760_SAAVEDRA",
            "project_name": "GDR 3760 — Saavedra",
            "unit_id": "gdr_p2",
            "unit_code": "P-2",
            "rooms_label": "2 ambientes",
            "rooms_count": 2,
            "surface_total_m2": 61.4,
            "currency": "USD",
            "list_price": 275700,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        }
    ]
    _patch_dialog_repo(
        monkeypatch,
        project_code="GDR_3760_SAAVEDRA",
        project_name="GDR 3760 — Saavedra",
        merged_units=merged_units,
    )
    detail = {
        "project_code": "GDR_3760_SAAVEDRA",
        "project_name": "GDR 3760 — Saavedra",
        "summary_jsonb": {
            "selected_project": {"code": "GDR_3760_SAAVEDRA", "name": "GDR 3760 — Saavedra"},
            "last_subject_type": "unit",
            "last_subject_project_code": "GDR_3760_SAAVEDRA",
            "last_subject_unit_id": "gdr_p2",
            "last_subject_unit_code": "P-2",
        },
    }
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-unit-price-no-range",
        detail=detail,
        question="esa cuanto vale",
        recent_messages=[],
        semantic_resolution=None,
    )

    answer = reply["answer"].lower()
    assert "desde usd" not in answer
    assert "hasta usd" not in answer
    assert "unidad p-2" in answer


def test_detect_light_queries_for_luminoso_and_como_da() -> None:
    assert services._detect_project_intent("es luminoso", summary=None)[0] == "LIGHT_ORIENTATION"
    assert services._detect_project_intent("como da", summary=None)[0] == "LIGHT_ORIENTATION"


def test_selected_project_typo_cracteristicas_resolves_to_features(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch, project_code="GDR_3760_SAAVEDRA", project_name="GDR 3760 — Saavedra")
    semantic = services._semantic_intent_resolver(
        "cracteristicas",
        detail=_detail_for_project("GDR_3760_SAAVEDRA", "GDR 3760 — Saavedra"),
        recent_messages=[],
        summary={"selected_project": {"code": "GDR_3760_SAAVEDRA", "name": "GDR 3760 — Saavedra"}},
    )

    assert semantic["intent"] == "FEATURES"
    assert semantic["chosen_project"] == "GDR_3760_SAAVEDRA"
    assert semantic["reason"] == "semantic_fuzzy_features"


def test_selected_project_typo_presio_resolves_to_price() -> None:
    semantic = services._semantic_intent_resolver(
        "presio",
        detail=_detail_for_project("BULNES_966_ALMAGRO", "Bulnes 966 — Almagro"),
        recent_messages=[],
        summary={"selected_project": {"code": "BULNES_966_ALMAGRO", "name": "Bulnes 966 — Almagro"}},
    )

    assert semantic["intent"] == "PRICE"
    assert semantic["chosen_project"] == "BULNES_966_ALMAGRO"
    assert semantic["reason"] == "semantic_fuzzy_price"


def test_selected_project_typo_entrga_resolves_to_delivery() -> None:
    semantic = services._semantic_intent_resolver(
        "entrga",
        detail=_detail_for_project("BULNES_966_ALMAGRO", "Bulnes 966 — Almagro"),
        recent_messages=[],
        summary={"selected_project": {"code": "BULNES_966_ALMAGRO", "name": "Bulnes 966 — Almagro"}},
    )

    assert semantic["intent"] == "DELIVERY"
    assert semantic["chosen_project"] == "BULNES_966_ALMAGRO"
    assert semantic["reason"] == "semantic_fuzzy_delivery"


def test_typo_without_project_selected_keeps_safe_behavior(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-no-project",
        detail={"summary_jsonb": {}},
        question="cracteristicas",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["variant"] in {"choose_project_once", "project_handoff"}
    assert "proyecto" in reply["answer"].lower()


def test_choose_project_not_triggered_for_high_similarity_known_intent(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch, project_code="GDR_3760_SAAVEDRA", project_name="GDR 3760 — Saavedra")
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-selected-project",
        detail=_detail_for_project("GDR_3760_SAAVEDRA", "GDR 3760 — Saavedra"),
        question="cracteristicas",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["variant"] == "project_qa"
    assert "gdr 3760" in reply["project_name"].lower()
    assert "sobre qué proyecto" not in reply["answer"].lower()


def test_single_output_with_typo_input(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch, project_code="BULNES_966_ALMAGRO", project_name="Bulnes 966 — Almagro")
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-typo-output",
        detail=_detail_for_project("BULNES_966_ALMAGRO", "Bulnes 966 — Almagro"),
        question="presio",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["variant"] == "project_qa"
    assert isinstance(reply["answer"], str)
    assert reply["answer"].count("?") <= 1


def test_greeting_hola_returns_natural_greeting_not_hard_choose_project(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-greeting",
        detail={"summary_jsonb": {}},
        question="hola",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["variant"] == "social_greeting"
    assert "hola" in reply["answer"].lower()
    assert "bulnes 966" in reply["answer"].lower()


def test_greeting_hi_returns_natural_response(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-hi",
        detail={"summary_jsonb": {}},
        question="hi",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["variant"] == "social_greeting"
    assert "hola" in reply["answer"].lower()


def test_ack_gracias_without_context_does_not_fall_to_choose_project_hard(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-gracias",
        detail={"summary_jsonb": {}},
        question="gracias",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["variant"] == "social_ack"
    assert "gracias" in reply["answer"].lower()
    assert "proyecto" not in reply["answer"].lower()


def test_ack_ok_with_selected_project_does_not_reset_context(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch, project_code="GDR_3760_SAAVEDRA", project_name="GDR 3760 — Saavedra")
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-ok",
        detail=_detail_for_project("GDR_3760_SAAVEDRA", "GDR 3760 — Saavedra"),
        question="ok",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["variant"] == "social_ack"
    assert reply["project_code"] == "GDR_3760_SAAVEDRA"
    assert "gdr 3760" in reply["answer"].lower()


def test_thumbs_up_does_not_trigger_overview_or_choose_project(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch, project_code="GDR_3760_SAAVEDRA", project_name="GDR 3760 — Saavedra")
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-thumbs",
        detail=_detail_for_project("GDR_3760_SAAVEDRA", "GDR 3760 — Saavedra"),
        question="👍",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["variant"] == "social_ack"
    assert "proyecto" not in reply["answer"].lower()
    assert "desarrollo" not in reply["answer"].lower()


def test_social_messages_single_output(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-social-single",
        detail={"summary_jsonb": {}},
        question="perfecto",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["variant"] == "social_ack"
    assert reply["answer"].count("?") <= 1


def test_global_scope_override_surface_filter_does_not_require_project(monkeypatch) -> None:
    merged_units = [
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "BULNES_966_ALMAGRO",
            "project_name": "Bulnes 966 — Almagro",
            "unit_id": "bulnes-a7c",
            "unit_code": "A-7C",
            "rooms_label": "2 ambientes",
            "rooms_count": 2,
            "surface_total_m2": 59.2,
            "currency": "USD",
            "list_price": 148000,
            "_source_table": "demo_units",
        },
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "GDR_3760_SAAVEDRA",
            "project_name": "GDR 3760 — Saavedra",
            "unit_id": "gdr-8a",
            "unit_code": "G-8A",
            "rooms_label": "3 ambientes",
            "rooms_count": 3,
            "surface_total_m2": 88.0,
            "currency": "USD",
            "list_price": 310000,
            "_source_table": "demo_units",
        },
    ]
    _patch_dialog_repo(monkeypatch, merged_units=merged_units)
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-global-surface",
        detail=_detail_for_project("BULNES_966_ALMAGRO", "Bulnes 966 — Almagro"),
        question="No importa el proyecto listado departamento más grandes que 50mts cuadrados",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["variant"] == "global_unit_filter_search"
    assert "varios proyectos" in reply["answer"].lower()
    assert "sobre qué proyecto" not in reply["answer"].lower()


def test_global_scope_override_persists_for_immediate_followup(monkeypatch) -> None:
    semantic = services._semantic_intent_resolver(
        "Los que tengan departamentos más grandes que 50 mts cuadrados",
        detail=_detail_for_project("BULNES_966_ALMAGRO", "Bulnes 966 — Almagro"),
        recent_messages=[],
        summary={"selected_project": {"code": "BULNES_966_ALMAGRO", "name": "Bulnes 966 — Almagro"}, "last_search_scope": "global", "last_intent": "GLOBAL_UNIT_FILTER_SEARCH"},
    )

    assert semantic["intent"] == "GLOBAL_UNIT_FILTER_SEARCH"
    assert semantic.get("search_scope") == "global"


def test_global_scope_phrase_any_project_forces_global_search() -> None:
    semantic = services._semantic_intent_resolver(
        "cualquiera con más de 50 m2",
        detail=_detail_for_project("BULNES_966_ALMAGRO", "Bulnes 966 — Almagro"),
        recent_messages=[],
        summary={"selected_project": {"code": "BULNES_966_ALMAGRO", "name": "Bulnes 966 — Almagro"}},
    )

    assert semantic["intent"] == "GLOBAL_UNIT_FILTER_SEARCH"
    assert semantic.get("search_scope") == "global"


def test_selected_project_not_used_when_user_says_no_importa_el_proyecto(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-global-feature",
        detail=_detail_for_project("BULNES_966_ALMAGRO", "Bulnes 966 — Almagro"),
        question="no importa el proyecto, mostrame los que tienen jardín",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["variant"] == "global_unit_feature_search"


def test_count_units_by_rooms_does_not_resolve_as_unit_detail(monkeypatch) -> None:
    merged_units = [
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "MANZANARES_3277",
            "project_name": "Manzanares 3277 — Saavedra",
            "unit_id": "manz_2a",
            "unit_code": "2A",
            "rooms_label": "2 ambientes",
            "rooms_count": 2,
            "surface_total_m2": 56.0,
            "currency": "USD",
            "list_price": 130000,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        },
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "MANZANARES_3277",
            "project_name": "Manzanares 3277 — Saavedra",
            "unit_id": "manz_2b",
            "unit_code": "2B",
            "rooms_label": "2 ambientes",
            "rooms_count": 2,
            "surface_total_m2": 58.0,
            "currency": "USD",
            "list_price": 145000,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        },
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "MANZANARES_3277",
            "project_name": "Manzanares 3277 — Saavedra",
            "unit_id": "manz_6a",
            "unit_code": "6A",
            "rooms_label": "3 ambientes",
            "rooms_count": 3,
            "surface_total_m2": 84.0,
            "currency": "USD",
            "list_price": 210000,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        },
    ]
    _patch_dialog_repo(monkeypatch, merged_units=merged_units)
    detail = {
        "project_code": "MANZANARES_3277",
        "project_name": "Manzanares 3277 — Saavedra",
        "summary_jsonb": {
            "selected_project": {"code": "MANZANARES_3277", "name": "Manzanares 3277 — Saavedra"},
            "last_subject_type": "unit",
            "last_subject_project_code": "MANZANARES_3277",
            "last_subject_project_name": "Manzanares 3277 — Saavedra",
            "last_subject_unit_id": "manz_6a",
            "last_subject_unit_code": "6A",
            "last_subject_summary": "6A en Manzanares 3277 — Saavedra",
        },
    }

    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-rooms-count",
        detail=detail,
        question="Cantidad de unidades 2 ambientes",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["variant"] == "project_units_by_rooms_count"
    assert "2 unidades de 2 ambientes" in reply["answer"].lower()
    assert "unidad 6a" not in reply["answer"].lower()


def test_list_units_by_rooms_returns_only_requested_typology(monkeypatch) -> None:
    merged_units = [
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "MANZANARES_3277",
            "project_name": "Manzanares 3277 — Saavedra",
            "unit_id": "manz_2a",
            "unit_code": "2A",
            "rooms_label": "2 ambientes",
            "rooms_count": 2,
            "surface_total_m2": 56.0,
            "currency": "USD",
            "list_price": 130000,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        },
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "MANZANARES_3277",
            "project_name": "Manzanares 3277 — Saavedra",
            "unit_id": "manz_2b",
            "unit_code": "2B",
            "rooms_label": "2 ambientes",
            "rooms_count": 2,
            "surface_total_m2": 58.0,
            "currency": "USD",
            "list_price": 145000,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        },
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "MANZANARES_3277",
            "project_name": "Manzanares 3277 — Saavedra",
            "unit_id": "manz_3a",
            "unit_code": "3A",
            "rooms_label": "3 ambientes",
            "rooms_count": 3,
            "surface_total_m2": 84.0,
            "currency": "USD",
            "list_price": 210000,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        },
    ]
    _patch_dialog_repo(monkeypatch, merged_units=merged_units)

    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-rooms-list",
        detail=_detail_for_project("MANZANARES_3277", "Manzanares 3277 — Saavedra"),
        question="Quiero todas las unidades de 2 ambientes",
        recent_messages=[],
        semantic_resolution=None,
    )

    answer = reply["answer"].lower()
    assert reply["variant"] == "project_units_by_rooms_list"
    assert "2a" in answer
    assert "2b" in answer
    assert "3a" not in answer
    assert "3 ambientes" not in answer


def test_en_todos_los_proyectos_applies_global_scope_to_previous_rooms_filter(monkeypatch) -> None:
    merged_units = [
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "BULNES_966_ALMAGRO",
            "project_name": "Bulnes 966 — Almagro",
            "unit_id": "bulnes_2a",
            "unit_code": "B-2A",
            "rooms_label": "2 ambientes",
            "rooms_count": 2,
            "surface_total_m2": 57.0,
            "currency": "USD",
            "list_price": 108000,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        },
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "GDR_3760_SAAVEDRA",
            "project_name": "GDR 3760 — Saavedra",
            "unit_id": "gdr_2b",
            "unit_code": "G-2B",
            "rooms_label": "2 ambientes",
            "rooms_count": 2,
            "surface_total_m2": 61.0,
            "currency": "USD",
            "list_price": 275700,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        },
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "MANZANARES_3277",
            "project_name": "Manzanares 3277 — Saavedra",
            "unit_id": "manz_2a",
            "unit_code": "M-2A",
            "rooms_label": "2 ambientes",
            "rooms_count": 2,
            "surface_total_m2": 56.0,
            "currency": "USD",
            "list_price": 130000,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        },
    ]
    _patch_dialog_repo(monkeypatch, merged_units=merged_units)
    detail = {
        "project_code": "MANZANARES_3277",
        "project_name": "Manzanares 3277 — Saavedra",
        "summary_jsonb": {
            "selected_project": {"code": "MANZANARES_3277", "name": "Manzanares 3277 — Saavedra"},
            "last_intent": "LIST_UNITS_BY_ROOMS",
            "last_rooms_query": {
                "rooms_count": 2,
                "rooms_label": "2 ambientes",
                "intent": "LIST_UNITS_BY_ROOMS",
                "search_scope": "project",
            },
        },
    }

    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-rooms-global-followup",
        detail=detail,
        question="En todos los proyectos",
        recent_messages=[],
        semantic_resolution=None,
    )

    answer = reply["answer"].lower()
    assert reply["variant"] == "global_units_by_rooms_list"
    assert "tomando todos los proyectos" in answer
    assert "bulnes 966" in answer
    assert "gdr 3760" in answer
    assert "manzanares 3277" in answer
    assert "sobre qué proyecto" not in answer


def test_en_todos_short_form_applies_global_scope_to_previous_filter(monkeypatch) -> None:
    merged_units = [
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "BULNES_966_ALMAGRO",
            "project_name": "Bulnes 966 — Almagro",
            "unit_id": "bulnes_2a",
            "unit_code": "B-2A",
            "rooms_label": "2 ambientes",
            "rooms_count": 2,
            "surface_total_m2": 57.0,
            "currency": "USD",
            "list_price": 108000,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        },
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "MANZANARES_3277",
            "project_name": "Manzanares 3277 — Saavedra",
            "unit_id": "manz_2a",
            "unit_code": "M-2A",
            "rooms_label": "2 ambientes",
            "rooms_count": 2,
            "surface_total_m2": 56.0,
            "currency": "USD",
            "list_price": 130000,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        },
    ]
    _patch_dialog_repo(monkeypatch, merged_units=merged_units)
    detail = {
        "project_code": "MANZANARES_3277",
        "project_name": "Manzanares 3277 — Saavedra",
        "summary_jsonb": {
            "selected_project": {"code": "MANZANARES_3277", "name": "Manzanares 3277 — Saavedra"},
            "last_intent": "COUNT_UNITS_BY_ROOMS",
            "last_rooms_query": {
                "rooms_count": 2,
                "rooms_label": "2 ambientes",
                "intent": "COUNT_UNITS_BY_ROOMS",
                "search_scope": "project",
            },
        },
    }

    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-rooms-global-short",
        detail=detail,
        question="En todos",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["variant"] == "global_units_by_rooms_count"
    assert "tomando todos los proyectos" in reply["answer"].lower()
    assert "2 unidades de 2 ambientes" in reply["answer"].lower()


def test_global_scope_override_does_not_trigger_choose_project(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    detail = {
        "project_code": "MANZANARES_3277",
        "project_name": "Manzanares 3277 — Saavedra",
        "summary_jsonb": {
            "selected_project": {"code": "MANZANARES_3277", "name": "Manzanares 3277 — Saavedra"},
            "last_intent": "LIST_UNITS_BY_ROOMS",
            "last_rooms_query": {
                "rooms_count": 2,
                "rooms_label": "2 ambientes",
                "intent": "LIST_UNITS_BY_ROOMS",
                "search_scope": "project",
            },
        },
    }

    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-rooms-no-choose-project",
        detail=detail,
        question="En todos los proyectos",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["variant"] != "choose_project_once"
    assert reply["variant"] != "project_handoff"
    assert "sobre qué proyecto" not in reply["answer"].lower()


def test_active_rooms_filter_projects_question_returns_matching_projects(monkeypatch) -> None:
    merged_units = [
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "BULNES_966_ALMAGRO",
            "project_name": "Bulnes 966 — Almagro",
            "unit_id": "bulnes_2a",
            "unit_code": "B-2A",
            "rooms_label": "2 ambientes",
            "rooms_count": 2,
            "surface_total_m2": 57.0,
            "currency": "USD",
            "list_price": 108000,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        },
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "MANZANARES_3277",
            "project_name": "Manzanares 3277 — Saavedra",
            "unit_id": "manz_2a",
            "unit_code": "M-2A",
            "rooms_label": "2 ambientes",
            "rooms_count": 2,
            "surface_total_m2": 56.0,
            "currency": "USD",
            "list_price": 130000,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        },
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "MANZANARES_3277",
            "project_name": "Manzanares 3277 — Saavedra",
            "unit_id": "manz_2b",
            "unit_code": "M-2B",
            "rooms_label": "2 ambientes",
            "rooms_count": 2,
            "surface_total_m2": 58.0,
            "currency": "USD",
            "list_price": 145000,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        },
    ]
    _patch_dialog_repo(monkeypatch, merged_units=merged_units)
    detail = {
        "summary_jsonb": {
            "last_search_scope": "global",
            "active_filter": {
                "type": "rooms",
                "payload": {"rooms_count": 2},
                "scope": "global",
                "origin_intent": "LIST_UNITS_BY_ROOMS",
                "summary": "unidades de 2 ambientes",
            },
        }
    }

    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-projects-active-rooms",
        detail=detail,
        question="cuáles son los proyectos",
        recent_messages=[],
        semantic_resolution=None,
    )

    answer = reply["answer"].lower()
    assert reply["variant"] == "projects_matching_active_filter"
    assert "unidades de 2 ambientes" in answer
    assert "bulnes 966" in answer
    assert "manzanares 3277" in answer
    assert "gdr 3760" not in answer


def test_en_cuales_uses_active_filter_context(monkeypatch) -> None:
    merged_units = [
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "BULNES_966_ALMAGRO",
            "project_name": "Bulnes 966 — Almagro",
            "unit_id": "bulnes_balcon",
            "unit_code": "B-7C",
            "rooms_label": "2 ambientes",
            "rooms_count": 2,
            "surface_total_m2": 59.2,
            "currency": "USD",
            "list_price": 148000,
            "availability_status": "available",
            "features_jsonb": ["balcon"],
            "_source_table": "demo_units",
        },
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "GDR_3760_SAAVEDRA",
            "project_name": "GDR 3760 — Saavedra",
            "unit_id": "gdr_balcon",
            "unit_code": "G-8A",
            "rooms_label": "3 ambientes",
            "rooms_count": 3,
            "surface_total_m2": 88.0,
            "currency": "USD",
            "list_price": 310000,
            "availability_status": "available",
            "features_jsonb": ["balcon", "parrilla"],
            "_source_table": "demo_units",
        },
    ]
    _patch_dialog_repo(monkeypatch, merged_units=merged_units)
    detail = {
        "summary_jsonb": {
            "last_search_scope": "global",
            "active_filter": {
                "type": "feature",
                "payload": {"feature_key": "balcon"},
                "scope": "global",
                "origin_intent": "GLOBAL_UNIT_SEARCH_BY_FEATURE",
                "summary": "unidades con balcón",
            },
        }
    }

    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-projects-active-feature",
        detail=detail,
        question="en cuáles",
        recent_messages=[],
        semantic_resolution=None,
    )

    answer = reply["answer"].lower()
    assert reply["variant"] == "projects_matching_active_filter"
    assert "bulnes 966" in answer
    assert "gdr 3760" in answer
    assert "balcón" in reply["answer"].lower() or "balcon" in answer


def test_projects_question_without_active_filter_returns_general_list(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-projects-general",
        detail={"summary_jsonb": {}},
        question="cuáles son los proyectos",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["variant"] == "project_catalog"
    assert "hoy tengo estos proyectos" in reply["answer"].lower()


def test_projects_question_with_global_scope_override_does_not_trigger_choose_project(monkeypatch) -> None:
    merged_units = [
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "BULNES_966_ALMAGRO",
            "project_name": "Bulnes 966 — Almagro",
            "unit_id": "bulnes_2a",
            "unit_code": "B-2A",
            "rooms_label": "2 ambientes",
            "rooms_count": 2,
            "surface_total_m2": 57.0,
            "currency": "USD",
            "list_price": 108000,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        }
    ]
    _patch_dialog_repo(monkeypatch, merged_units=merged_units)
    detail = {
        "summary_jsonb": {
            "selected_project": {"code": "MANZANARES_3277", "name": "Manzanares 3277 — Saavedra"},
            "active_filter": {
                "type": "rooms",
                "payload": {"rooms_count": 2},
                "scope": "global",
                "origin_intent": "COUNT_UNITS_BY_ROOMS",
                "summary": "unidades de 2 ambientes",
            },
            "last_search_scope": "global",
        }
    }

    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-projects-global-no-choose",
        detail=detail,
        question="cuáles son los proyectos",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["variant"] == "projects_matching_active_filter"
    assert "sobre qué proyecto" not in reply["answer"].lower()


def test_active_filter_context_persists_across_rooms_count_flow(monkeypatch) -> None:
    merged_units = [
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "BULNES_966_ALMAGRO",
            "project_name": "Bulnes 966 — Almagro",
            "unit_id": "bulnes_2a",
            "unit_code": "B-2A",
            "rooms_label": "2 ambientes",
            "rooms_count": 2,
            "surface_total_m2": 57.0,
            "currency": "USD",
            "list_price": 108000,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        },
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "MANZANARES_3277",
            "project_name": "Manzanares 3277 — Saavedra",
            "unit_id": "manz_2a",
            "unit_code": "M-2A",
            "rooms_label": "2 ambientes",
            "rooms_count": 2,
            "surface_total_m2": 56.0,
            "currency": "USD",
            "list_price": 130000,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        },
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "MANZANARES_3277",
            "project_name": "Manzanares 3277 — Saavedra",
            "unit_id": "manz_2b",
            "unit_code": "M-2B",
            "rooms_label": "2 ambientes",
            "rooms_count": 2,
            "surface_total_m2": 58.0,
            "currency": "USD",
            "list_price": 145000,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        },
    ]
    _patch_dialog_repo(monkeypatch, merged_units=merged_units)

    first = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-active-filter-step-1",
        detail=_detail_for_project("MANZANARES_3277", "Manzanares 3277 — Saavedra"),
        question="Cantidad de unidades 2 ambientes",
        recent_messages=[],
        semantic_resolution=None,
    )
    summary_after_first = first["summary_patch"]
    assert (summary_after_first.get("active_filter") or {}).get("type") == "rooms"
    assert ((summary_after_first.get("active_filter") or {}).get("payload") or {}).get("rooms_count") == 2

    second = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-active-filter-step-2",
        detail={"summary_jsonb": summary_after_first | {"selected_project": {"code": "MANZANARES_3277", "name": "Manzanares 3277 — Saavedra"}}},
        question="En todos los proyectos",
        recent_messages=[],
        semantic_resolution=None,
    )
    summary_after_second = second["summary_patch"]
    assert ((summary_after_second.get("active_filter") or {}).get("scope")) == "global"

    third = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-active-filter-step-3",
        detail={"summary_jsonb": summary_after_second},
        question="cuáles son los proyectos",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert third["variant"] == "projects_matching_active_filter"
    assert "bulnes 966" in third["answer"].lower()
    assert "manzanares 3277" in third["answer"].lower()


def test_active_result_set_can_be_filtered_by_balcony(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    detail = {
        "summary_jsonb": {
            "last_search_scope": "global",
            "active_filter": {
                "type": "rooms",
                "payload": {"rooms_count": 2},
                "scope": "global",
                "origin_intent": "LIST_UNITS_BY_ROOMS",
                "summary": "unidades de 2 ambientes",
            },
            "last_result_units": [
                {"project_code": "BULNES_966_ALMAGRO", "project_name": "Bulnes 966 — Almagro", "unit_id": "bulnes_7c", "unit_code": "A-7C", "rooms_label": "2 ambientes", "rooms_count": 2, "surface_total_m2": 59.2, "list_price": 148000, "currency": "USD", "availability_status": "available", "features_jsonb": ["balcon"], "balcony_protection": "unknown"},
                {"project_code": "MANZANARES_3277", "project_name": "Manzanares 3277 — Saavedra", "unit_id": "manz_2a", "unit_code": "M-2A", "rooms_label": "2 ambientes", "rooms_count": 2, "surface_total_m2": 56.0, "list_price": 130000, "currency": "USD", "availability_status": "available", "features_jsonb": []},
            ],
        }
    }

    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-result-set-balcony",
        detail=detail,
        question="de estos departamentos cuáles tiene balcón",
        recent_messages=[],
        semantic_resolution=None,
    )

    answer = reply["answer"].lower()
    assert reply["variant"] == "active_set_feature_filter"
    assert "a-7c" in answer
    assert "m-2a" not in answer


def test_active_result_set_can_be_filtered_by_generic_feature(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    detail = {
        "summary_jsonb": {
            "last_result_units": [
                {"project_code": "BULNES_966_ALMAGRO", "project_name": "Bulnes 966 — Almagro", "unit_id": "bulnes_2b", "unit_code": "B-2B", "rooms_label": "2 ambientes", "rooms_count": 2, "surface_total_m2": 57.1, "list_price": 108000, "currency": "USD", "availability_status": "available", "features_jsonb": ["cochera"]},
                {"project_code": "GDR_3760_SAAVEDRA", "project_name": "GDR 3760 — Saavedra", "unit_id": "gdr_8a", "unit_code": "G-8A", "rooms_label": "3 ambientes", "rooms_count": 3, "surface_total_m2": 88.0, "list_price": 310000, "currency": "USD", "availability_status": "available", "features_jsonb": ["parrilla"]},
                {"project_code": "MANZANARES_3277", "project_name": "Manzanares 3277 — Saavedra", "unit_id": "manz_j", "unit_code": "M-J1", "rooms_label": "2 ambientes", "rooms_count": 2, "surface_total_m2": 60.0, "list_price": 170000, "currency": "USD", "availability_status": "available", "features_jsonb": ["jacuzzi"]},
            ],
        }
    }

    cochera = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-result-set-cochera",
        detail=detail,
        question="de esos cuáles tienen cochera",
        recent_messages=[],
        semantic_resolution=None,
    )
    parrilla = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-result-set-parrilla",
        detail=detail,
        question="y con parrilla?",
        recent_messages=[],
        semantic_resolution=None,
    )
    jacuzzi = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-result-set-jacuzzi",
        detail=detail,
        question="de estas unidades cuál tiene jacuzzi?",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert "b-2b" in cochera["answer"].lower()
    assert "g-8a" in parrilla["answer"].lower()
    assert "m-j1" in jacuzzi["answer"].lower()


def test_de_estos_departamentos_prefers_result_set_not_last_unit(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    detail = {
        "summary_jsonb": {
            "last_subject_type": "unit",
            "last_subject_project_code": "GDR_3760_SAAVEDRA",
            "last_subject_project_name": "GDR 3760 — Saavedra",
            "last_subject_unit_id": "gdr_9z",
            "last_subject_unit_code": "9Z",
            "last_subject_summary": "9Z en GDR 3760 — Saavedra",
            "last_result_units": [
                {"project_code": "BULNES_966_ALMAGRO", "project_name": "Bulnes 966 — Almagro", "unit_id": "bulnes_7c", "unit_code": "A-7C", "rooms_label": "2 ambientes", "rooms_count": 2, "surface_total_m2": 59.2, "list_price": 148000, "currency": "USD", "availability_status": "available", "features_jsonb": ["balcon"], "balcony_protection": "unknown"},
                {"project_code": "MANZANARES_3277", "project_name": "Manzanares 3277 — Saavedra", "unit_id": "manz_2a", "unit_code": "M-2A", "rooms_label": "2 ambientes", "rooms_count": 2, "surface_total_m2": 56.0, "list_price": 130000, "currency": "USD", "availability_status": "available", "features_jsonb": []},
            ],
        }
    }

    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-result-set-vs-last-unit",
        detail=detail,
        question="de estos departamentos cuáles tiene balcón",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["variant"] == "active_set_feature_filter"
    assert "9z" not in reply["answer"].lower()
    assert "a-7c" in reply["answer"].lower()


def test_largest_with_feature_uses_filtered_subset(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    detail = {
        "summary_jsonb": {
            "last_search_scope": "global",
            "active_filter": {
                "type": "rooms",
                "payload": {"rooms_count": 2},
                "scope": "global",
                "origin_intent": "LIST_UNITS_BY_ROOMS",
                "summary": "unidades de 2 ambientes",
            },
            "last_result_units": [
                {"project_code": "BULNES_966_ALMAGRO", "project_name": "Bulnes 966 — Almagro", "unit_id": "bulnes_7c", "unit_code": "A-7C", "rooms_label": "2 ambientes", "rooms_count": 2, "surface_total_m2": 59.2, "list_price": 148000, "currency": "USD", "availability_status": "available", "features_jsonb": ["balcon"], "balcony_protection": "unknown"},
                {"project_code": "MANZANARES_3277", "project_name": "Manzanares 3277 — Saavedra", "unit_id": "manz_9a", "unit_code": "M-9A", "rooms_label": "2 ambientes", "rooms_count": 2, "surface_total_m2": 71.0, "list_price": 199000, "currency": "USD", "availability_status": "available", "features_jsonb": []},
                {"project_code": "MANZANARES_3277", "project_name": "Manzanares 3277 — Saavedra", "unit_id": "manz_8b", "unit_code": "M-8B", "rooms_label": "2 ambientes", "rooms_count": 2, "surface_total_m2": 63.0, "list_price": 185000, "currency": "USD", "availability_status": "available", "features_jsonb": ["balcon"], "balcony_protection": "unknown"},
            ],
        }
    }

    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-result-set-extreme-feature",
        detail=detail,
        question="dame el departamento más grande con balcón, su precio y proyecto",
        recent_messages=[],
        semantic_resolution=None,
    )

    answer = reply["answer"].lower()
    assert reply["variant"] == "active_set_feature_extreme"
    assert "m-8b" in answer
    assert "m-9a" not in answer


def test_feature_filter_then_projects_question_uses_enriched_active_filter(monkeypatch) -> None:
    merged_units = [
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "BULNES_966_ALMAGRO",
            "project_name": "Bulnes 966 — Almagro",
            "unit_id": "bulnes_7c",
            "unit_code": "A-7C",
            "rooms_label": "2 ambientes",
            "rooms_count": 2,
            "surface_total_m2": 59.2,
            "currency": "USD",
            "list_price": 148000,
            "availability_status": "available",
            "features_jsonb": ["balcon"],
            "balcony_protection": "unknown",
            "_source_table": "demo_units",
        },
        {
            "workspace_id": "ws_demo_vertice360",
            "project_code": "MANZANARES_3277",
            "project_name": "Manzanares 3277 — Saavedra",
            "unit_id": "manz_2a",
            "unit_code": "M-2A",
            "rooms_label": "2 ambientes",
            "rooms_count": 2,
            "surface_total_m2": 56.0,
            "currency": "USD",
            "list_price": 130000,
            "availability_status": "available",
            "features_jsonb": [],
            "_source_table": "demo_units",
        },
    ]
    _patch_dialog_repo(monkeypatch, merged_units=merged_units)
    detail = {
        "summary_jsonb": {
            "last_search_scope": "global",
            "active_filter": {
                "type": "rooms",
                "payload": {"rooms_count": 2},
                "scope": "global",
                "origin_intent": "LIST_UNITS_BY_ROOMS",
                "summary": "unidades de 2 ambientes",
            },
        }
    }

    first = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-enriched-filter-step-1",
        detail=detail,
        question="de estos departamentos cuáles tiene balcón",
        recent_messages=[],
        semantic_resolution=None,
    )
    second = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-enriched-filter-step-2",
        detail={"summary_jsonb": first["summary_patch"]},
        question="cuáles son los proyectos",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert second["variant"] == "projects_matching_active_filter"
    assert "bulnes 966" in second["answer"].lower()
    assert "manzanares 3277" not in second["answer"].lower()


def test_generic_features_like_garage_bbq_jacuzzi_are_supported_when_data_exists(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    detail = {
        "summary_jsonb": {
            "last_result_units": [
                {"project_code": "BULNES_966_ALMAGRO", "project_name": "Bulnes 966 — Almagro", "unit_id": "bulnes_2b", "unit_code": "B-2B", "rooms_label": "2 ambientes", "rooms_count": 2, "surface_total_m2": 57.1, "list_price": 108000, "currency": "USD", "availability_status": "available", "has_garage": True, "features_jsonb": []},
                {"project_code": "GDR_3760_SAAVEDRA", "project_name": "GDR 3760 — Saavedra", "unit_id": "gdr_8a", "unit_code": "G-8A", "rooms_label": "3 ambientes", "rooms_count": 3, "surface_total_m2": 88.0, "list_price": 310000, "currency": "USD", "availability_status": "available", "features_jsonb": ["parrilla"]},
                {"project_code": "MANZANARES_3277", "project_name": "Manzanares 3277 — Saavedra", "unit_id": "manz_j", "unit_code": "M-J1", "rooms_label": "2 ambientes", "rooms_count": 2, "surface_total_m2": 60.0, "list_price": 170000, "currency": "USD", "availability_status": "available", "features_jsonb": ["jacuzzi"]},
            ],
        }
    }

    garage = services._resolve_project_knowledge_reply(object(), ticket_id="ticket-generic-garage", detail=detail, question="de esos cuáles tienen cochera", recent_messages=[], semantic_resolution=None)
    bbq = services._resolve_project_knowledge_reply(object(), ticket_id="ticket-generic-bbq", detail=detail, question="y con parrilla?", recent_messages=[], semantic_resolution=None)
    jacuzzi = services._resolve_project_knowledge_reply(object(), ticket_id="ticket-generic-jacuzzi", detail=detail, question="de estas unidades cuál tiene jacuzzi?", recent_messages=[], semantic_resolution=None)

    assert "b-2b" in garage["answer"].lower()
    assert "g-8a" in bbq["answer"].lower()
    assert "m-j1" in jacuzzi["answer"].lower()


def test_honest_answer_when_feature_data_missing(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    detail = {
        "summary_jsonb": {
            "last_result_units": [
                {"project_code": "MANZANARES_3277", "project_name": "Manzanares 3277 — Saavedra", "unit_id": "manz_2a", "unit_code": "M-2A", "rooms_label": "2 ambientes", "rooms_count": 2, "surface_total_m2": 56.0, "list_price": 130000, "currency": "USD", "availability_status": "available", "features_jsonb": []},
                {"project_code": "MANZANARES_3277", "project_name": "Manzanares 3277 — Saavedra", "unit_id": "manz_2b", "unit_code": "M-2B", "rooms_label": "2 ambientes", "rooms_count": 2, "surface_total_m2": 58.0, "list_price": 145000, "currency": "USD", "availability_status": "available", "features_jsonb": []},
            ],
        }
    }

    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-feature-missing-data",
        detail=detail,
        question="y con jacuzzi?",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["variant"] == "active_set_feature_filter"
    assert "no tengo dato suficiente" in reply["answer"].lower()
    assert "sobre qué proyecto" not in reply["answer"].lower()


def _detail_for_active_balcony_result_set() -> dict[str, Any]:
    return {
        "summary_jsonb": {
            "last_result_units": [
                {"project_code": "BULNES_966_ALMAGRO", "project_name": "Bulnes 966 — Almagro", "unit_id": "bulnes_7c", "unit_code": "A-7C", "rooms_label": "2 ambientes", "rooms_count": 2, "surface_total_m2": 59.2, "list_price": 148000, "currency": "USD", "availability_status": "available", "features_jsonb": ["balcon"], "balcony_protection": "unknown"},
                {"project_code": "MANZANARES_3277", "project_name": "Manzanares 3277 — Saavedra", "unit_id": "manz_8b", "unit_code": "M-8B", "rooms_label": "2 ambientes", "rooms_count": 2, "surface_total_m2": 63.0, "list_price": 185000, "currency": "USD", "availability_status": "available", "features_jsonb": ["balcon"], "balcony_protection": "unknown"},
                {"project_code": "GDR_3760_SAAVEDRA", "project_name": "GDR 3760 — Saavedra", "unit_id": "gdr_2b", "unit_code": "2B", "rooms_label": "2 ambientes", "rooms_count": 2, "surface_total_m2": 113.0, "list_price": 275700, "currency": "USD", "availability_status": "available", "features_jsonb": ["balcon"], "balcony_protection": "unknown"},
                {"project_code": "GDR_3760_SAAVEDRA", "project_name": "GDR 3760 — Saavedra", "unit_id": "gdr_3b", "unit_code": "3B", "rooms_label": "3 ambientes", "rooms_count": 3, "surface_total_m2": 113.0, "list_price": 297600, "currency": "USD", "availability_status": "available", "features_jsonb": ["balcon"], "balcony_protection": "unknown"},
                {"project_code": "GDR_3760_SAAVEDRA", "project_name": "GDR 3760 — Saavedra", "unit_id": "gdr_4a", "unit_code": "4A", "rooms_label": "3 ambientes", "rooms_count": 3, "surface_total_m2": 137.0, "list_price": 326800, "currency": "USD", "availability_status": "available", "features_jsonb": ["balcon", "parrilla"], "balcony_protection": "unknown"},
            ],
            "active_filter": {
                "type": "feature",
                "payload": {"feature_key": "balcon"},
                "scope": "global",
                "origin_intent": "GLOBAL_UNIT_SEARCH_BY_FEATURE",
                "summary": "unidades con balcón",
            },
        }
    }


def test_top_n_largest_uses_active_result_set_with_existing_feature_filter(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-ranking-top-surface",
        detail=_detail_for_active_balcony_result_set(),
        question="me das los tres mas grandes en forma descendiente por mt cuadrado",
        recent_messages=[],
        semantic_resolution=None,
    )

    answer = reply["answer"].lower()
    assert reply["variant"] == "unit_list_followup"
    assert "unidades con balcón" in answer or "unidades con balcon" in answer
    assert "1. 4a" in answer
    assert "2. 2b" in answer
    assert "3. 3b" in answer


def test_top_n_preserves_active_facets_like_balcony(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-ranking-facets",
        detail=_detail_for_active_balcony_result_set(),
        question="los 3 mas grandes",
        recent_messages=[],
        semantic_resolution=None,
    )

    active_filter = reply["summary_patch"].get("active_filter") or {}
    assert reply["variant"] == "unit_list_followup"
    assert str(active_filter.get("summary") or "").lower().find("balc") >= 0


def test_top_n_descending_by_surface_returns_expected_units(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-ranking-desc-surface",
        detail=_detail_for_active_balcony_result_set(),
        question="top 3 mas grandes",
        recent_messages=[],
        semantic_resolution=None,
    )

    last_units = reply["summary_patch"].get("last_result_units") or []
    assert [row.get("unit_code") for row in last_units[:3]] == ["4A", "2B", "3B"]


def test_top_n_cheapest_uses_active_result_set(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-ranking-cheapest",
        detail=_detail_for_active_balcony_result_set(),
        question="los dos mas baratos",
        recent_messages=[],
        semantic_resolution=None,
    )

    answer = reply["answer"]
    assert reply["variant"] == "unit_list_followup"
    assert answer.index("A-7C") < answer.index("M-8B")


def test_top_n_updates_last_result_units(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-ranking-summary",
        detail=_detail_for_active_balcony_result_set(),
        question="los tres mas grandes",
        recent_messages=[],
        semantic_resolution=None,
    )

    last_units = reply["summary_patch"].get("last_result_units") or []
    assert len(last_units) == 3
    assert [row.get("unit_code") for row in last_units] == ["4A", "2B", "3B"]


def test_ranking_query_does_not_fallback_to_project_overview(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-ranking-no-project",
        detail=_detail_for_active_balcony_result_set(),
        question="me das los tres mas grandes en forma descendiente por mt cuadrado",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["variant"] == "unit_list_followup"
    assert "sobre qué proyecto" not in reply["answer"].lower()


def test_single_output_for_global_surface_query(monkeypatch) -> None:
    _patch_dialog_repo(monkeypatch)
    reply = services._resolve_project_knowledge_reply(
        object(),
        ticket_id="ticket-global-single",
        detail=_detail_for_project("BULNES_966_ALMAGRO", "Bulnes 966 — Almagro"),
        question="cualquiera con más de 50 m2",
        recent_messages=[],
        semantic_resolution=None,
    )

    assert reply["variant"] == "global_unit_filter_search"
    assert reply["answer"].count("?") <= 1


def test_total_units_and_available_units_are_distinct_intents() -> None:
    total_intent, total_followup, _ = services._detect_project_intent("cuantas unidades son", summary=None)
    available_intent, available_followup, _ = services._detect_project_intent("cuantas hay disponibles", summary=None)

    assert total_intent == "TOTAL_UNITS"
    assert total_followup is False
    assert available_intent == "AVAILABLE_UNITS"
    assert available_followup is False


def test_features_response_does_not_mix_location_as_amenity(monkeypatch) -> None:
    reply = _resolve(
        "caracteristicas",
        monkeypatch=monkeypatch,
        intent="FEATURES",
    )

    assert "Entre los amenities reales veo Saavedra" not in reply["answer"]


def test_features_response_does_not_mix_typology_as_amenity(monkeypatch) -> None:
    reply = _resolve(
        "caracteristicas",
        monkeypatch=monkeypatch,
        intent="FEATURES",
    )

    assert "Entre los amenities reales veo 2 y 3 ambientes" not in reply["answer"]


def test_features_response_does_not_duplicate_overview_terms_as_amenities(monkeypatch) -> None:
    reply = _resolve(
        "caracteristicas",
        monkeypatch=monkeypatch,
        intent="FEATURES",
    )
    answer = reply["answer"].lower()

    assert answer.count("seguridad") == 1
    assert answer.count("domotica") == 1
    assert "amenities reales" not in answer


def test_features_response_with_only_overview_does_not_force_amenities_list(monkeypatch) -> None:
    reply = _resolve(
        "caracteristicas",
        monkeypatch=monkeypatch,
        intent="FEATURES",
        marketing_assets=[],
        unit_types=[],
    )

    assert "Desarrollo de 2 y 3 ambientes" in reply["answer"]
    assert "amenities" not in reply["answer"].lower()


def test_features_response_single_output_no_fallback(monkeypatch) -> None:
    reply = _resolve(
        "caracteristicas",
        monkeypatch=monkeypatch,
        intent="FEATURES",
    )

    assert reply["variant"] == "project_qa"
    assert reply["found"] is True
    assert "prefiero confirm" not in reply["answer"].lower()
