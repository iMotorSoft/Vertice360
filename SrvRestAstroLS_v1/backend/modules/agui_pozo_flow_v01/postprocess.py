"""
Post-processing phase for AG-UI Pozo Flow v01.
Prefer creating a new versioned module for significant changes.
"""

from datetime import datetime
from uuid import uuid4


def apply_business_rules(raw_operation: dict) -> dict:
    """
    Normalize the extracted operation and add business metadata.
    """
    normalized = {
        "operation_id": f"op-{uuid4()}",
        "project_name": raw_operation.get("project_name"),
        "amount": raw_operation.get("amount"),
        "currency": raw_operation.get("currency"),
        "received_at": datetime.utcnow().isoformat(),
        "meta": {"source": "agui_pozo_flow_v01"},
    }
    return normalized
