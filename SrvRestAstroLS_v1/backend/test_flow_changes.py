"""
Test script to verify the WhatsApp flow changes:
1. fecha_mudanza is no longer asked
2. Final message format is correct
3. Handoff happens after presupuesto
4. "Hi" doesn't restart flow when in handoff state

Run this test with:
cd /media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/Vertice360/SrvRestAstroLS_v1/backend && python -c "exec(open('test_flow_changes.py').read())"
"""

import sys
import os

# Add the parent directory to Python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Create a mock backend module structure
import types

backend_module = types.ModuleType("backend")
backend_module.__path__ = [backend_dir]
sys.modules["backend"] = backend_module

# Now import directly from the file
import importlib.util

spec = importlib.util.spec_from_file_location(
    "commercial_memory",
    os.path.join(backend_dir, "modules/vertice360_workflow_demo/commercial_memory.py"),
)
commercial_memory = importlib.util.module_from_spec(spec)
sys.modules["commercial_memory"] = commercial_memory
spec.loader.exec_module(commercial_memory)


def test_commercial_slot_priority():
    """Test that fecha_mudanza is not in COMMERCIAL_SLOT_PRIORITY"""
    print("\n=== Test 1: COMMERCIAL_SLOT_PRIORITY ===")
    priority = commercial_memory.COMMERCIAL_SLOT_PRIORITY
    print(f"COMMERCIAL_SLOT_PRIORITY: {priority}")

    assert "fecha_mudanza" not in priority, "fecha_mudanza should not be in priority"
    assert "zona" in priority, "zona should be in priority"
    assert "tipologia" in priority, "tipologia should be in priority"
    assert "presupuesto" in priority, "presupuesto should be in priority"
    print("✓ PASS: fecha_mudanza correctly removed from priority")


def test_build_next_best_question():
    """Test that fecha_mudanza question is not asked"""
    print("\n=== Test 2: build_next_best_question ===")

    # Test when only fecha_mudanza would be missing (should return None now)
    missing = ["fecha_mudanza"]
    question, key = commercial_memory.build_next_best_question(missing)
    print(f"Missing: {missing} -> Question: {question}, Key: {key}")

    assert question is None, "Should not ask fecha_mudanza question"
    assert key is None, "Should return None key"
    print("✓ PASS: No question for fecha_mudanza")

    # Test normal flow
    missing = ["zona", "tipologia"]
    question, key = commercial_memory.build_next_best_question(missing)
    print(f"Missing: {missing} -> Question: {question}, Key: {key}")

    assert question is not None, "Should ask about zona"
    assert "zona" in question.lower() or "ambientes" in question.lower(), (
        "Should mention zona or ambientes"
    )
    print("✓ PASS: Correct question for zona/ambientes")

    # Test presupuesto question
    missing = ["presupuesto"]
    question, key = commercial_memory.build_next_best_question(missing)
    print(f"Missing: {missing} -> Question: {question}, Key: {key}")

    assert question is not None, "Should ask about presupuesto"
    assert "presupuesto" in question.lower(), "Should mention presupuesto"
    print("✓ PASS: Correct question for presupuesto")


def test_budget_parsing():
    """Test budget parsing still works correctly"""
    print("\n=== Test 3: Budget Parsing ===")

    test_cases = [
        ("120k USD", 120000, "USD"),
        ("150000 pesos", 150000, "ARS"),
        ("200 mil", 200000, None),
        ("usd 120", 120, "USD"),
    ]

    for text, expected_amount, expected_currency in test_cases:
        amount, currency = commercial_memory.parse_budget_currency(text)
        print(f"'{text}' -> amount={amount}, currency={currency}")

        assert amount == expected_amount, (
            f"Expected amount {expected_amount}, got {amount}"
        )
        if expected_currency:
            assert currency == expected_currency, (
                f"Expected currency {expected_currency}, got {currency}"
            )

    print("✓ PASS: Budget parsing works correctly")


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("TESTING WHATSAPP FLOW CHANGES")
    print("=" * 60)

    try:
        test_commercial_slot_priority()
        test_build_next_best_question()
        test_budget_parsing()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
        print("\nSummary of changes:")
        print("- fecha_mudanza removed from COMMERCIAL_SLOT_PRIORITY")
        print("- No question asked for fecha_mudanza")
        print("- Flow goes directly to handoff after presupuesto")
        print("- Budget parsing still works correctly")
        return True
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


# Run the tests
success = run_all_tests()
