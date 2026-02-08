from __future__ import annotations

import asyncio

from backend import globalVar
from backend.modules.vertice360_ai_workflow_demo import services, store


def test_next_best_question_for_minimal_search(monkeypatch):
    monkeypatch.setattr(globalVar, "OpenAI_Key", "")
    store.reset_store()

    result = asyncio.run(
        services.run_workflow(
            "vertice360-ai-workflow",
            "busco depto",
        )
    )
    output = result.get("output") or {}
    question = output.get("recommendedQuestion") or output.get("responseText") or ""

    assert output.get("decision") == "ask_next_best_question"
    assert ("zona" in question.lower()) or ("ambientes" in question.lower())
    assert len(question) <= 140


def test_next_best_question_for_budget(monkeypatch):
    monkeypatch.setattr(globalVar, "OpenAI_Key", "")
    store.reset_store()

    result = asyncio.run(
        services.run_workflow(
            "vertice360-ai-workflow",
            "CABA Caballito 3 ambientes",
        )
    )
    output = result.get("output") or {}
    question = output.get("recommendedQuestion") or output.get("responseText") or ""

    assert output.get("decision") == "ask_next_best_question"
    assert "presupuesto" in question.lower()
    assert "moneda" in question.lower()
    assert len(question) <= 140
