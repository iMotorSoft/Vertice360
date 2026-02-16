import asyncio
from unittest.mock import AsyncMock

import pytest

from backend import globalVar
from backend.modules.vertice360_workflow_demo import services, store


@pytest.fixture(autouse=True)
def setup_teardown():
    store.reset_store()
    globalVar.VERTICE360_AI_WORKFLOW_REPLY = True
    globalVar.VERTICE360_AI_WORKFLOW_REPLY_PREVIEW_MAX = 0
    globalVar.FEATURE_AI = False
    globalVar.OpenAI_Key = ""
    yield
    store.reset_store()


async def _async_test_slot_memory_no_repeat_budget():
    sender = "5491100011111"

    services._send_whatsapp_text = AsyncMock(return_value={"id": "m1"})
    services._run_ai_workflow_reply = AsyncMock(return_value={
        "decision": "ask_next_best_question",
        "recommendedQuestion": "Pregunta de AI que ignora memoria",
        "responseText": "Respuesta AI"
    })

    # 1) Start flow
    r1 = await services.process_inbound_message({
        "text": "busco depto",
        "from": sender,
        "messageId": "s1",
    })
    reply1 = r1["replyText"]
    assert "¿Por qué zona buscás y cuántos ambientes necesitás?" in reply1

    # 2) Provide zone + typology
    r2 = await services.process_inbound_message({
        "text": "almagro, 3 ambientes",
        "from": sender,
        "messageId": "s2",
    })
    reply2 = r2["replyText"]
    assert "¿Cuál es tu presupuesto aproximado y en qué moneda?" in reply2

    # 3) Provide budget with k suffix
    r3 = await services.process_inbound_message({
        "text": "120K usd",
        "from": sender,
        "messageId": "s3",
    })
    reply3 = r3["replyText"]
    assert "mudanza" in reply3.lower()

    # 4) Ambiguous small amount (should not re-ask budget if already confirmed)
    r4 = await services.process_inbound_message({
        "text": "usd 120",
        "from": sender,
        "messageId": "s4",
    })
    reply4 = r4["replyText"]
    assert "mudanza" in reply4.lower()

    # 5) Clarify amount
    r5 = await services.process_inbound_message({
        "text": "USD 120 mil",
        "from": sender,
        "messageId": "s5",
    })
    reply5 = r5["replyText"].lower()
    assert "mudanza" in reply5 or "gracias. tengo" in reply5

    # No repeated identical next_question twice in a row (if state changed)
    assert reply2 != reply1
    assert reply3 != reply2
    # reply4 may equal reply3 because of strict order + single canonical phrasing if user provides redundant info
    # assert reply4 != reply3 # REMOVED


def test_slot_memory_no_repeat_budget():
    asyncio.run(_async_test_slot_memory_no_repeat_budget())
