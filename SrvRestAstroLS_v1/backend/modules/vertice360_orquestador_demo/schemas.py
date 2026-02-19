from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class IngestMessageRequest(BaseModel):
    phone: str = Field(..., min_length=3)
    text: str = Field(..., min_length=1)
    project_code: str | None = None
    source: str | None = None


class VisitProposeRequest(BaseModel):
    ticket_id: str = Field(..., min_length=1)
    advisor_name: str | None = None
    option1: datetime | None = None
    option2: datetime | None = None
    option3: datetime | None = None
    message_out: str = Field(..., min_length=1)
    mode: Literal["propose", "reschedule"] = "propose"


class VisitConfirmRequest(BaseModel):
    proposal_id: str = Field(..., min_length=1)
    confirmed_option: int = Field(..., ge=1, le=3)
    confirmed_by: Literal["client", "advisor", "supervisor"]


class VisitRescheduleRequest(BaseModel):
    ticket_id: str = Field(..., min_length=1)
    advisor_name: str | None = None
    option1: datetime | None = None
    option2: datetime | None = None
    option3: datetime | None = None
    message_out: str = Field(..., min_length=1)


class SupervisorSendRequest(BaseModel):
    ticket_id: str = Field(..., min_length=1)
    target: Literal["client", "advisor"]
    text: str = Field(..., min_length=1)


class ApiEnvelope(BaseModel):
    ok: bool = True
    data: dict[str, Any]
