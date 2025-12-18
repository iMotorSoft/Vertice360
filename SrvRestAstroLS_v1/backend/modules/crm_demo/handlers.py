from __future__ import annotations

from typing import Any

from litestar import Controller, Router, get, post
from litestar.exceptions import HTTPException

from backend.modules.crm_demo import events, store


def _ensure_payload_keys(payload: dict[str, Any], required: list[str]) -> None:
    missing = [k for k in required if not payload.get(k)]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing fields: {', '.join(missing)}")


class InboxController(Controller):
    path = "/inbox"

    @get("/conversations")
    async def list_conversations(self) -> list[dict[str, Any]]:
        return store.store.list_conversations()

    @get("/conversations/{conversation_id:str}")
    async def conversation_detail(self, conversation_id: str) -> dict[str, Any]:
        conv = store.store.get_conversation(conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conv

    @post("/conversations/{conversation_id:str}/send")
    async def send_message(self, conversation_id: str, data: dict[str, Any]) -> dict[str, Any]:
        _ensure_payload_keys(data, ["text"])
        try:
            msg = store.store.add_outbound_message(conversation_id, data["text"])
        except KeyError:
            raise HTTPException(status_code=404, detail="Conversation not found")

        payload = store.store._message_to_dict(msg)  # noqa: SLF001 - local serialization helper
        await events.publish("conversation.message.new", payload)
        await events.publish("conversation.message.status", {**payload, "status": "sent"})
        return payload


class MockInboundController(Controller):
    path = "/mock"

    @post("/inbound")
    async def inbound(self, data: dict[str, Any]) -> dict[str, Any]:
        _ensure_payload_keys(data, ["channel", "conversationId", "text"])
        conversation_id = data["conversationId"]
        try:
            msg = store.store.add_inbound_message(data.get("channel", ""), conversation_id, data["text"])
        except KeyError:
            raise HTTPException(status_code=404, detail="Conversation not found")

        payload = store.store._message_to_dict(msg)  # noqa: SLF001 - local serialization helper
        await events.publish("conversation.message.new", payload)
        await events.publish("conversation.message.status", {**payload, "status": "delivered"})
        return payload


class DealsController(Controller):
    path = "/deals"

    @post("/{deal_id:str}/move")
    async def move_deal(self, deal_id: str, data: dict[str, Any]) -> dict[str, Any]:
        _ensure_payload_keys(data, ["toStageId"])
        try:
            deal = store.store.move_deal(deal_id, data["toStageId"])
        except KeyError:
            raise HTTPException(status_code=404, detail="Deal not found")
        payload = store.store._deal_to_dict(deal)  # noqa: SLF001 - local serialization helper
        await events.publish("deal.stage.changed", payload)
        return payload


class TasksController(Controller):
    path = "/tasks"

    @get("")
    async def list_tasks(self) -> list[dict[str, Any]]:
        return store.store.list_tasks()

    @post("")
    async def create_task(self, data: dict[str, Any]) -> dict[str, Any]:
        _ensure_payload_keys(data, ["title", "leadId", "dueAt"])
        task = store.store.create_task(data["title"], data["leadId"], data.get("dealId"), data["dueAt"])
        payload = store.store._task_to_dict(task)  # noqa: SLF001 - local serialization helper
        await events.publish("task.created", payload)
        return payload

    @post("/{task_id:str}/complete")
    async def complete_task(self, task_id: str) -> dict[str, Any]:
        try:
            task = store.store.complete_task(task_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Task not found")
        payload = store.store._task_to_dict(task)  # noqa: SLF001 - local serialization helper
        await events.publish("task.completed", payload)
        return payload


@get("/pipeline")
async def list_pipeline() -> list[dict[str, Any]]:
    return store.store.list_pipeline()


crm_router = Router(
    path="/api/demo/crm",
    route_handlers=[InboxController, MockInboundController, DealsController, TasksController, list_pipeline],
)
