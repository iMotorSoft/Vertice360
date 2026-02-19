from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from backend.modules.vertice360_orquestador_demo import db, services


def _db_ready() -> bool:
    return services.demo_db_ready()


pytestmark = pytest.mark.skipif(
    not _db_ready(),
    reason="Requires DB_PG_V360_URL + psycopg connectivity to v360",
)


def _unique_phone() -> str:
    tail = str(uuid.uuid4().int)[-10:]
    return f"54911{tail}"


def _counts_for_ticket(ticket_id: str) -> dict[str, int]:
    def _tx(conn):
        ticket_row = conn.execute("select count(*) from tickets where id = %s", (ticket_id,)).fetchone()
        message_row = conn.execute(
            "select count(*) from messages where conversation_id = (select conversation_id from tickets where id = %s)",
            (ticket_id,),
        ).fetchone()
        event_row = conn.execute(
            "select count(*) from events where correlation_id = %s",
            (ticket_id,),
        ).fetchone()
        return {
            "tickets": int(ticket_row[0]),
            "messages": int(message_row[0]),
            "events": int(event_row[0]),
        }

    return db.run_in_transaction(_tx)


def test_bootstrap_returns_seed_counts(client):
    response = client.get("/api/demo/vertice360-orquestador/bootstrap")
    assert response.status_code == 200

    payload = response.json()
    assert len(payload.get("projects") or []) == 3
    assert len(payload.get("marketing_assets") or []) == 3
    assert len(payload.get("users") or []) == 2


def test_ingest_message_creates_lead_conversation_ticket_message_event(client):
    response = client.post(
        "/api/demo/vertice360-orquestador/ingest_message",
        json={
            "phone": _unique_phone(),
            "text": "Hola, quiero coordinar visita",
            "source": "whatsapp",
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload.get("ticket_id")
    assert payload.get("lead_id")
    assert payload.get("conversation_id")
    assert payload.get("message_id")
    assert payload.get("lead_created") is True
    assert payload.get("conversation_created") is True
    assert payload.get("ticket_created") is True

    counts = _counts_for_ticket(str(payload["ticket_id"]))
    assert counts["tickets"] == 1
    assert counts["messages"] >= 1
    assert counts["events"] >= 2


def test_dashboard_lists_ticket_with_last_message_snippet(client):
    phone = _unique_phone()
    text = "Necesito informacion de unidades disponibles"

    ingest = client.post(
        "/api/demo/vertice360-orquestador/ingest_message",
        json={"phone": phone, "text": text},
    )
    assert ingest.status_code == 200
    ticket_id = ingest.json()["ticket_id"]

    response = client.get(
        "/api/demo/vertice360-orquestador/dashboard",
        params={"cliente": phone},
    )
    assert response.status_code == 200

    payload = response.json()
    tickets = payload.get("tickets") or []
    target = next((row for row in tickets if row.get("ticket_id") == ticket_id), None)
    assert target is not None
    assert target.get("last_message_snippet")


def test_propose_and_confirm_updates_stage_and_visit_scheduled_at(client):
    ingest = client.post(
        "/api/demo/vertice360-orquestador/ingest_message",
        json={"phone": _unique_phone(), "text": "Quiero agendar visita"},
    )
    assert ingest.status_code == 200
    ticket_id = ingest.json()["ticket_id"]

    option1 = datetime.now(timezone.utc) + timedelta(days=1)
    option2 = datetime.now(timezone.utc) + timedelta(days=2)
    option3 = datetime.now(timezone.utc) + timedelta(days=3)

    propose = client.post(
        "/api/demo/vertice360-orquestador/visit/propose",
        json={
            "ticket_id": ticket_id,
            "message_out": "Te propongo estas fechas para visitar.",
            "mode": "propose",
            "option1": option1.isoformat(),
            "option2": option2.isoformat(),
            "option3": option3.isoformat(),
        },
    )
    assert propose.status_code == 200
    propose_payload = propose.json()
    assert propose_payload.get("stage") == "Esperando confirmación"
    proposal_id = propose_payload.get("proposal_id")
    assert proposal_id

    confirm = client.post(
        "/api/demo/vertice360-orquestador/visit/confirm",
        json={
            "proposal_id": proposal_id,
            "confirmed_option": 1,
            "confirmed_by": "client",
        },
    )
    assert confirm.status_code == 200
    confirm_payload = confirm.json()
    assert confirm_payload.get("stage") == "Visita confirmada"
    assert confirm_payload.get("visit_scheduled_at")


def test_supervisor_send_adds_message_and_event(client):
    ingest = client.post(
        "/api/demo/vertice360-orquestador/ingest_message",
        json={"phone": _unique_phone(), "text": "Necesito ayuda con el asesor"},
    )
    assert ingest.status_code == 200
    ticket_id = ingest.json()["ticket_id"]

    send = client.post(
        "/api/demo/vertice360-orquestador/supervisor/send",
        json={
            "ticket_id": ticket_id,
            "target": "advisor",
            "text": "Por favor tomar este caso prioritario.",
        },
    )
    assert send.status_code == 200
    payload = send.json()
    assert payload.get("message_id")

    def _tx(conn):
        message_row = conn.execute(
            "select count(*) from messages where id = %s and actor = 'supervisor'::actor_role and direction = 'out'",
            (payload["message_id"],),
        ).fetchone()
        event_row = conn.execute(
            "select count(*) from events where correlation_id = %s and name = 'supervisor.message.sent'",
            (ticket_id,),
        ).fetchone()
        return int(message_row[0]), int(event_row[0])

    message_count, event_count = db.run_in_transaction(_tx)
    assert message_count == 1
    assert event_count >= 1
