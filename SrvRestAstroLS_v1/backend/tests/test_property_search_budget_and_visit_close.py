import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

from backend.modules.vertice360_workflow_demo import commercial_memory
from backend.modules.vertice360_ai_workflow_demo import langgraph_flow
from backend.modules.vertice360_ai_workflow_demo import store

def test_budget_parsing_variants():
    # 1. "120 k usd"
    amt, cur = commercial_memory.parse_budget_currency("presupuesto 120 k usd")
    assert amt == 120000
    assert cur == "USD"

    # 2. "120k" 
    amt, cur = commercial_memory.parse_budget_currency("120k") 
    assert amt == 120000
    assert cur is None 

    # 3. "usd 90.000"
    amt, cur = commercial_memory.parse_budget_currency("usd 90.000")
    assert amt == 90000
    assert cur == "USD"

    # 4. "1.5 millones de pesos"
    amt, cur = commercial_memory.parse_budget_currency("1.5 millones de pesos")
    assert amt == 1500000
    assert cur == "ARS"

    # 5. "USD 120 k"
    amt, cur = commercial_memory.parse_budget_currency("USD 120 k")
    assert amt == 120000
    assert cur == "USD"


def test_visit_parsing():
    # 1. "viernes 14hs a 16hs"
    res = commercial_memory.parse_visita("puedo el viernes 14hs a 16hs")
    assert res["visit_day_of_week"] == "viernes"
    assert res["visit_time_from"] == "14:00"
    assert res["visit_time_to"] == "16:00"

    # 2. "jueves 14 a 16"
    res = commercial_memory.parse_visita("jueves 14 a 16")
    assert res["visit_day_of_week"] == "jueves"
    assert res["visit_time_from"] == "14:00"
    assert res["visit_time_to"] == "16:00"
    
    # 3. "Lunes a las 16"
    res = commercial_memory.parse_visita("Lunes a las 16")
    assert res["visit_day_of_week"] == "lunes"
    assert res["visit_time_from"] == "16:00"
    assert res["visit_time_to"] is None


def run_async(coro):
    return asyncio.run(coro)

def test_flow_visit_handoff():
    async def _test():
        # Initialize store for the run
        # create_run(workflow_id, input_text) returns run dict with 'runId'
        run_obj = store.create_run("test_workflow", "user input")
        run_id = run_obj["runId"]
        
        # Setup state with filled slots except visit
        state = {
            "intent": "general", 
            "intent_hint": "property_search", 
            "commercial_slots": {
                "zona": "Palermo",
                "tipologia": "3 amb",
                "presupuesto": 120000,
                "moneda": "USD",
                "fecha_mudanza": "abril 2026",
                "visit": None,
                "handoff_done": False
            },
            "pragmatics": {"missingSlots": {}}, 
            "missing_slots_count": 0,
            "run_id": run_id
        }
        
        # 1. Decide Next -> Should ask for visit
        res_decide = await langgraph_flow.decide_next(state)
        assert res_decide["decision"] == "ask_visit_schedule"
        
        # Simulate response building for this decision
        state["decision"] = "ask_visit_schedule"
        res_build = await langgraph_flow.build_response(state)
        assert "Qué día y horario" in res_build["response_text"]
        
        # 2. User provides visit -> Handoff
        state["commercial_slots"]["visit"] = {
            "visit_day_of_week": "viernes",
            "visit_time_from": "14:00",
            "visit_time_to": "16:00"
        }
        
        res_decide_2 = await langgraph_flow.decide_next(state)
        assert res_decide_2["decision"] == "handoff_to_sales"
        assert res_decide_2["commercial"]["handoff_done"] is True
        
        state["decision"] = "handoff_to_sales"
        res_build_2 = await langgraph_flow.build_response(state)
        text = res_build_2["response_text"]
        
        assert "viernes" in text
        assert "14:00" in text
        # Summary rendering might include spaces or not depending on implementation
        assert "USD 120" in text # Loose match to be safe
        assert "confirm" in text 

    run_async(_test())

if __name__ == "__main__":
    try:
        test_budget_parsing_variants()
        print("test_budget_parsing_variants PASS")
        test_visit_parsing()
        print("test_visit_parsing PASS")
        test_flow_visit_handoff()
        print("test_flow_visit_handoff PASS")
        print("ALL TESTS PASSED")
    except Exception as e:
        print(f"TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
