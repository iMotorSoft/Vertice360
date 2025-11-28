"""
Extraction phase for AG-UI Pozo Flow v01.
Clone to a new version for future enhancements rather than mutating in place.
"""


def extract_operation(text: str, intent: str) -> dict:
    """
    Extract structured fields from the free-form input.
    This stub echoes a simple payload mimicking extraction.
    """
    return {
        "project_name": "Proyecto Demo",
        "amount": 1500000,
        "currency": "USD",
        "raw_text": text,
        "intent": intent,
    }
