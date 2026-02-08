import asyncio
import pytest
from unittest.mock import AsyncMock
from backend import globalVar
from backend.modules.vertice360_workflow_demo import services, store, commercial_memory

@pytest.fixture(autouse=True)
def setup_teardown():
    store.reset_store()
    globalVar.VERTICE360_AI_WORKFLOW_REPLY = True
    globalVar.VERTICE360_AI_WORKFLOW_REPLY_PREVIEW_MAX = 0
    yield
    store.reset_store()

async def _async_test_ars_budget_flow():
    """
    Test ARS parsing sequence:
    1) "busco depto" => ask zona/tipologia
    2) "Caballito, 3 ambientes" => ask presupuesto/moneda
    3) "1000000 argentinos" => sets budget=1000000, currency=ARS, asks date
    """
    sender = "5491199990000"

    # Mock AI
    services._send_whatsapp_text = AsyncMock(return_value={"id": "m1"})
    services._run_ai_workflow_reply = AsyncMock(return_value={
        "decision": "ask_next_best_question",
        "recommendedQuestion": "¿Cuál es tu presupuesto?",
        "responseText": "AI fallback"
    })

    # 1. Start
    await services.process_inbound_message({"text": "busco depto", "from": sender, "messageId": "1"})
    
    # 2. Zone/Typology
    await services.process_inbound_message({"text": "Caballito, 3 ambientes", "from": sender, "messageId": "2"})
    t = store._find_active_ticket_by_phone(sender)
    assert t["commercial"]["presupuesto"] is None
    
    # 3. "1000000 argentinos"
    r3 = await services.process_inbound_message({"text": "1000000 argentinos", "from": sender, "messageId": "3"})
    print(f"Reply 3: {r3['replyText']}")
    
    assert t["commercial"]["presupuesto"] == 1000000
    assert t["commercial"]["moneda"] == "ARS"
    
    # Verify next question is about DATE (mudanza), not budget again
    assert "mudarte" in r3["replyText"].lower() or "cuando" in r3["replyText"].lower()
    
    # 4. "1m pesos" parsing check
    p4, c4 = commercial_memory.parse_budget_currency("1m pesos")
    assert p4 == 1000000
    assert c4 == "ARS"
    
    # 5. "1.5m usd" parsing check
    p5, c5 = commercial_memory.parse_budget_currency("1.5m usd")
    assert p5 == 1500000
    assert c5 == "USD"

    # 6. "120.000" (default ARS fallback logic test)
    # The requirement said "$ 120.000" => ARS. 
    p6, c6 = commercial_memory.parse_budget_currency("$ 120.000")
    assert p6 == 120000
    assert c6 == "ARS" # via fallback_currency logic if $ present

def test_ars_budget_flow():
    asyncio.run(_async_test_ars_budget_flow())
