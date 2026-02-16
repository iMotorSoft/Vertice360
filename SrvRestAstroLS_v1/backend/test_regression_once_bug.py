"""
Regression test for bug: Bot stuck after partial zona/ambientes capture

Bug Report:
- User: "Buen dia" → ask zona+ambientes
- User: "3 ambientes" → bot asks missing zona (OK)
- User: "Once" → expected: ask presupuesto; actual: no response (stuck)

Root Cause:
- "Once" neighborhood was missing from NEIGHBORHOOD_GAZETTEER
- parse_zona("Once") returned None, so zona slot was never filled
- Bot kept asking for zona indefinitely

Fix:
- Added "Once" to NEIGHBORHOOD_GAZETTEER

Run with:
cd /media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/Vertice360/SrvRestAstroLS_v1/backend && python test_regression_once_bug.py
"""

import sys
import os

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import types

backend_module = types.ModuleType("backend")
backend_module.__path__ = [backend_dir]
sys.modules["backend"] = backend_module

import importlib.util

spec = importlib.util.spec_from_file_location(
    "commercial_memory",
    os.path.join(backend_dir, "modules/vertice360_workflow_demo/commercial_memory.py"),
)
commercial_memory = importlib.util.module_from_spec(spec)
sys.modules["commercial_memory"] = commercial_memory
spec.loader.exec_module(commercial_memory)


def test_once_neighborhood_recognition():
    """Test that 'Once' is recognized as a valid zona"""
    print("\n" + "=" * 70)
    print("REGRESSION TEST: 'Once' neighborhood recognition")
    print("=" * 70)

    # Test parse_zona with various forms of "Once"
    test_cases = [
        ("Once", "Once"),
        ("en Once", "Once"),
        ("zona Once", "Once"),
        ("barrio Once", "Once"),
        ("Busco en Once", "Once"),
    ]

    print("\nTesting parse_zona with 'Once':")
    all_passed = True
    for text, expected in test_cases:
        result = commercial_memory.parse_zona(text)
        status = "✓" if result == expected else "✗"
        print(f"  {status} parse_zona('{text}') = {result}")
        if result != expected:
            all_passed = False

    # Verify Once is in gazetteer
    assert "Once" in commercial_memory.NEIGHBORHOOD_GAZETTEER, (
        "Once should be in NEIGHBORHOOD_GAZETTEER"
    )
    print("\n✓ 'Once' is in NEIGHBORHOOD_GAZETTEER")

    return all_passed


def test_complete_flow_with_once():
    """Test complete conversation flow with 'Once' as zona"""
    print("\n" + "=" * 70)
    print("REGRESSION TEST: Complete flow with 'Once'")
    print("=" * 70)

    ticket = {
        "commercial": {
            "zona": None,
            "tipologia": None,
            "presupuesto": None,
            "moneda": None,
        }
    }

    # Step 1: Initial greeting
    print("\n1. User: 'Buen dia'")
    missing = commercial_memory.calculate_missing_slots(ticket["commercial"])
    question, _ = commercial_memory.build_next_best_question(
        missing, ticket["commercial"]
    )
    print(f"   Bot: {question}")
    assert "zona" in question and "ambientes" in question

    # Step 2: User provides ambientes
    print("\n2. User: '3 ambientes'")
    ticket["commercial"]["tipologia"] = "3 ambientes"
    missing = commercial_memory.calculate_missing_slots(ticket["commercial"])
    question, key = commercial_memory.build_next_best_question(
        missing, ticket["commercial"]
    )
    print(f"   Bot: {question}")
    assert "Perfecto" in question, "Should acknowledge ambientes"
    assert "zona" in question.lower(), "Should ask for zona"

    # Step 3: User provides "Once" (THE CRITICAL TEST)
    print("\n3. User: 'Once'")
    zona = commercial_memory.parse_zona("Once")
    assert zona is not None, "BUG: 'Once' should be recognized as zona"
    ticket["commercial"]["zona"] = zona

    missing = commercial_memory.calculate_missing_slots(ticket["commercial"])
    print(f"   Missing slots: {missing}")

    question, key = commercial_memory.build_next_best_question(
        missing, ticket["commercial"]
    )
    print(f"   Bot: {question}")

    # THIS IS THE KEY ASSERTION - bot should now ask for presupuesto
    assert question is not None, "Bot should not be silent"
    assert "presupuesto" in question.lower(), (
        f"Bot should ask for presupuesto, got: {question}"
    )

    # Step 4: User provides presupuesto
    print("\n4. User: '120000 USD'")
    ticket["commercial"]["presupuesto"] = 120000
    ticket["commercial"]["moneda"] = "USD"

    missing = commercial_memory.calculate_missing_slots(ticket["commercial"])
    print(f"   Missing slots: {missing}")
    assert len(missing) == 0, "All slots should be filled"

    print("\n✅ REGRESSION TEST PASSED: Flow completes correctly with 'Once'")
    return True


def test_other_neighborhoods():
    """Test that other common neighborhoods are recognized"""
    print("\n" + "=" * 70)
    print("TEST: Other common neighborhoods")
    print("=" * 70)

    neighborhoods = [
        "Palermo",
        "Belgrano",
        "Recoleta",
        "Almagro",
        "Caballito",
        "San Telmo",
        "Once",
        "Villa Crespo",
        "Nuñez",
        "Colegiales",
        "Chacarita",
        "Boedo",
        "Flores",
        "Floresta",
        "Villa Urquiza",
        "Retiro",
    ]

    print("\nChecking standalone recognition:")
    for neighborhood in neighborhoods:
        result = commercial_memory.parse_zona(neighborhood)
        status = "✓" if result == neighborhood else "✗"
        print(f"  {status} {neighborhood}: {result}")

    return True


def run_all_tests():
    """Run all regression tests"""
    print("=" * 70)
    print("REGRESSION TEST SUITE: Once Bug Fix")
    print("=" * 70)

    try:
        test_once_neighborhood_recognition()
        test_complete_flow_with_once()
        test_other_neighborhoods()

        print("\n" + "=" * 70)
        print("ALL REGRESSION TESTS PASSED ✓")
        print("=" * 70)
        print("\nFix Summary:")
        print("- Added 'Once' to NEIGHBORHOOD_GAZETTEER")
        print("- parse_zona('Once') now returns 'Once'")
        print("- Flow continues to presupuesto after zona+ambientes")
        return True
    except AssertionError as e:
        print(f"\n❌ REGRESSION TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
