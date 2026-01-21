from backend.modules.vertice360_workflow_demo import services as svc


def test_ai_reply_enabled_uses_ai_text_truncated(monkeypatch) -> None:
    monkeypatch.setattr(svc.globalVar, "VERTICE360_AI_WORKFLOW_REPLY", True)
    monkeypatch.setattr(svc.globalVar, "VERTICE360_AI_WORKFLOW_REPLY_PREVIEW_MAX", 10)
    ai_text = "abcdefghijklmnop"
    fallback = "fallback"

    result = svc._pick_whatsapp_reply_text(ai_text, fallback)

    assert result == "abcdefghi\u2026"


def test_ai_reply_enabled_empty_ai_uses_fallback(monkeypatch) -> None:
    monkeypatch.setattr(svc.globalVar, "VERTICE360_AI_WORKFLOW_REPLY", True)
    monkeypatch.setattr(svc.globalVar, "VERTICE360_AI_WORKFLOW_REPLY_PREVIEW_MAX", 10)

    result = svc._pick_whatsapp_reply_text("   ", "fallback")

    assert result == "fallback"


def test_ai_reply_disabled_uses_fallback(monkeypatch) -> None:
    monkeypatch.setattr(svc.globalVar, "VERTICE360_AI_WORKFLOW_REPLY", False)
    monkeypatch.setattr(svc.globalVar, "VERTICE360_AI_WORKFLOW_REPLY_PREVIEW_MAX", 10)

    result = svc._pick_whatsapp_reply_text("hello", "fallback")

    assert result == "fallback"
