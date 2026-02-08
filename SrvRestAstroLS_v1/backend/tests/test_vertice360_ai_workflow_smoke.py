from __future__ import annotations

import asyncio

from backend.modules.vertice360_ai_workflow_demo import services, store


def test_multi_intent_price_location():
    store.reset_store()
    result = asyncio.run(
        services.run_workflow(
            "vertice360-ai-workflow",
            "Necesito precio y ubicacion. Email: test@mail.com",
        )
    )
    output = result.get("output") or {}

    assert result.get("mode") == "heuristic"
    assert output.get("primaryIntent") == "price"
    assert output.get("intent") == "price"
    assert "location" in (output.get("secondaryIntents") or [])
    assert output.get("decision") == "ask_next_best_question"
    pragmatics = output.get("pragmatics") or {}
    questions = pragmatics.get("recommendedQuestions") or []
    joined = " ".join(questions).lower()
    assert "zona" in joined or "proyecto" in joined
    assert "presupuesto" in joined and "moneda" in joined

    response = (output.get("responseText") or "").lower()
    assert "presupuesto" in response or "moneda" in response
