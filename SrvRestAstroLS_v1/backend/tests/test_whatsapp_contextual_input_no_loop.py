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
    assert "zona" in reply1.lower() or "tipolog" in reply1.lower()

    # 2) Provide zone + typology
    r2 = await services.process_inbound_message({
        "text": "palermo, 2 ambientes",
        "from": sender,
        "messageId": "c2",
    })
    reply2 = r2["replyText"]
    assert "presupuesto" in reply2.lower()

    # 3) Provide budget
    r3 = await services.process_inbound_message({
        "text": "90k usd",
        "from": sender,
        "messageId": "c3",
    })
    reply3 = r3["replyText"]
    assert "presupuesto" not in reply3.lower()

    # 4) Repeat budget in another format -> should not loop the same question
    r4 = await services.process_inbound_message({
        "text": "90000 dolares",
        "from": sender,
        "messageId": "c4",
    })
    reply4 = r4["replyText"]
    assert "presupuesto" not in reply4.lower()
    assert reply4 != reply3

    # Ensure contextual input is used
    assert captured_inputs
    assert "Mensaje usuario: quiero un depto" in captured_inputs[0]
    assert "pending_ambiguity" in captured_inputs[0]

    # Ambiguity confirmation scenario (new ticket)
    sender2 = "5491100033333"
    r1b = await services.process_inbound_message({
        "text": "quiero un depto",
        "from": sender2,
        "messageId": "d1",
    })
    reply1b = r1b["replyText"]
    assert "zona" in reply1b.lower() or "tipolog" in reply1b.lower()

    r2b = await services.process_inbound_message({
        "text": "palermo, 2 ambientes",
        "from": sender2,
        "messageId": "d2",
    })
    reply2b = r2b["replyText"]
    assert "presupuesto" in reply2b.lower()

    r3b = await services.process_inbound_message({
        "text": "usd 120",
        "from": sender2,
        "messageId": "d3",
    })
    reply3b = r3b["replyText"]
    assert "mil" in reply3b.lower()

    r4b = await services.process_inbound_message({
        "text": "si",
        "from": sender2,
        "messageId": "d4",
    })
    reply4b = r4b["replyText"]
    assert reply4b != reply3b
    assert "presupuesto" not in reply4b.lower()


def test_contextual_input_no_loop():
    asyncio.run(_async_test_contextual_input_no_loop())
