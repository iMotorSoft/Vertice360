from __future__ import annotations

import asyncio
import pytest
from backend import globalVar
from backend.modules.vertice360_workflow_demo import services, store

@pytest.fixture(autouse=True)
def clean_stores():
    store.reset_store()
    yield

async def mock_send_whatsapp_text(provider, to, text):
    return {"id": "mock-msg-id", "status": "sent"}

def test_lead_flow_ordering_deterministic(monkeypatch):
    # Setup
    monkeypatch.setattr(globalVar, "VERTICE360_AI_WORKFLOW_REPLY", False)
    monkeypatch.setattr(services, "_send_whatsapp_text", mock_send_whatsapp_text)
    
    # 1. Inbound "Hi"
    res1 = asyncio.run(services.process_inbound_message({
        "provider": "meta_whatsapp",
        "channel": "whatsapp",
        "from": "541130946950",
        "to": "541100000000",
        "messageId": "inbound-1",
        "text": "Hi",
        "timestamp": 1000
    }))
    
    ticket_id = res1["ticketId"]
    reply1 = res1["replyText"]
    
    # Assert: Intro + Zona/Ambientes question
    assert "Soy el asistente de Vértice360 👋." in reply1
    assert "¿Por qué zona buscás y cuántos ambientes necesitás?" in reply1
    
    # 2. Inbound "Almagro. 2 ambientes"
    res2 = asyncio.run(services.process_inbound_message({
        "provider": "meta_whatsapp",
        "channel": "whatsapp",
        "from": "541130946950",
        "to": "541100000000",
        "messageId": "inbound-2",
        "text": "Almagro. 2 ambientes",
        "timestamp": 2000,
        "ticketId": ticket_id
    }))
    
    reply2 = res2["replyText"]
    # Assert: NO intro, ONLY presupuesto question
    assert "Soy el asistente" not in reply2
    assert "¿Cuál es tu presupuesto aproximado y en qué moneda?" in reply2
    
    # 3. Inbound "120k usd"
    res3 = asyncio.run(services.process_inbound_message({
        "provider": "meta_whatsapp",
        "channel": "whatsapp",
        "from": "541130946950",
        "to": "541100000000",
        "messageId": "inbound-3",
        "text": "120k usd",
        "timestamp": 3000,
        "ticketId": ticket_id
    }))
    
    reply3 = res3["replyText"]
    # Assert: Mudanza question
    assert "¿Para qué mes y año estimás la mudanza?" in reply3
    
    # 4. Inbound "Marzo 2026"
    res4 = asyncio.run(services.process_inbound_message({
        "provider": "meta_whatsapp",
        "channel": "whatsapp",
        "from": "541130946950",
        "to": "541100000000",
        "messageId": "inbound-4",
        "text": "Marzo 2026",
        "timestamp": 4000,
        "ticketId": ticket_id
    }))
    
    reply4 = res4["replyText"]
    # Assert: Summary and Handoff
    assert "Gracias. Tengo: zona Almagro, 2 ambientes, presupuesto 120000 USD, mudanza marzo 2026." in reply4
    assert "¿Querés coordinar visita?" in reply4
    
    ticket = store.tickets[ticket_id]
    assert ticket.get("handoffRequired") is True
    assert ticket.get("handoffStage") == "required"
    assert ticket["slot_memory"]["summarySent"] is True
    
    # 5. Inbound short greeting after summary -> keep same ticket and re-ask visit slot (no reset)
    res5 = asyncio.run(services.process_inbound_message({
        "provider": "meta_whatsapp",
        "channel": "whatsapp",
        "from": "541130946950",
        "to": "541100000000",
        "messageId": "inbound-5",
        "text": "hi",
        "timestamp": 5000,
        "ticketId": ticket_id
    }))
    
    assert res5["ticketId"] == ticket_id
    assert "¿Por qué zona buscás" not in (res5.get("replyText") or "")
    assert "día y franja horaria" in (res5.get("replyText") or "").lower()
