from __future__ import annotations

from typing import Any

from backend.modules.vertice360_orquestador_demo import repo


def _reset_repo_caches() -> None:
    repo._PROJECT_SCHEMA_CACHE = None  # type: ignore[attr-defined]
    repo._PROJECT_CAPABILITIES_CACHE = None  # type: ignore[attr-defined]


def test_get_project_capabilities_detects_enabled_features(monkeypatch) -> None:
    _reset_repo_caches()

    schema_map = {
        "projects": ["id", "code", "name", "description", "location_jsonb", "delivery_date", "status"],
        "marketing_assets": ["id", "project_id", "short_copy", "chips", "is_active"],
        "units": ["id", "project_id", "rooms", "price", "currency", "status"],
        "payment_plans": ["id", "project_id", "description"],
    }

    monkeypatch.setattr(repo, "discover_project_schema", lambda conn, force_refresh=False: schema_map)

    caps = repo.get_project_capabilities(object(), force_refresh=True)

    assert caps["project_overview"] is True
    assert caps["marketing_assets"] is True
    assert caps["prices_by_rooms"] is True
    assert caps["availability_by_rooms"] is True
    assert caps["financing"] is True
    assert caps["delivery_date"] is True


def test_get_prices_by_rooms_filters_rooms_and_currency(monkeypatch) -> None:
    _reset_repo_caches()

    schema_map = {
        "projects": ["id", "code", "name"],
        "units": ["id", "project_id", "rooms", "price", "currency", "status", "unit_code"],
    }
    monkeypatch.setattr(repo, "discover_project_schema", lambda conn, force_refresh=False: schema_map)

    captured: dict[str, Any] = {}

    def fake_fetch_all(conn, name: str, query: str, params=()):  # noqa: ANN001
        captured["name"] = name
        captured["query"] = query
        captured["params"] = params
        return [
            {
                "rooms": "2",
                "price": 125000,
                "currency": "USD",
                "status": "available",
                "unit_ref": "2A",
                "_source_table": "units",
            }
        ]

    monkeypatch.setattr(repo, "_fetch_all_knowledge", fake_fetch_all)

    rows = repo.get_prices_by_rooms(
        object(),
        "MANZANARES_3277",
        rooms=2,
        currency="USD",
    )

    assert rows
    assert captured["name"] == "get_prices_by_rooms"
    assert '"units"' in captured["query"]
    assert captured["params"] == ("MANZANARES_3277", "2", "USD")


def test_get_project_marketing_assets_uses_project_scope(monkeypatch) -> None:
    _reset_repo_caches()

    schema_map = {
        "projects": ["id", "code", "name"],
        "marketing_assets": ["id", "project_id", "title", "short_copy", "chips", "is_active", "sort_order"],
    }
    monkeypatch.setattr(repo, "discover_project_schema", lambda conn, force_refresh=False: schema_map)

    captured: dict[str, Any] = {}

    def fake_fetch_all(conn, name: str, query: str, params=()):  # noqa: ANN001
        captured["name"] = name
        captured["query"] = query
        captured["params"] = params
        return [
            {
                "title": "Proyecto",
                "short_copy": "Copy aprobado",
                "chips": ["Seguridad"],
                "_source_table": "marketing_assets",
            }
        ]

    monkeypatch.setattr(repo, "_fetch_all_knowledge", fake_fetch_all)

    rows = repo.get_project_marketing_assets(object(), "GDR_3760_SAAVEDRA")

    assert rows
    assert captured["name"] == "get_project_marketing_assets"
    assert '"marketing_assets"' in captured["query"]
    assert captured["params"] == ("GDR_3760_SAAVEDRA",)


def test_get_total_units_for_project_reads_bundle_nested_units_total(monkeypatch) -> None:
    _reset_repo_caches()

    schema_map = {
        "demo_project_facts": ["project_code", "description"],
        "demo_project_bundles": ["project_code", "bundle_jsonb"],
    }
    monkeypatch.setattr(repo, "discover_project_schema", lambda conn, force_refresh=False: schema_map)
    monkeypatch.setattr(repo, "get_demo_project_facts", lambda conn, project_code: {"project_code": project_code})
    monkeypatch.setattr(
        repo,
        "get_demo_project_bundle",
        lambda conn, project_code: {
            "project_code": project_code,
            "bundle_jsonb": {
                "building": {"structure": {"units_total": 46}},
            },
        },
    )

    total_units = repo.get_total_units_for_project(object(), "GDR_3760_SAAVEDRA")

    assert total_units == 46


def test_get_unit_status_breakdown_normalizes_demo_units_statuses(monkeypatch) -> None:
    monkeypatch.setattr(
        repo,
        "list_demo_units",
        lambda conn, project_code, rooms=None, currency=None: [
            {"availability_status": "available"},
            {"availability_status": "reservada"},
            {"availability_status": "ocupada"},
            {"availability_status": "no disponible"},
        ],
    )

    breakdown = repo.get_unit_status_breakdown(object(), "MANZANARES_3277")

    assert breakdown == {
        "available": 1,
        "reserved": 1,
        "unavailable": 2,
    }


def test_get_project_profile_reads_demo_project_profile(monkeypatch) -> None:
    _reset_repo_caches()

    schema_map = {
        "demo_project_profile": ["project_code", "units_total", "inventory_is_complete"],
    }
    monkeypatch.setattr(repo, "discover_project_schema", lambda conn, force_refresh=False: schema_map)

    captured: dict[str, Any] = {}

    def fake_fetch_one(conn, name: str, query: str, params=()):  # noqa: ANN001
        captured["name"] = name
        captured["query"] = query
        captured["params"] = params
        return {
            "project_code": "MANZANARES_3277",
            "units_total": 4,
            "inventory_is_complete": False,
        }

    monkeypatch.setattr(repo, "_fetch_one_knowledge", fake_fetch_one)

    class DummyConn:
        execute = None

    row = repo.get_project_profile(DummyConn(), "MANZANARES_3277")

    assert row is not None
    assert row["project_code"] == "MANZANARES_3277"
    assert row["_source_table"] == "demo_project_profile"
    assert captured["name"] == "get_project_profile"
    assert captured["params"] == ("MANZANARES_3277",)


def test_get_units_with_filters_uses_demo_unit_profile_flags(monkeypatch) -> None:
    monkeypatch.setattr(
        repo,
        "list_demo_units",
        lambda conn, project_code, rooms=None, currency=None: [
            {
                "workspace_id": "ws_demo_vertice360",
                "project_code": project_code,
                "unit_id": "manzanares_3277_p6_a",
                "unit_code": "6A",
                "rooms_count": 3,
                "features_jsonb": [],
                "_source_table": "demo_units",
            }
        ],
    )
    monkeypatch.setattr(
        repo,
        "get_unit_profiles_for_project",
        lambda conn, project_code: [
            {
                "workspace_id": "ws_demo_vertice360",
                "project_code": project_code,
                "unit_id": "manzanares_3277_p6_a",
                "has_garden": True,
                "recommended_profiles_jsonb": ["pets"],
                "_source_table": "demo_unit_profile",
            }
        ],
    )

    rows = repo.get_units_with_filters(
        object(),
        project_code="MANZANARES_3277",
        feature_key="jardin",
        has_garden=True,
    )

    assert len(rows) == 1
    assert rows[0]["unit_code"] == "6A"
    assert rows[0]["has_garden"] is True
    assert rows[0]["_profile_source_table"] == "demo_unit_profile"


def test_get_units_global_filtered_applies_surface_threshold(monkeypatch) -> None:
    monkeypatch.setattr(
        repo,
        "list_all_demo_units",
        lambda conn, rooms=None, currency=None: [
            {
                "workspace_id": "ws_demo_vertice360",
                "project_code": "BULNES_966_ALMAGRO",
                "project_name": "Bulnes 966 — Almagro",
                "unit_id": "bulnes-a7c",
                "unit_code": "A-7C",
                "rooms_count": 2,
                "surface_total_m2": 59.2,
                "availability_status": "available",
                "_source_table": "demo_units",
            },
            {
                "workspace_id": "ws_demo_vertice360",
                "project_code": "BULNES_966_ALMAGRO",
                "project_name": "Bulnes 966 — Almagro",
                "unit_id": "bulnes-1a",
                "unit_code": "B-1A",
                "rooms_count": 1,
                "surface_total_m2": 34.5,
                "availability_status": "available",
                "_source_table": "demo_units",
            },
        ],
    )
    monkeypatch.setattr(
        repo,
        "list_projects",
        lambda conn: [
            {"code": "BULNES_966_ALMAGRO", "name": "Bulnes 966 — Almagro"},
        ],
    )
    monkeypatch.setattr(repo, "get_unit_profiles_for_project", lambda conn, project_code: [])

    rows = repo.get_units_global_filtered(
        object(),
        min_surface_total_m2=50,
        availability="available",
    )

    assert len(rows) == 1
    assert rows[0]["unit_code"] == "A-7C"
