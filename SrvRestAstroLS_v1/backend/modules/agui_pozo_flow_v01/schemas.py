"""
JSON schemas for AG-UI Pozo Flow v01.
Clone this module when evolving the schema in future versions.
"""

OPERATION_SCHEMA = {
    "type": "object",
    "properties": {
        "operation_id": {"type": "string"},
        "project_name": {"type": "string"},
        "amount": {"type": "number"},
        "currency": {"type": "string"},
        "received_at": {"type": "string", "format": "date-time"},
    },
    "required": ["operation_id", "project_name", "amount", "currency", "received_at"],
}
