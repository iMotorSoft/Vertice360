"""
Validation phase for AG-UI Pozo Flow v01.
Consider cloning this file for future versions instead of mutating it.
"""

from jsonschema import ValidationError, validate

from .schemas import OPERATION_SCHEMA


def validate_operation(operation: dict) -> list[str]:
    """
    Validate the normalized operation against the JSON schema.
    Returns a list of validation error messages (empty when valid).
    """
    errors: list[str] = []
    try:
        validate(operation, OPERATION_SCHEMA)
    except ValidationError as exc:
        errors.append(exc.message)
    return errors
