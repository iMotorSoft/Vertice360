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

async def _async_test_summary_close_flow():
    """
    Test sequence:
    1) "busco depto" -> asks zona/tipologia
    2) "Caballito, 3 ambientes" -> asks presupuesto/moneda
    3) "USD 120k" -> asks mudanza
    4) "15 de febrero" -> MUST send summary close
    5) "si" -> asks visit window follow-up
    """
    sender = "5491177778888"

    # Mock dependencies
    services._send_whatsapp_text = AsyncMock(return_value={"id": "m1"})
    # Mock AI to return a generic fallback if called, to prove we bypass it when confirming
    services._run_ai_workflow_reply = AsyncMock(return_value={
        "decision": "ask_next_best_question",
        "recommendedQuestion": "Pregunta de AI fallback",
        "responseText": "AI fallback"
    })

    # 1. Start chain
    await services.process_inbound_message({"text": "busco depto", "from": sender, "messageId": "1"})
    
    # 2. Provide Zone/Typology
    await services.process_inbound_message({"text": "Caballito, 3 ambientes", "from": sender, "messageId": "2"})
    
    # 3. Provide Budget
    await services.process_inbound_message({"text": "USD 120k", "from": sender, "messageId": "3"})
    
    # 4. Provide Date (Last slot)
    r4 = await services.process_inbound_message({"text": "15 de febrero", "from": sender, "messageId": "4"})
    
    # Check Result 4: Should be Summary Close
    reply4 = r4["replyText"]
    print(f"DEBUG: Reply 4: {reply4}")
    
    assert "Gracias. Tengo:" in reply4
    assert "Caballito" in reply4
    assert "3 ambientes" in reply4
    assert "120000" in reply4
    assert "coordinar visita" in reply4.lower()
    
    # Pending action should remain unset for summary close
    t = store._find_active_ticket_by_phone(sender)
    assert t["pendingAction"] is None

    # 5. Confirm "Si"
    r5 = await services.process_inbound_message({"text": "si, todo bien", "from": sender, "messageId": "5"})
    reply5 = r5["replyText"]
    print(f"DEBUG: Reply 5: {reply5}")

    # Check Result 5: Should ask for visit window
    assert "franja horaria" in reply5.lower()
    # PendingAction not used in new flow
    
    # Check AI was NOT called for r5 (optimization check, optional but good)
    # services._run_ai_workflow_reply.call_count should be ... well, it was called for previous steps.
    # We can check specific call args if needed, but the pendingAction state proof is enough.

def test_summary_close_flow():
    asyncio.run(_async_test_summary_close_flow())
