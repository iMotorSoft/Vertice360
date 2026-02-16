import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from backend import globalVar
from backend.modules.vertice360_workflow_demo import services, store, commercial_memory

@pytest.fixture(autouse=True)
def setup_teardown():
    store.reset_store()
    # Mock globalVar for AI reply
    globalVar.VERTICE360_AI_WORKFLOW_REPLY = True
    globalVar.VERTICE360_AI_WORKFLOW_REPLY_PREVIEW_MAX = 0
    yield
    store.reset_store()

async def _async_test_commercial_memory_no_repeat_flow():
    """
    Simulates the flow:
    1) "busco depto" -> missing everything -> asks zona/tipologia
    2) "Caballito, 3 ambientes" -> stored -> missing budget -> asks budget
    3) "USD 120k" -> stored -> missing date -> asks date
    4) "febrero" -> stored -> missing nothing -> asks visit (or AI fallback)
    """
    
    sender_phone = "5491112345678"
    
    # Mock external calls to avoid networking/AI costs
    services._send_whatsapp_text = AsyncMock(return_value={"id": "mock_msg_id"})
    services._run_ai_workflow_reply = AsyncMock(return_value={
        "decision": "ask_next_best_question",
        "recommendedQuestion": "Pregunta tonta de AI que ignora memoria",
        "responseText": "Pregunta tonta de AI que ignora memoria"
    })

    # --- Step 1: User says "busco depto" ---
    inbound_1 = {
        "text": "hola busco depto", 
        "from": sender_phone, 
        "timestamp": 1000,
        "messageId": "msg1"
    }
    res1 = await services.process_inbound_message(inbound_1)
    reply1 = res1["replyText"]
    
    # Check ticket created
    ticket = store._find_active_ticket_by_phone(sender_phone)
    assert ticket is not None
    assert ticket["commercial"]["zona"] is None
    assert ticket["commercial"]["tipologia"] is None
    
    # Expect: Ask for Zona/Tipologia (Priority 1)
    # deterministic question: "¿En qué zona o barrio estás buscando?" or combined
    # Since tipologia is also missing, logic says:
    # if zona missing: if tipologia missing -> "Por qué zona buscás y qué tipología...?"
    assert "¿Por qué zona buscás y cuántos ambientes necesitás?" in reply1


    # --- Step 2: User says "Caballito, 3 ambientes" ---
    inbound_2 = {
        "text": "en Caballito, 3 ambientes",
        "from": sender_phone,
        "timestamp": 2000,
        "messageId": "msg2"
    }
    res2 = await services.process_inbound_message(inbound_2)
    reply2 = res2["replyText"]
    
    # Check memory update
    assert ticket["commercial"]["zona"] == "Caballito"
    assert ticket["commercial"]["tipologia"] == "3 ambientes"
    assert ticket["commercial"]["presupuesto"] is None
    
    # Expect: Ask for Budget (Priority 3, skipping 2 since filled)
    assert "presupuesto" in reply2.lower() and "moneda" in reply2.lower()
    assert "zona" not in reply2.lower() # Should NOT ask for zona again

    # --- Step 3: User says "USD 120k" ---
    inbound_3 = {
        "text": "tengo USD 120k",
        "from": sender_phone,
        "timestamp": 3000,
        "messageId": "msg3"
    }
    res3 = await services.process_inbound_message(inbound_3)
    reply3 = res3["replyText"]
    
    # Check memory update
    assert ticket["commercial"]["presupuesto"] == 120000
    assert ticket["commercial"]["moneda"] == "USD"
    
    # Expect: Ask for Date (Priority 4)
    assert "mudanza" in reply3.lower()


    # --- Step 4: User says "marzo" ---
    inbound_4 = {
        "text": "me quiero mudar en marzo",
        "from": sender_phone,
        "timestamp": 4000,
        "messageId": "msg4"
    }
    res4 = await services.process_inbound_message(inbound_4)
    reply4 = res4["replyText"]
    
    # Check memory update
    assert ticket["commercial"]["fecha_mudanza"] == "marzo"

    
    # Expect: No missing slots -> Summary close
    assert "Gracias. Tengo:" in reply4

def test_commercial_memory_no_repeat_flow():
    asyncio.run(_async_test_commercial_memory_no_repeat_flow())


async def _async_test_parser_robustness():
    """Verify parsing of tricky values"""
    
    # Budget parsing
    b1, c1 = commercial_memory.parse_budget_currency("USD 120k")
    assert b1 == 120000
    assert c1 == "USD"
    
    b2, c2 = commercial_memory.parse_budget_currency("120.000 dolares")
    assert b2 == 120000
    assert c2 == "USD"
    
    b3, c3 = commercial_memory.parse_budget_currency("50M pesos")
    assert b3 == 50000000
    assert c3 == "ARS"
    
    # Zone parsing
    z1 = commercial_memory.parse_zona("busco en CABA caballito")
    assert z1 == "Caballito" # or CABA? Regex priority check
    
    # Typology
    t1 = commercial_memory.parse_tipologia("un 2 amb estaria bien")
    assert t1 == "2 ambientes"

def test_parser_robustness():
    asyncio.run(_async_test_parser_robustness())

async def _async_test_ticket_reuse():
    """Verify that multiple messages from same phone reuse the ticket"""
    sender = "5491199999999"
    
    services._send_whatsapp_text = AsyncMock(return_value={"id": "m"})
    services._run_ai_workflow_reply = AsyncMock(return_value=None)
    
    # Msg 1
    await services.process_inbound_message({"text": "hi", "from": sender, "messageId": "m1"})
    t1 = store._find_active_ticket_by_phone(sender)
    assert t1 is not None
    
    # Msg 2 (no ticketId provided in inbound)
    await services.process_inbound_message({"text": "again", "from": sender, "messageId": "m2"})
    t2 = store._find_active_ticket_by_phone(sender)
    
    assert t1["ticketId"] == t2["ticketId"]
    # 2 inbound + 1 outbound (second outbound is deduped)
    assert len(t1["messages"]) == 3
    outbound = [m for m in t1["messages"] if m.get("direction") == "outbound"]
    assert len(outbound) == 1

def test_ticket_reuse():
    asyncio.run(_async_test_ticket_reuse())
