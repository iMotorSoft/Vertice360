"""Ruta demo de chat (LainGraph) sobre datos mock de Pozo360."""

from __future__ import annotations

from typing import Any

from litestar import Router, Request, post
from litestar.exceptions import HTTPException
from pydantic import BaseModel, Field

from services.demo_codex_chat import run_demo_chat


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="Mensaje del usuario para LainGraph.")
    history: list[ChatMessage] = Field(
        default_factory=list, description="Historial opcional de mensajes previos."
    )


class ChatResponse(BaseModel):
    reply: str
    model: str
    created: int
    usage: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None


@post("/chat", tags=["demo", "codex", "chat"])
async def chat_with_lain_graph(request: Request) -> ChatResponse:
    """Ejecuta una interacción de chat demo usando gpt-4o-mini."""
    try:
        body = await request.json()
        payload = ChatRequest.model_validate(body)
        result = run_demo_chat(prompt=payload.prompt, history=[m.dict() for m in payload.history])
    except Exception as exc:  # pragma: no cover - queremos devolver el detalle al front
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ChatResponse(**result)


router = Router(path="/api/demo/codex", route_handlers=[chat_with_lain_graph])
