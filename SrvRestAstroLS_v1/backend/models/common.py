from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str


class VersionResponse(BaseModel):
    app_name: str
    version: str
    environment: str


class FlowRunResponse(BaseModel):
    raw_input: str
    intent: dict
    raw_extracted: dict
    normalized_operation: dict
    validation_errors: list[str]
    meta: dict[str, Any]
