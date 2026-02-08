from __future__ import annotations

import unicodedata
from typing import Any


def template_reply(context: dict[str, Any]) -> str:
    normalized = _strip_accents(str(context.get("normalizedInput") or "").lower())
    primary_intent = context.get("primaryIntent") or "general"
    decision = context.get("decision") or ""
    pragmatics = context.get("pragmatics") or {}
    speech_act = pragmatics.get("speechAct")
    missing_slots = pragmatics.get("missingSlots") or context.get("missingSlots") or {}
    options = context.get("options") or {}

    chosen = _detect_option_choice(normalized)
    if chosen:
        return _template_choose_option(chosen, options)

    if decision == "ask_docs" or primary_intent == "docs":
        return _template_docs_request()

    if decision == "book_visit" or primary_intent == "visit":
        return _template_book_visit()

    if primary_intent == "property_search" or decision == "property_search":
        if _has_options(options):
            return _template_property_search_with_options(options)
        return _template_property_search_missing(missing_slots)

    if speech_act == "greeting":
        return _template_greeting()

    return _template_general()


def _template_greeting() -> str:
    return (
        "Hola! Soy el asistente de Vertice360. "
        "Decime zona, ambientes y presupuesto para buscar opciones."
    )


def _template_general() -> str:
    return (
        "Puedo ayudarte con disponibilidad, precios, ubicacion y visitas. "
        "Contame zona, ambientes y presupuesto."
    )


def _template_property_search_missing(missing_slots: dict[str, Any]) -> str:
    missing = _render_missing_slots(missing_slots)
    if not missing:
        missing = "zona, ambientes, presupuesto y moneda"
    return f"Para avanzar necesito: {missing}."


def _template_property_search_with_options(options: dict[str, Any]) -> str:
    option_a = _format_option("A", options.get("optionA"))
    option_b = _format_option("B", options.get("optionB"))
    lines = [line for line in (option_a, option_b) if line]
    options_text = "\n".join(lines)
    return (
        f"Opciones sugeridas:\n{options_text}\n"
        "Si queres, coordinamos visita. Decime dia y horario."
    )


def _template_choose_option(choice: str, options: dict[str, Any]) -> str:
    key = "optionA" if choice == "A" else "optionB"
    option = options.get(key) if isinstance(options, dict) else None
    details = _format_option(choice, option) if isinstance(option, dict) else f"Opcion {choice}"
    return (
        f"Perfecto, tomo {details}. "
        "Si queres coordinamos visita. Decime dia y horario."
    )


def _template_book_visit() -> str:
    return "Para agendar la visita necesito dia y horario, y tu nombre + telefono o email."


def _template_docs_request() -> str:
    return "Para avanzar necesito DNI y comprobante de ingresos."


def _detect_option_choice(text: str) -> str | None:
    if "opcion a" in text or "opciona" in text:
        return "A"
    if "opcion b" in text or "opcionb" in text:
        return "B"
    if "opcion" in text and "b" in text:
        return "B"
    if "opcion" in text and "a" in text:
        return "A"
    return None


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _has_options(options: dict[str, Any]) -> bool:
    if not isinstance(options, dict):
        return False
    return isinstance(options.get("optionA"), dict) and isinstance(options.get("optionB"), dict)


def _format_option(label: str, unit: dict[str, Any] | None) -> str:
    if not isinstance(unit, dict):
        return ""
    unit_code = unit.get("unitCode") or "-"
    rooms = unit.get("rooms") or "-"
    area = unit.get("areaM2") or "-"
    price = _format_price(unit.get("price"))
    currency = unit.get("currency") or "-"
    neighborhood = unit.get("neighborhood") or "-"
    return (
        f"Opcion {label}: {unit_code}, {rooms} ambientes, {area} m2, "
        f"{currency} {price}, {neighborhood}"
    )


def _format_price(price: Any) -> str:
    if price is None:
        return "-"
    try:
        return str(int(float(price)))
    except (TypeError, ValueError):
        return "-"


def _render_missing_slots(missing_slots: dict[str, Any]) -> str:
    if not isinstance(missing_slots, dict):
        return ""
    labels = []
    for _, value in missing_slots.items():
        if isinstance(value, list) and value:
            labels.extend(str(item) for item in value)
    return ", ".join(_dedupe(labels))


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        cleaned = item.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        output.append(cleaned)
    return output
