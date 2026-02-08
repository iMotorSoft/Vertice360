from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any

_SEED = 14207


@dataclass(frozen=True, slots=True)
class Project:
    project_id: str
    name: str
    city: str
    neighborhood: str
    currency: str


@dataclass(frozen=True, slots=True)
class Unit:
    unit_code: str
    project_id: str
    rooms: int
    floor: int
    area_m2: int
    price: float
    currency: str
    status: str


_PROJECTS: tuple[Project, ...] = (
    Project(
        project_id="P-CAB-01",
        name="Parque Caballito",
        city="CABA",
        neighborhood="Caballito",
        currency="USD",
    ),
    Project(
        project_id="P-PAL-02",
        name="Nido Palermo",
        city="CABA",
        neighborhood="Palermo",
        currency="USD",
    ),
    Project(
        project_id="P-ALM-03",
        name="Luz Almagro",
        city="CABA",
        neighborhood="Almagro",
        currency="USD",
    ),
)

_UNITS: tuple[Unit, ...] = (
    Unit(
        unit_code="5A",
        project_id="P-CAB-01",
        rooms=3,
        floor=5,
        area_m2=78,
        price=185000,
        currency="USD",
        status="disponible",
    ),
    Unit(
        unit_code="8C",
        project_id="P-CAB-01",
        rooms=3,
        floor=8,
        area_m2=82,
        price=198000,
        currency="USD",
        status="reservada",
    ),
    Unit(
        unit_code="2B",
        project_id="P-CAB-01",
        rooms=2,
        floor=2,
        area_m2=55,
        price=135000,
        currency="USD",
        status="disponible",
    ),
    Unit(
        unit_code="1A",
        project_id="P-CAB-01",
        rooms=1,
        floor=1,
        area_m2=42,
        price=110000,
        currency="USD",
        status="disponible",
    ),
    Unit(
        unit_code="7B",
        project_id="P-PAL-02",
        rooms=3,
        floor=7,
        area_m2=90,
        price=240000,
        currency="USD",
        status="disponible",
    ),
    Unit(
        unit_code="3D",
        project_id="P-PAL-02",
        rooms=2,
        floor=3,
        area_m2=60,
        price=160000,
        currency="USD",
        status="vendida",
    ),
    Unit(
        unit_code="4A",
        project_id="P-ALM-03",
        rooms=3,
        floor=4,
        area_m2=75,
        price=175000,
        currency="USD",
        status="disponible",
    ),
    Unit(
        unit_code="9F",
        project_id="P-ALM-03",
        rooms=4,
        floor=9,
        area_m2=110,
        price=290000,
        currency="USD",
        status="disponible",
    ),
)

_PROJECTS_BY_ID: dict[str, Project] = {}
_UNIT_RANK: dict[str, int] = {}

_STATUS_SCORES: dict[str, float] = {
    "disponible": 2.0,
    "reservada": 1.0,
    "vendida": 0.0,
}


def reset_mock_data() -> None:
    global _PROJECTS_BY_ID
    global _UNIT_RANK

    _PROJECTS_BY_ID = {project.project_id: project for project in _PROJECTS}
    unit_codes = [unit.unit_code for unit in _UNITS]
    rng = random.Random(_SEED)
    rng.shuffle(unit_codes)
    _UNIT_RANK = {code: idx for idx, code in enumerate(unit_codes)}


def list_projects() -> list[dict[str, Any]]:
    return [_project_payload(project) for project in _PROJECTS]


def search_units(
    *,
    city: str | None = None,
    neighborhood: str | None = None,
    rooms: int | None = None,
    max_price: float | None = None,
    currency: str | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for unit in _UNITS:
        project = _PROJECTS_BY_ID.get(unit.project_id)
        if not project:
            continue
        if city and not _text_match(project.city, city):
            continue
        if neighborhood and not _text_match(project.neighborhood, neighborhood):
            continue
        if rooms is not None and unit.rooms != rooms:
            continue
        if currency and unit.currency.strip().upper() != currency.strip().upper():
            continue
        if max_price is not None and unit.price > max_price:
            continue
        results.append(_unit_payload(unit, project))
    return results


def get_recommended_options(filters: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    resolved = filters or {}
    city = resolved.get("city")
    neighborhood = resolved.get("neighborhood")
    rooms = resolved.get("rooms")
    max_price = resolved.get("max_price")
    currency = resolved.get("currency")

    candidates = search_units(
        city=city,
        neighborhood=neighborhood,
        rooms=rooms,
        max_price=max_price,
        currency=currency,
    )
    if len(candidates) < 2:
        candidates = [_unit_payload(unit, _PROJECTS_BY_ID[unit.project_id]) for unit in _UNITS]

    scored: list[tuple[float, dict[str, Any]]] = []
    for candidate in candidates:
        score = _score_unit(candidate, city, neighborhood, rooms, max_price, currency)
        scored.append((score, candidate))

    scored.sort(
        key=lambda item: (
            -item[0],
            item[1].get("price") or 0,
            _UNIT_RANK.get(item[1].get("unitCode", ""), 0),
        )
    )

    if len(scored) < 2:
        raise ValueError("not enough units to recommend")

    option_a = dict(scored[0][1])
    option_b = dict(scored[1][1])
    if option_a.get("unitCode") == option_b.get("unitCode") and len(scored) > 2:
        option_b = dict(scored[2][1])

    return {"optionA": option_a, "optionB": option_b}


def format_options_for_prompt(options: dict[str, Any]) -> str:
    option_a = options.get("optionA")
    option_b = options.get("optionB")

    parts: list[str] = []
    if isinstance(option_a, dict):
        parts.append(_format_option("A", option_a))
    if isinstance(option_b, dict):
        parts.append(_format_option("B", option_b))
    return " | ".join(parts)


def _project_payload(project: Project) -> dict[str, Any]:
    return {
        "projectId": project.project_id,
        "projectName": project.name,
        "city": project.city,
        "neighborhood": project.neighborhood,
        "currency": project.currency,
    }


def _unit_payload(unit: Unit, project: Project) -> dict[str, Any]:
    return {
        "unitCode": unit.unit_code,
        "projectId": project.project_id,
        "projectName": project.name,
        "city": project.city,
        "neighborhood": project.neighborhood,
        "rooms": unit.rooms,
        "floor": unit.floor,
        "areaM2": unit.area_m2,
        "price": unit.price,
        "currency": unit.currency,
        "status": unit.status,
    }


def _score_unit(
    unit: dict[str, Any],
    city: str | None,
    neighborhood: str | None,
    rooms: int | None,
    max_price: float | None,
    currency: str | None,
) -> float:
    score = _STATUS_SCORES.get(str(unit.get("status") or "").lower(), 0.0)

    if city:
        score += 3.0 if _text_match(str(unit.get("city") or ""), city) else -1.0
    if neighborhood:
        score += 4.0 if _text_match(str(unit.get("neighborhood") or ""), neighborhood) else -1.5
    if rooms is not None:
        score += 2.0 if unit.get("rooms") == rooms else -0.5
    if currency:
        score += 1.0 if _text_match(str(unit.get("currency") or ""), currency) else -1.0
    if max_price is not None:
        score += 1.5 if float(unit.get("price") or 0) <= max_price else -1.5

    return score


def _text_match(value: str, expected: str) -> bool:
    return value.strip().lower() == expected.strip().lower()


def _format_option(label: str, unit: dict[str, Any]) -> str:
    project_name = unit.get("projectName") or "-"
    neighborhood = unit.get("neighborhood") or "-"
    city = unit.get("city") or "-"
    unit_code = unit.get("unitCode") or "-"
    rooms = unit.get("rooms") or "-"
    area = unit.get("areaM2") or "-"
    currency = unit.get("currency") or "-"
    status = unit.get("status") or "-"
    price_raw = unit.get("price")
    price = _format_price(price_raw)

    return (
        f"{label}: {project_name} ({neighborhood}, {city}) {unit_code}, "
        f"{rooms} ambientes, {area} m2, {currency} {price}, {status}"
    )


def _format_price(price: Any) -> str:
    if price is None:
        return "-"
    try:
        return str(int(float(price)))
    except (TypeError, ValueError):
        return "-"


reset_mock_data()
