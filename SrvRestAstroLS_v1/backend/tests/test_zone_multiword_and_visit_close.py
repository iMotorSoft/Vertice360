import asyncio
import re
from unittest.mock import MagicMock, AsyncMock
# We need to mock things we can't import easily or that depend on heavy machinery
# But here we are importing actual modules since we want integration test logic
from modules.vertice360_workflow_demo import commercial_memory
from modules.vertice360_ai_workflow_demo import langgraph_flow

# Simple helper to run async
def run_async(coro):
    return asyncio.run(coro)

# Mock store to avoid 'run not found'
langgraph_flow.store = MagicMock()
langgraph_flow.store.add_step = MagicMock()
# Also mock _record_step if needed, but mocking store is enough if _record_step just calls it
# Actually _record_step logic:
# await store.add_step(...)
# Since it is async, MagicMock might not be awaitable if called directly?
# store.add_step is usually sync? Let's check trace. 
# Trace says: store.add_step(run_id, step) -> raise KeyError.
# So it is sync.

# However, _record_step is async def.
# It calls store.add_step synchronously?
# Let's mock _record_step to be safe and avoid any store interaction.
langgraph_flow._record_step = AsyncMock()

def test_zone_multiword_extraction():
    # 1. Gazetteer check
    assert commercial_memory.parse_zona("Busco en Villa Lugano") == "Villa Lugano"
    assert commercial_memory.parse_zona("Quiero por Parque Chacabuco") == "Parque Chacabuco"
    assert commercial_memory.parse_zona("villa crespo cerca de corrientes") == "Villa Crespo"
    
    # 2. Regex fallback check
    # "zona palermo" -> Palermo
    assert commercial_memory.parse_zona("zona palermo") == "Palermo"
    
def test_budget_ambiguity_resolution():
    # 1. Ambiguous number
    val, cur = commercial_memory.parse_budget_currency("50000")
    assert val == 50000
    assert cur is None # Ambiguous
    
    # 2. Explicit currency
    val, cur = commercial_memory.parse_budget_currency("50000 pesos")
    assert val == 50000
    assert cur == "ARS"
    
    val, cur = commercial_memory.parse_budget_currency("1000 usd")
    assert val == 1000
    assert cur == "USD"
    
    val, cur = commercial_memory.parse_budget_currency("1000 argentinos")
    assert val == 1000
    assert cur == "ARS"
    
    # 3. Ignore small numbers heuristic
    val, cur = commercial_memory.parse_budget_currency("16")
    assert val is None # Should be ignored as likely time/date
    
    val, cur = commercial_memory.parse_budget_currency("16")
    assert val is None # Should be ignored as likely time/date
    
    # val, cur = commercial_memory.parse_budget_currency("2025")
    # assert val is None # Likely year - debatable if it should be budget 2025. Skipped.

def test_visit_parsing_and_handoff():
    async def _test():
        # Setup state
        state = {
            "input": "Prefiero ir el jueves a las 16 horas",
            "commercial_slots": {
                "zona": "Palermo",
                "tipologia": "Depto",
                "presupuesto": 1000,
                "moneda": "USD"
            },
            "intent_hint": "property_search",
            "run_id": "test_run",
            # We need intents/pk dummy if pragmatics uses them
            "intents": [],
            "entities": {"visit": {"visit_day_of_week": "jueves", "visit_time_from": "16"}} 
        }
        
        # Test extract_entities logic indirectly via what extract_entities returns
        # But we can call extract_entities directly if we want
        extracted = await langgraph_flow.extract_entities(state)
        # Verify extracted
        assert extracted["entities"]["visit"]["visit_day_of_week"] == "jueves"
        
        # Manually update state like the graph would
        state["entities"] = extracted["entities"]
        
        # Run pragmatics
        res_prag = await langgraph_flow.pragmatics(state)
        comm_slots = res_prag["commercial_slots"]
        assert comm_slots["visit"] is not None
        
        # Run decide_next
        state["commercial_slots"] = comm_slots
        res_decide = await langgraph_flow.decide_next(state)
        print(f"DEBUG: res_decide keys: {res_decide.keys()}")
        if "commercial" not in res_decide:
            print(f"DEBUG: state['commercial_slots']: {state.get('commercial_slots')}")
        
        # Should be handoff_to_sales because visits are present and slots are full
        assert res_decide["decision"] == "handoff_to_sales"
        assert res_decide["commercial"]["handoff_done"] is True
        
        # Run build_response
        state["decision"] = "handoff_to_sales"
        state["commercial_slots"] = res_decide["commercial"]
        res_build = await langgraph_flow.build_response(state)
        
        print("Response:", res_build["response_text"])
        assert "jueves" in res_build["response_text"]
        assert "16" in res_build["response_text"]
        assert "Palermo" in res_build["response_text"]
        
    run_async(_test())

def test_visit_close_commercial():
    async def _test():
        # Case: All slots full but NO visit yet
        state = {
            "input": "Busco depto en palermo 1000 usd",
            "commercial_slots": {
                "zona": "Palermo",
                "tipologia": "Depto",
                "presupuesto": 1000,
                "moneda": "USD"
            },
            "intent_hint": "property_search",
            "pragmatics": {"missingSlots": {}}, # No missing slots
            "intent": "property_search",
            "intents": [{"name": "property_search", "score": 0.9}]
        }
        
        # Skip straight to decide_next since we set up the state
        res_decide = await langgraph_flow.decide_next(state)
        
        # Should go to close_commercial to ask for visit
        assert res_decide["decision"] == "close_commercial"
        assert res_decide["commercial"]["expected_slot"] == "visit_schedule"
        
        # Check response
        state["decision"] = "close_commercial"
        state["commercial_slots"] = res_decide["commercial"]
        res_build = await langgraph_flow.build_response(state)
        
        assert "Qué día y horario" in res_build["response_text"]
        assert "Qué día y horario" in res_build["response_text"]
        assert "Tengo tus preferencias" in res_build["response_text"]
        assert "Palermo" in res_build["response_text"]
        
    run_async(_test())

if __name__ == "__main__":
    try:
        test_zone_multiword_extraction()
        print("test_zone_multiword_extraction PASS")
        test_budget_ambiguity_resolution()
        print("test_budget_ambiguity_resolution PASS")
        test_visit_parsing_and_handoff()
        print("test_visit_parsing_and_handoff PASS")
        test_visit_close_commercial()
        print("test_visit_close_commercial PASS")
        print("ALL TESTS PASSED")
    except Exception as e:
        print(f"TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
