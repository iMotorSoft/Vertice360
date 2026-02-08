from __future__ import annotations

import asyncio

from backend import globalVar
from backend.modules.vertice360_ai_workflow_demo import services, store


def test_missing_slots_invariant(monkeypatch):
    monkeypatch.setattr(globalVar, "OpenAI_Key", "")
    store.reset_store()

    # No missing slots -> no recommended question and no ask_next_best_question
    result = asyncio.run(
        services.run_workflow(
            "vertice360-ai-workflow",
            "Hola",
        )
    )
    output = result.get("output") or {}
    assert output.get("missingSlotsCount") == 0
    assert output.get("decision") != "ask_next_best_question"
    assert not output.get("recommendedQuestion")

    # Missing slots -> must ask and include recommendedQuestion
    result = asyncio.run(
        services.run_workflow(
            "vertice360-ai-workflow",
            "busco depto",
        )
    )
    output = result.get("output") or {}
    assert (output.get("missingSlotsCount") or 0) > 0
    assert output.get("decision") == "ask_next_best_question"
    assert output.get("recommendedQuestion")
