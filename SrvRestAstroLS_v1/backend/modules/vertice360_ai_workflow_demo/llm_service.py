from __future__ import annotations

import json
import re
from typing import Any

from backend import globalVar
from backend.modules.vertice360_ai_workflow_demo import llm_prompts

_UNIT_CODE_PATTERN = re.compile(r"\b\d{1,2}[A-Z]\b")


def generate_human_reply(
    *,
    user_text: str,
    nlu: dict[str, Any],
    options: dict[str, Any] | None,
    missing_slots: dict[str, Any],
    max_chars: int,
) -> dict[str, Any]:
    resolved_max = _resolve_max_chars(max_chars)
    allowed_codes = _extract_option_codes(options)

    if not globalVar.OpenAI_Key:
        return _fallback(
            reason="missing_openai_key",
            options=options,
            missing_slots=missing_slots,
            max_chars=resolved_max,
        )

    model = globalVar.OpenAI_Model or "gpt-4o-mini"
    try:
        response_text = _call_openai(
            user_text=user_text,
            nlu=nlu,
            options=options,
            missing_slots=missing_slots,
            model=model,
            max_chars=resolved_max,
        )
    except Exception:
        return _fallback(
            reason="openai_error",
            options=options,
            missing_slots=missing_slots,
            max_chars=resolved_max,
        )

    response_text = _normalize_text(response_text)
    response_text = _truncate(response_text, resolved_max)
    if not response_text:
        return _fallback(
            reason="empty_response",
            options=options,
            missing_slots=missing_slots,
            max_chars=resolved_max,
        )

    if _mentions_unknown_unit_code(response_text, allowed_codes):
        return _fallback(
            reason="unknown_unit_code",
            options=options,
            missing_slots=missing_slots,
            max_chars=resolved_max,
        )

    return {
        "responseText": response_text,
        "usedFallback": False,
        "fallbackReason": None,
        "model": model,
    }


def _call_openai(
    *,
    user_text: str,
    nlu: dict[str, Any],
    options: dict[str, Any] | None,
    missing_slots: dict[str, Any],
    model: str,
    max_chars: int,
) -> str:
    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover - depends on installed lib
        raise RuntimeError("openai_not_available") from exc

    client = OpenAI(api_key=globalVar.OpenAI_Key)
    messages = [
        {"role": "system", "content": llm_prompts.system_prompt},
        {
            "role": "user",
            "content": _build_user_prompt(
                user_text=user_text,
                nlu=nlu,
                options=options,
                missing_slots=missing_slots,
            ),
        },
    ]
    max_tokens = max(64, int(max_chars / 4))
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.4,
        max_tokens=max_tokens,
    )
    if not response.choices:
        return ""
    content = response.choices[0].message.content
    return content or ""


def _build_user_prompt(
    *,
    user_text: str,
    nlu: dict[str, Any],
    options: dict[str, Any] | None,
    missing_slots: dict[str, Any],
) -> str:
    payload = {
        "user_text": user_text,
        "nlu": nlu,
        "missing_slots": missing_slots,
        "options": options or {},
    }
    return json.dumps(payload, ensure_ascii=True)


def _fallback(
    *,
    reason: str,
    options: dict[str, Any] | None,
    missing_slots: dict[str, Any],
    max_chars: int,
) -> dict[str, Any]:
    response_text = _build_fallback_response(options, missing_slots)
    response_text = _normalize_text(response_text)
    response_text = _truncate(response_text, max_chars)
    if not response_text:
        response_text = "Para seguir necesito un dato adicional."
    return {
        "responseText": response_text,
        "usedFallback": True,
        "fallbackReason": reason,
        "model": None,
    }


def _build_fallback_response(
    options: dict[str, Any] | None,
    missing_slots: dict[str, Any],
) -> str:
    pieces: list[str] = []
    options_text = _format_options_for_prompt(options)
    if options_text:
        pieces.append(f"Opciones: {options_text}.")

    missing_list = _flatten_missing_slots(missing_slots)
    if missing_list:
        missing_text = ", ".join(missing_list)
        pieces.append(f"Para avanzar necesito: {missing_text}.")
    else:
        pieces.append("Decime si alguna opcion te interesa o tu presupuesto.")

    return " ".join(pieces).strip()


def _format_options_for_prompt(options: dict[str, Any] | None) -> str:
    if not options or not isinstance(options, dict):
        return ""
    option_a = options.get("optionA")
    option_b = options.get("optionB")
    parts: list[str] = []
    if isinstance(option_a, dict):
        parts.append(_format_option("A", option_a))
    if isinstance(option_b, dict):
        parts.append(_format_option("B", option_b))
    return " | ".join([part for part in parts if part])


def _format_option(label: str, unit: dict[str, Any]) -> str:
    unit_code = unit.get("unitCode") or "-"
    rooms = unit.get("rooms") or "-"
    area = unit.get("areaM2") or "-"
    price = _format_price(unit.get("price"))
    currency = unit.get("currency") or "-"
    neighborhood = unit.get("neighborhood") or "-"
    return (
        f"{label} {unit_code}, {rooms} ambientes, {area} m2, "
        f"{currency} {price}, {neighborhood}"
    )


def _format_price(price: Any) -> str:
    if price is None:
        return "-"
    try:
        return str(int(float(price)))
    except (TypeError, ValueError):
        return "-"


def _flatten_missing_slots(missing_slots: dict[str, Any]) -> list[str]:
    items: list[str] = []
    if not isinstance(missing_slots, dict):
        return items
    for key, value in missing_slots.items():
        if isinstance(value, list) and value:
            items.extend(str(item) for item in value)
        else:
            items.append(str(key))
    return _dedupe(items)


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


def _resolve_max_chars(max_chars: int) -> int:
    if isinstance(max_chars, int) and max_chars > 0:
        return max_chars
    return 240


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip()


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _extract_option_codes(options: dict[str, Any] | None) -> set[str]:
    codes: set[str] = set()
    if not options or not isinstance(options, dict):
        return codes
    for key in ("optionA", "optionB"):
        candidate = options.get(key)
        if isinstance(candidate, dict):
            code = candidate.get("unitCode")
            if code:
                codes.add(str(code))
    return codes


def _mentions_unknown_unit_code(text: str, allowed_codes: set[str]) -> bool:
    matches = set(_UNIT_CODE_PATTERN.findall(text))
    if not matches:
        return False
    if not allowed_codes:
        return True
    return any(code not in allowed_codes for code in matches)
