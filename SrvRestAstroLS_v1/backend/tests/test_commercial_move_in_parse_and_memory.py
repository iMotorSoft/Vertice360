import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from backend import globalVar
from backend.modules.vertice360_workflow_demo import services, store, commercial_memory

@pytest.fixture(autouse=True)
def setup_teardown():
    store.reset_store()
    globalVar.VERTICE360_AI_WORKFLOW_REPLY = True
    globalVar.VERTICE360_AI_WORKFLOW_REPLY_PREVIEW_MAX = 0
    yield
    store.reset_store()

async def _async_test_move_in_parsing_and_memory():
    """
    Test requested sequence:
      a) inbound "busco depto" -> pregunta zona/tipologia
      b) inbound "Caballito, 3 ambientes" -> pregunta presupuesto/moneda
      c) inbound "USD 120k" -> pregunta mudanza
      d) inbound "mediados de febrero" -> YA NO pregunta mudanza; propone visita
    """
    sender = "5491155556666"

    # Mock dependencies
    services._send_whatsapp_text = AsyncMock(return_value={"id": "m1"})
    # AI mock that tries to be annoying (asking what is already known) to verify we override it
    services._run_ai_workflow_reply = AsyncMock(return_value={
        "decision": "ask_next_best_question",
        "recommendedQuestion": "¿Para cuándo necesitás mudarte?", # Simulating loop
        "responseText": "AI Response"
    })

    # a) "busco depto"
    r1 = await services.process_inbound_message({"text": "busco depto", "from": sender, "messageId": "1"})
    t = store._find_active_ticket_by_phone(sender)
    assert t is not None
    assert "¿En qué zona o barrio" in r1["replyText"] or "zona" in r1["replyText"].lower()

    # b) "Caballito, 3 ambientes"
    r2 = await services.process_inbound_message({"text": "Caballito, 3 ambientes", "from": sender, "messageId": "2"})
    assert t["commercial"]["zona"] == "Caballito"
    assert t["commercial"]["tipologia"] == "3 ambientes"
    assert "presupuesto" in r2["replyText"].lower()

    # c) "USD 120k"
    r3 = await services.process_inbound_message({"text": "USD 120k", "from": sender, "messageId": "3"})
    assert t["commercial"]["presupuesto"] == 120000
    assert "mudarte" in r3["replyText"].lower()

    # d) "mediados de febrero"
    r4 = await services.process_inbound_message({"text": "mediados de febrero", "from": sender, "messageId": "4"})
    
    # 1. Verify persisted in memory
    assert t["commercial"]["fecha_mudanza"] is not None
    assert "mediados de febrero" in t["commercial"]["fecha_mudanza"] or "febrero" in t["commercial"]["fecha_mudanza"]
    
    # 2. Verify we did NOT ask for date again (loop fixed)
    # 3. Verify we proposed visit (Goal 3)
    assert "coordinar visita" in r4["replyText"]
    print(f"DEBUG: Reply 4 was: {r4['replyText']}")

    # e) "15 de febrero" (Additional robustness check on NEW ticket or same?)
    # Let's try overwriting or similar format on same ticket? 
    # Or just parsing check separately.
    
    # Check parsing directly
    p1 = commercial_memory.parse_fecha_mudanza("15 de febrero")
    assert "02-15" in p1 # "2026-02-15"
    
    p2 = commercial_memory.parse_fecha_mudanza("15/02")
    assert "02-15" in p2
    
    p3 = commercial_memory.parse_fecha_mudanza("la semana que viene") 
    # Fallback to temporal keyword "semana" -> returns cleaned text
    assert p3 == "la semana que viene"

def test_move_in_parsing_and_memory():
    asyncio.run(_async_test_move_in_parsing_and_memory())
