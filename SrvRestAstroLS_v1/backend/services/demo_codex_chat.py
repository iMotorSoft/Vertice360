"""Servicio de chat demo para Vertice360 usando LainGraph (gpt-4o-mini)."""

from __future__ import annotations

from typing import Any

from openai import OpenAI

import globalVar
from db import demo_vertice360_data

# Prompt base para contextualizar al modelo con el mock de Vertice360.
SYSTEM_PROMPT = (
    "Eres LainGraph, asistente demo de Vertice360. "
    "Responde en español, breve y accionable. "
    "Usa solo los datos de la demo /api/demo/codex/*. Si no encuentras un dato, dilo."
)


def _format_demo_context() -> str:
    """Compacta los datos mock para dárselos al LLM."""
    projects = "\n".join(
        f"- {p['id_proyecto']}: {p['nombre']} ({p['ciudad']}, {p['estado']}), "
        f"precio USD {p['precio_desde']}–{p['precio_hasta']}"
        for p in demo_vertice360_data.proyectos_en_pozo
    )
    units = "\n".join(
        f"- {u['id_unidad']} ({u['id_proyecto']}): {u['ambiente']}, piso {u['piso']}, "
        f"{u['estado_unidad']}, USD {u['precio_lista']}"
        for u in demo_vertice360_data.unidades
    )
    investors = "\n".join(
        f"- {i['id_inversor']}: {i['nombre']} ({i['tipo_inversor']}, {i['pais']})"
        for i in demo_vertice360_data.inversores
    )
    operations = "\n".join(
        f"- {op['id_operacion']}: {op['tipo_operacion']} de {op['id_unidad']} "
        f"por {op['id_inversor']} el {op['fecha']} (USD {op['monto']})"
        for op in demo_vertice360_data.reservas_y_ventas
    )
    return (
        "Contexto demo Vertice360:\n"
        f"Proyectos:\n{projects}\n\n"
        f"Unidades:\n{units}\n\n"
        f"Inversores:\n{investors}\n\n"
        f"Operaciones:\n{operations}\n"
        "Siempre responde citando los IDs relevantes."
    )


def run_demo_chat(prompt: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """Ejecuta la llamada al LLM usando el modelo configurado (gpt-4o-mini)."""
    if not prompt or not prompt.strip():
        raise ValueError("El prompt no puede estar vacío.")

    api_key = globalVar.OpenAI_Key
    if not api_key:
        raise RuntimeError("Falta OpenAI API key (VERTICE360_OPENAI_KEY u OPENAI_API_KEY).")

    client = OpenAI(api_key=api_key)

    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": _format_demo_context()},
    ]

    for msg in history or []:
        role = msg.get("role") or "user"
        content = msg.get("content") or ""
        if content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": prompt})

    completion = client.chat.completions.create(
        model=globalVar.OpenAI_Model or "gpt-4o-mini",
        messages=messages,
        temperature=0.2,
    )

    choice = completion.choices[0].message
    usage_data: dict[str, Any] | None = None
    if completion.usage:
        usage_data = completion.usage.model_dump() if hasattr(completion.usage, "model_dump") else dict(completion.usage)

    return {
        "reply": choice.content or "",
        "model": completion.model,
        "created": completion.created,
        "usage": usage_data,
        "meta": {
            "prompt": prompt,
            "history_length": len(history or []),
            "source": "demo_codex_lain_graph",
        },
    }


__all__ = ["run_demo_chat"]
