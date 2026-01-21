from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal


# ----------------------
# Data models (lightweight dataclasses)
# ----------------------


@dataclass
class Message:
    id: str
    conversation_id: str
    sender: Literal["agent", "lead"]
    text: str
    ts: str
    status: Literal["sent", "delivered", "read"] = "sent"


@dataclass
class Conversation:
    id: str
    lead_id: str
    channel: str
    subject: str
    messages: list[Message] = field(default_factory=list)


@dataclass
class Deal:
    id: str
    lead_id: str
    title: str
    stage_id: str
    amount: float
    currency: str


@dataclass
class Task:
    id: str
    title: str
    lead_id: str
    deal_id: str | None
    due_at: str
    status: Literal["open", "completed"] = "open"


@dataclass
class Note:
    id: str
    lead_id: str
    text: str
    created_at: str


@dataclass
class Lead:
    id: str
    name: str
    email: str
    phone: str
    source: str
    tags: list[str] = field(default_factory=list)


def _iso(dt_value: dt.datetime) -> str:
    return dt_value.replace(tzinfo=dt.timezone.utc).isoformat()


def _ts_now() -> str:
    return _iso(dt.datetime.now(dt.UTC))


def _uuid() -> str:
    return str(uuid.uuid4())


class CRMStore:
    """In-memory store for CRM demo entities."""

    def __init__(self) -> None:
        self.leads: dict[str, Lead] = {}
        self.conversations: dict[str, Conversation] = {}
        self.deals: dict[str, Deal] = {}
        self.tasks: dict[str, Task] = {}
        self.notes: dict[str, Note] = {}
        self._seed()

    # --------- seed data ---------
    def _seed(self) -> None:
        lead_a = Lead(
            id="lead-1001",
            name="Maria Lopez",
            email="maria.lopez@example.com",
            phone="+54 9 11 5555-1001",
            source="Web form",
            tags=["premium", "investor"],
        )
        lead_b = Lead(
            id="lead-1002",
            name="Carlos Perez",
            email="carlos.perez@example.com",
            phone="+54 9 11 5555-1002",
            source="Instagram Ads",
            tags=["hot"],
        )

        conv_a = Conversation(
            id="conv-9001",
            lead_id=lead_a.id,
            channel="whatsapp",
            subject="Consulta sobre depto 2 ambientes",
            messages=[],
        )
        conv_a.messages.extend(
            [
                Message(
                    id="msg-1",
                    conversation_id=conv_a.id,
                    sender="lead",
                    text="Hola, me interesa el depto de 2 ambientes en Caballito.",
                    ts=_iso(dt.datetime.now(dt.UTC) - dt.timedelta(minutes=15)),
                    status="read",
                ),
                Message(
                    id="msg-2",
                    conversation_id=conv_a.id,
                    sender="agent",
                    text="Hola Maria! Claro, tenes disponibilidad para una visita virtual manana?",
                    ts=_iso(dt.datetime.now(dt.UTC) - dt.timedelta(minutes=12)),
                    status="delivered",
                ),
            ]
        )

        conv_b = Conversation(
            id="conv-9002",
            lead_id=lead_b.id,
            channel="email",
            subject="Financiacion disponible",
            messages=[],
        )
        conv_b.messages.extend(
            [
                Message(
                    id="msg-3",
                    conversation_id=conv_b.id,
                    sender="lead",
                    text="Hola, ofrecen financiacion para el proyecto Vertice360?",
                    ts=_iso(dt.datetime.now(dt.UTC) - dt.timedelta(hours=2)),
                ),
                Message(
                    id="msg-4",
                    conversation_id=conv_b.id,
                    sender="agent",
                    text="Hola Carlos! Si, contamos con un plan de financiacion en 24 cuotas.",
                    ts=_iso(dt.datetime.now(dt.UTC) - dt.timedelta(hours=1, minutes=55)),
                ),
            ]
        )

        deal_a = Deal(
            id="deal-5001",
            lead_id=lead_a.id,
            title="Venta Depto 2 amb - Caballito",
            stage_id="stage-contacted",
            amount=120000.0,
            currency="USD",
        )
        deal_b = Deal(
            id="deal-5002",
            lead_id=lead_b.id,
            title="Venta Loft - Palermo",
            stage_id="stage-qualification",
            amount=185000.0,
            currency="USD",
        )

        task_a = Task(
            id="task-7001",
            title="Enviar brochure Vertice360",
            lead_id=lead_a.id,
            deal_id=deal_a.id,
            due_at=_iso(dt.datetime.now(dt.UTC) + dt.timedelta(hours=4)),
        )
        task_b = Task(
            id="task-7002",
            title="Coordinar visita virtual",
            lead_id=lead_a.id,
            deal_id=deal_a.id,
            due_at=_iso(dt.datetime.now(dt.UTC) + dt.timedelta(days=1)),
        )

        self.leads = {lead_a.id: lead_a, lead_b.id: lead_b}
        self.conversations = {conv_a.id: conv_a, conv_b.id: conv_b}
        self.deals = {deal_a.id: deal_a, deal_b.id: deal_b}
        self.tasks = {task_a.id: task_a, task_b.id: task_b}
        self.notes = {}

    # --------- helpers ---------
    def list_conversations(self) -> list[dict[str, Any]]:
        return [self._conversation_to_dict(conv) for conv in self.conversations.values()]

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        conv = self.conversations.get(conversation_id)
        return self._conversation_to_dict(conv) if conv else None

    def add_outbound_message(self, conversation_id: str, text: str) -> Message:
        conv = self.conversations.get(conversation_id)
        if not conv:
            raise KeyError("conversation not found")
        message = Message(
            id=_uuid(),
            conversation_id=conversation_id,
            sender="agent",
            text=text,
            ts=_ts_now(),
            status="sent",
        )
        conv.messages.append(message)
        return message

    def add_inbound_message(self, channel: str, conversation_id: str, text: str) -> Message:
        conv = self.conversations.get(conversation_id)
        if not conv:
            raise KeyError("conversation not found")
        message = Message(
            id=_uuid(),
            conversation_id=conversation_id,
            sender="lead",
            text=text,
            ts=_ts_now(),
            status="delivered",
        )
        if channel:
            conv.channel = channel
        conv.messages.append(message)
        return message

    def move_deal(self, deal_id: str, to_stage_id: str) -> Deal:
        deal = self.deals.get(deal_id)
        if not deal:
            raise KeyError("deal not found")
        deal.stage_id = to_stage_id
        return deal

    def list_pipeline(self) -> list[dict[str, Any]]:
        return [self._deal_to_dict(d) for d in self.deals.values()]

    def list_tasks(self) -> list[dict[str, Any]]:
        return [self._task_to_dict(t) for t in self.tasks.values()]

    def create_task(self, title: str, lead_id: str, deal_id: str | None, due_at: str) -> Task:
        task = Task(
            id=_uuid(),
            title=title,
            lead_id=lead_id,
            deal_id=deal_id,
            due_at=due_at,
            status="open",
        )
        self.tasks[task.id] = task
        return task

    def complete_task(self, task_id: str) -> Task:
        task = self.tasks.get(task_id)
        if not task:
            raise KeyError("task not found")
        task.status = "completed"
        return task

    # --------- serialization helpers ---------
    def _conversation_to_dict(self, conv: Conversation) -> dict[str, Any]:
        return {
            "id": conv.id,
            "leadId": conv.lead_id,
            "channel": conv.channel,
            "subject": conv.subject,
            "messages": [self._message_to_dict(m) for m in conv.messages],
        }

    def _message_to_dict(self, msg: Message) -> dict[str, Any]:
        return {
            "id": msg.id,
            "conversationId": msg.conversation_id,
            "sender": msg.sender,
            "text": msg.text,
            "ts": msg.ts,
            "status": msg.status,
        }

    def _deal_to_dict(self, deal: Deal) -> dict[str, Any]:
        return {
            "id": deal.id,
            "leadId": deal.lead_id,
            "title": deal.title,
            "stageId": deal.stage_id,
            "amount": deal.amount,
            "currency": deal.currency,
        }

    def _task_to_dict(self, task: Task) -> dict[str, Any]:
        return {
            "id": task.id,
            "title": task.title,
            "leadId": task.lead_id,
            "dealId": task.deal_id,
            "dueAt": task.due_at,
            "status": task.status,
        }


store = CRMStore()
