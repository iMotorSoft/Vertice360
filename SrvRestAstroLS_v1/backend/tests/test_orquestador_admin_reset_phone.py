from __future__ import annotations

import uuid

import pytest

from backend import globalVar
from backend.modules.vertice360_orquestador_demo import db, repo, services


def _db_ready() -> bool:
    return services.demo_db_ready()


pytestmark = pytest.mark.skipif(
    not _db_ready(),
    reason="Requires DB_PG_V360_URL + psycopg connectivity to v360",
)


def _unique_phone_e164() -> str:
    tail = str(uuid.uuid4().int)[-10:]
    return f"+54911{tail}"


def _counts_for_phone(phone_e164: str) -> dict[str, int]:
    def _tx(conn):
        lead_row = conn.execute(
            "select count(*) from leads where phone_e164 = %s",
            (phone_e164,),
        ).fetchone()
        conversation_row = conn.execute(
            """
            select count(*)
            from conversations c
            join leads l on l.id = c.lead_id
            where l.phone_e164 = %s
            """,
            (phone_e164,),
        ).fetchone()
        ticket_row = conn.execute(
            """
            select count(*)
            from tickets t
            join leads l on l.id = t.lead_id
            where l.phone_e164 = %s
            """,
            (phone_e164,),
        ).fetchone()
        message_row = conn.execute(
            """
            select count(*)
            from messages m
            join leads l on l.id = m.lead_id
            where l.phone_e164 = %s
            """,
            (phone_e164,),
        ).fetchone()
        proposal_row = conn.execute(
            """
            select count(*)
            from visit_proposals vp
            join tickets t on t.id = vp.ticket_id
            join leads l on l.id = t.lead_id
            where l.phone_e164 = %s
            """,
            (phone_e164,),
        ).fetchone()
        confirmation_row = conn.execute(
            """
            select count(*)
            from visit_confirmations vc
            join tickets t on t.id = vc.ticket_id
            join leads l on l.id = t.lead_id
            where l.phone_e164 = %s
            """,
            (phone_e164,),
        ).fetchone()
        event_row = conn.execute(
            """
            select count(*)
            from events e
            join tickets t on e.correlation_id::text = t.id::text
            join leads l on l.id = t.lead_id
            where l.phone_e164 = %s
            """,
            (phone_e164,),
        ).fetchone()
        return {
            "leads": int(lead_row[0]),
            "conversations": int(conversation_row[0]),
            "tickets": int(ticket_row[0]),
            "messages": int(message_row[0]),
            "visit_proposals": int(proposal_row[0]),
            "visit_confirmations": int(confirmation_row[0]),
            "events": int(event_row[0]),
        }

    return db.run_in_transaction(_tx)


def _cleanup_phone(phone_e164: str) -> None:
    def _tx(conn):
        repo.reset_by_phone(conn, phone_e164)

    db.run_in_transaction(_tx)


def test_admin_reset_phone_deletes_orquestador_data(client, monkeypatch) -> None:
    monkeypatch.setenv("VERTICE360_ENV", "dev")
    monkeypatch.setenv("V360_ADMIN_TOKEN", "test")
    monkeypatch.setattr(globalVar, "ENVIRONMENT", "dev", raising=False)
    monkeypatch.setattr(globalVar, "RUN_ENV", "dev", raising=False)
    monkeypatch.setattr(globalVar, "V360_ADMIN_TOKEN", "test", raising=False)

    phone = _unique_phone_e164()

    try:
        ingest = client.post(
            "/api/demo/vertice360-orquestador/ingest_message",
            json={"phone": phone, "text": "Hola, quiero informacion"},
        )
        assert ingest.status_code == 200

        before = _counts_for_phone(phone)
        assert before["leads"] == 1
        assert before["conversations"] == 1
        assert before["tickets"] == 1
        assert before["messages"] >= 1
        assert before["events"] >= 2

        response = client.post(
            "/api/demo/vertice360-orquestador/admin/reset_phone",
            json={"phone": phone},
            headers={"x-v360-admin-token": "test"},
        )
        assert response.status_code == 200

        payload = response.json()
        assert payload.get("ok") is True
        assert payload.get("phone") == phone
        assert payload.get("deleted") == {
            "events": before["events"],
            "visit_confirmations": 0,
            "visit_proposals": 0,
            "messages": before["messages"],
            "tickets": 1,
            "conversations": 1,
            "leads": 1,
        }

        after = _counts_for_phone(phone)
        assert after == {
            "leads": 0,
            "conversations": 0,
            "tickets": 0,
            "messages": 0,
            "visit_proposals": 0,
            "visit_confirmations": 0,
            "events": 0,
        }
    finally:
        _cleanup_phone(phone)
