from __future__ import annotations

import json
import logging
from typing import Any

from jsonschema import ValidationError, validate

from backend import globalVar

logger = logging.getLogger(__name__)


SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "slotUpdates": {
            "type": "object",
            "properties": {
                "zona": {"type": ["string", "null"]},
                "tipologia": {"type": ["string", "null"]},
                "presupuesto_amount": {"type": ["number", "null"]},
                "presupuesto_raw": {"type": ["string", "null"]},
                "moneda": {"type": ["string", "null"]},
                "fecha_mudanza": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        },
        "confirmed": {
            "type": "object",
            "properties": {
                "budget": {"type": "boolean"},
                "currency": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
        "ambiguities": {
            "type": "object",
            "properties": {
                "budget": {"type": "boolean"},
                "budget_amount": {"type": ["number", "null"]},
                "currency": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        },
        "next_action": {"type": "string"},
        "next_question": {"type": ["string", "null"]},
    },
    "required": [
        "slotUpdates",
        "confirmed",
        "ambiguities",
        "next_action",
        "next_question",
    ],
    "additionalProperties": False,
}


def _sanitize_question(text: str | None) -> str | None:
    if not text:
        return None
    normalized = " ".join(str(text).split())
    if not normalized:
        return None
    if len(normalized) > 140:
        normalized = normalized[:140].rstrip()
    if not normalized.endswith("?") and not normalized.startswith("¿"):
        normalized = f"¿{normalized}?" if len(normalized) < 138 else normalized
    return normalized


def _parse_json(content: str) -> dict[str, Any] | None:
    if not content:
        return None
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def reduce_state(
    previous_state: dict[str, Any],
    new_message_text: str,
    last_messages: list[str] | None = None,
) -> dict[str, Any] | None:
    if not globalVar.OpenAI_Key or not globalVar.FEATURE_AI:
        return None

    prompt_state = json.dumps(previous_state or {}, ensure_ascii=False)
    recent = last_messages or []
    recent_text = "\n".join(recent[-3:]) if recent else ""

    system_prompt = (
        "Sos un reductor de estado para un CRM inmobiliario. "
        "Devolvé SOLO JSON valido según el schema. "
        "No incluyas texto adicional. "
        "La pregunta debe estar en español, max 140 caracteres, "
        "y pedir como máximo 2 piezas de información."
    )

    user_prompt = (
        "Schema esperado (resumen):\n"
        "{"
        "slotUpdates:{zona, tipologia, presupuesto_amount, presupuesto_raw, moneda, fecha_mudanza},"
        "confirmed:{budget,currency},"
        "ambiguities:{budget,budget_amount,currency},"
        "next_action, next_question}.\n\n"
        f"Estado previo: {prompt_state}\n\n"
        f"Mensajes recientes: {recent_text or '-'}\n\n"
        f"Nuevo mensaje: {new_message_text}\n"
    )

    try:
        from openai import OpenAI

        client = OpenAI(api_key=globalVar.OpenAI_Key)
        response = client.chat.completions.create(
            model=globalVar.OpenAI_Model or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=300,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("llm_state_reducer_failed=%s", type(exc).__name__)
        return None

    if not response.choices:
        return None

    content = response.choices[0].message.content or ""
    payload = _parse_json(content)
    if payload is None:
        return None

    try:
        validate(payload, SCHEMA)
    except ValidationError:
        return None

    payload["next_question"] = _sanitize_question(payload.get("next_question"))
    return payload
