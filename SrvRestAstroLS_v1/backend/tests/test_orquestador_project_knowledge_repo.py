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
