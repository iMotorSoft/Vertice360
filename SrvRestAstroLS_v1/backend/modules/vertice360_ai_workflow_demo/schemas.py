from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    workflowId: str = Field(..., min_length=1)
    input: str = Field(..., min_length=1)
    mode: str | None = "heuristic"


class ResetRequest(BaseModel):
    reason: str | None = None


class SendReplyRequest(BaseModel):
    ticketId: str = Field(..., min_length=1)
    to: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)


class IntentScore(BaseModel):
    name: str
    score: float
    evidence: list[str] = Field(default_factory=list)


class IntentSummary(BaseModel):
    intents: list[IntentScore]
    primaryIntent: str
    secondaryIntents: list[str] = Field(default_factory=list)


class PragmaticsSummary(BaseModel):
    speechAct: Literal["question", "request", "greeting", "complaint", "other"]
    urgency: Literal["low", "medium", "high"]
    missingSlots: dict[str, list[str]] = Field(default_factory=dict)
    recommendedQuestions: list[str] = Field(default_factory=list)
