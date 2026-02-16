"""
Test for improved zona/ambientes flow with partial capture acknowledgment.

Run with:
cd /media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/Vertice360/SrvRestAstroLS_v1/backend && python test_zona_ambientes_flow.py
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


def test_both_missing():
    """Test when both zona and ambientes are missing"""
    print("\n=== Test 1: Both zona and ambientes missing ===")

    missing = ["zona", "tipologia"]
    current = {}
    question, key = commercial_memory.build_next_best_question(missing, current)

    print(f"Missing: {missing}")
    print(f"Current: {current}")
    print(f"Question: {question}")
    print(f"Key: {key}")

    expected = "¿Por qué zona buscás y cuántos ambientes necesitás?"
    assert question == expected, f"Expected: {expected}\nGot: {question}"
    assert key == "zona", f"Expected key: zona, got: {key}"
    print("✓ PASS: Combined question when both missing")


def test_only_zona_missing():
    """Test when zona is missing but ambientes is present"""
    print("\n=== Test 2: Only zona missing (ambientes present) ===")

    missing = ["zona"]
    current = {"tipologia": "2 ambientes"}
    question, key = commercial_memory.build_next_best_question(missing, current)

    print(f"Missing: {missing}")
    print(f"Current: {current}")
    print(f"Question: {question}")
    print(f"Key: {key}")

    expected = "Perfecto, 2 ambientes. ¿Por qué zona buscás?"
    assert question == expected, f"Expected: {expected}\nGot: {question}"
    assert key == "zona", f"Expected key: zona, got: {key}"
    print("✓ PASS: Acknowledges ambientes, asks for zona")


def test_only_ambientes_missing():
    """Test when ambientes is missing but zona is present"""
    print("\n=== Test 3: Only ambientes missing (zona present) ===")

    missing = ["tipologia"]
    current = {"zona": "Palermo"}
    question, key = commercial_memory.build_next_best_question(missing, current)

    print(f"Missing: {missing}")
    print(f"Current: {current}")
    print(f"Question: {question}")
    print(f"Key: {key}")

    expected = "Perfecto, zona Palermo. ¿Cuántos ambientes necesitás?"
    assert question == expected, f"Expected: {expected}\nGot: {question}"
    assert key == "tipologia", f"Expected key: tipologia, got: {key}"
    print("✓ PASS: Acknowledges zona, asks for ambientes")


def test_monoambiente():
    """Test with monoambiente (special case)"""
    print("\n=== Test 4: Monoambiente case ===")

    missing = ["zona"]
    current = {"tipologia": "monoambiente"}
    question, key = commercial_memory.build_next_best_question(missing, current)

    print(f"Missing: {missing}")
    print(f"Current: {current}")
    print(f"Question: {question}")
    print(f"Key: {key}")

    expected = "Perfecto, 1 ambientes. ¿Por qué zona buscás?"
    assert question == expected, f"Expected: {expected}\nGot: {question}"
    print("✓ PASS: Handles monoambiente correctly")


def test_both_present():
    """Test when both are present - should proceed to presupuesto"""
    print("\n=== Test 5: Both present, presupuesto missing ===")

    missing = ["presupuesto", "moneda"]
    current = {"zona": "Palermo", "tipologia": "2 ambientes"}
    question, key = commercial_memory.build_next_best_question(missing, current)

    print(f"Missing: {missing}")
    print(f"Current: {current}")
    print(f"Question: {question}")
    print(f"Key: {key}")

    expected = "¿Cuál es tu presupuesto aproximado y en qué moneda?"
    assert question == expected, f"Expected: {expected}\nGot: {question}"
    assert key == "presupuesto", f"Expected key: presupuesto, got: {key}"
    print("✓ PASS: Proceeds to presupuesto question")


def test_no_missing():
    """Test when nothing is missing"""
    print("\n=== Test 6: No missing slots ===")

    missing = []
    current = {
        "zona": "Palermo",
        "tipologia": "2 ambientes",
        "presupuesto": 120000,
        "moneda": "USD",
    }
    question, key = commercial_memory.build_next_best_question(missing, current)

    print(f"Missing: {missing}")
    print(f"Question: {question}")
    print(f"Key: {key}")

    assert question is None, f"Expected None, got: {question}"
    assert key is None, f"Expected None, got: {key}"
    print("✓ PASS: Returns None when nothing missing")


def test_conversation_flow_simulation():
    """Simulate a complete conversation flow"""
    print("\n=== Test 7: Complete conversation flow simulation ===")

    # Step 1: User says "Hola"
    print("\nStep 1: User says 'Hola'")
    missing = ["zona", "tipologia"]
    current = {}
    question, key = commercial_memory.build_next_best_question(missing, current)
    print(f"  Bot: {question}")
    assert "zona" in question and "ambientes" in question

    # Step 2: User says "Palermo"
    print("\nStep 2: User says 'Palermo'")
    missing = ["tipologia"]  # zona is now captured
    current = {"zona": "Palermo"}
    question, key = commercial_memory.build_next_best_question(missing, current)
    print(f"  Bot: {question}")
    assert "Perfecto, zona Palermo" in question
    assert "ambientes" in question

    # Step 3: User says "3 ambientes"
    print("\nStep 3: User says '3 ambientes'")
    missing = ["presupuesto", "moneda"]
    current = {"zona": "Palermo", "tipologia": "3 ambientes"}
    question, key = commercial_memory.build_next_best_question(missing, current)
    print(f"  Bot: {question}")
    assert "presupuesto" in question

    # Step 4: User says "120k USD"
    print("\nStep 4: User says '120k USD'")
    missing = []
    current = {
        "zona": "Palermo",
        "tipologia": "3 ambientes",
        "presupuesto": 120000,
        "moneda": "USD",
    }
    question, key = commercial_memory.build_next_best_question(missing, current)
    print(f"  Bot: (no question - all slots filled)")
    assert question is None

    print("\n✓ PASS: Complete flow works correctly")


def run_all_tests():
    """Run all tests"""
    print("=" * 70)
    print("TESTING ZONA/AMBIENTES PARTIAL CAPTURE FLOW")
    print("=" * 70)

    try:
        test_both_missing()
        test_only_zona_missing()
        test_only_ambientes_missing()
        test_monoambiente()
        test_both_present()
        test_no_missing()
        test_conversation_flow_simulation()

        print("\n" + "=" * 70)
        print("ALL TESTS PASSED ✓")
        print("=" * 70)
        print("\nSummary:")
        print("- Both missing: Combined question")
        print("- Only zona missing: Acknowledges ambientes, asks for zona")
        print("- Only ambientes missing: Acknowledges zona, asks for ambientes")
        print("- Both present: Proceeds to presupuesto")
        print("- No mudanza question (already removed)")
        return True
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


# Run the tests
success = run_all_tests()
sys.exit(0 if success else 1)
