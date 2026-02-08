from __future__ import annotations

from backend import globalVar
from backend.modules.vertice360_ai_workflow_demo import llm_service, mock_data


def test_fallback_when_openai_key_missing(monkeypatch):
    monkeypatch.setattr(globalVar, "OpenAI_Key", "")
    options = mock_data.get_recommended_options(
        {"city": "CABA", "neighborhood": "Caballito", "rooms": 3}
    )

    result = llm_service.generate_human_reply(
        user_text="Quiero 3 ambientes en Caballito.",
        nlu={"intent": "search"},
        options=options,
        missing_slots={},
        max_chars=240,
    )

    assert result["usedFallback"] is True


def test_template_fallback_text_not_empty(monkeypatch):
    monkeypatch.setattr(globalVar, "OpenAI_Key", "")
    result = llm_service.generate_human_reply(
        user_text="Busco algo en CABA.",
        nlu={"intent": "search"},
        options=None,
        missing_slots={"budget": ["max_price", "currency"]},
        max_chars=200,
    )

    assert result["responseText"]
