"""
Classifier phase for AG-UI Pozo Flow v01.
Clone this module to a new version (e.g., agui_pozo_flow_v02) for future iterations.
"""


def classify_intent(text: str) -> dict:
    """
    Classify the intent of the user's input.
    In this stub version, it returns a static intent with high confidence.
    """
    return {"intent": "single_operation", "confidence": 0.9, "echo": text}
