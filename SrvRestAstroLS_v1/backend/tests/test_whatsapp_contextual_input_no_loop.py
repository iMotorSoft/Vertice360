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


async def _async_test_contextual_input_no_loop():
    captured_inputs = []

    async def _fake_ai_run(text, message_id, ticket_id, context=None):
        captured_inputs.append(text)
        return {
            "decision": "ask_next_best_question",
            "recommendedQuestion": "Pregunta AI",
            "responseText": "Respuesta AI",
        }

    services._run_ai_workflow_reply = AsyncMock(side_effect=_fake_ai_run)
    services._send_whatsapp_text = AsyncMock(return_value={"id": "m"})

    sender = "5491100022222"

    # 1) Start flow
    r1 = await services.process_inbound_message({
        "text": "quiero un depto",
        "from": sender,
        "messageId": "c1",
    })
    reply1 = r1["replyText"]
    assert "¿Por qué zona buscás y cuántos ambientes necesitás?" in reply1

    # 2) Provide zone + typology
    r2 = await services.process_inbound_message({
        "text": "palermo, 2 ambientes",
        "from": sender,
        "messageId": "c2",
    })
    reply2 = r2["replyText"]
    assert "¿Cuál es tu presupuesto aproximado y en qué moneda?" in reply2

    # 3) Provide budget
    r3 = await services.process_inbound_message({
        "text": "90k usd",
        "from": sender,
        "messageId": "c3",
    })
    reply3 = r3["replyText"]
    assert "mudanza" in reply3.lower()

    # 4) Repeat budget in another format -> same question is allowed now
    r4 = await services.process_inbound_message({
        "text": "90000 dolares",
        "from": sender,
        "messageId": "c4",
    })
    reply4 = r4["replyText"]
    assert "mudanza" in reply4.lower()
    # reply4 may equal reply3 because of strict order + single canonical phrasing

    # Ensure contextual input is used
    assert captured_inputs
    assert "Mensaje usuario: quiero un depto" in captured_inputs[0]

    # Ambiguity confirmation scenario (new ticket)
    sender2 = "5491100033333"
    r1b = await services.process_inbound_message({
        "text": "quiero un depto",
        "from": sender2,
        "messageId": "d1",
    })
    reply1b = r1b["replyText"]
    assert "¿Por qué zona buscás y cuántos ambientes necesitás?" in reply1b

    r2b = await services.process_inbound_message({
        "text": "palermo, 2 ambientes",
        "from": sender2,
        "messageId": "d2",
    })
    reply2b = r2b["replyText"]
    assert "¿Cuál es tu presupuesto aproximado y en qué moneda?" in reply2b

    r3b = await services.process_inbound_message({
        "text": "usd 120",
        "from": sender2,
        "messageId": "d3",
    })
    reply3b = r3b["replyText"]
    assert "¿confirmás si es usd 120 o usd 120 mil" in reply3b.lower()

    r4b = await services.process_inbound_message({
        "text": "si",
        "from": sender2,
        "messageId": "d4",
    })
    reply4b = r4b["replyText"]
    assert "mudanza" in reply4b.lower()


def test_contextual_input_no_loop():
    asyncio.run(_async_test_contextual_input_no_loop())
