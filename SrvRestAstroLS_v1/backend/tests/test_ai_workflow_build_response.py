from __future__ import annotations

import asyncio

from backend import globalVar
from backend.modules.vertice360_ai_workflow_demo import services, store


def test_build_response_asks_budget_when_missing(monkeypatch):
    monkeypatch.setattr(globalVar, "OpenAI_Key", "")
    store.reset_store()

    result = asyncio.run(
        services.run_workflow(
            "vertice360-ai-workflow",
            "CABA Caballito depto 3 ambientes",
        )
    )
    output = result.get("output") or {}
    response = output.get("responseText") or ""
    question = output.get("recommendedQuestion") or ""

    assert output.get("decision") == "ask_next_best_question"
    assert output.get("usedFallback") is True
    assert "presupuesto" in response.lower() or "presupuesto" in question.lower()
    assert "moneda" in response.lower() or "moneda" in question.lower()
    assert len(response) <= 140


def test_build_response_fallback_when_openai_key_missing(monkeypatch):
    monkeypatch.setattr(globalVar, "OpenAI_Key", "")
    store.reset_store()

    result = asyncio.run(
        services.run_workflow(
            "vertice360-ai-workflow",
            "Hola",
        )
    )
    output = result.get("output") or {}

    assert output.get("usedFallback") is True
