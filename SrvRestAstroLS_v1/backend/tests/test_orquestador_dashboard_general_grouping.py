from __future__ import annotations

from typing import Any

from backend.modules.vertice360_orquestador_demo import services


def _wire_dashboard_stubs(monkeypatch, rows: list[dict[str, Any]]) -> None:
    monkeypatch.setattr(services.repo, "get_dashboard_ticket_rows", lambda conn, cliente: rows)
    monkeypatch.setattr(services.repo, "get_dashboard_kpis", lambda conn: {})
    monkeypatch.setattr(services.repo, "find_cliente_activo", lambda conn, cliente: None)

    def run_in_transaction(callback):
        return callback(object())

    monkeypatch.setattr(services.db, "run_in_transaction", run_in_transaction)


def test_dashboard_general_grouping_stable(monkeypatch) -> None:
    rows = [
        {
            "ticket_id": "T-1",
            "project_code": None,
            "project_name": None,
            "ticket_inbound_line_key": "gupshup:4526325251",
            "ticket_inbound_line_phone": "+4526325251",
            "last_message_text": "hola",
            "stage": "Nuevo",
            "phone_e164": "+5491111111111",
        },
        {
            "ticket_id": "T-2",
            "project_code": None,
            "project_name": None,
            "ticket_inbound_line_key": "gupshup:4526325250",
            "ticket_inbound_line_phone": "+4526325250",
            "last_message_text": "hola",
            "stage": "Nuevo",
            "phone_e164": "+5491222222222",
        },
        {
            "ticket_id": "T-3",
            "project_code": None,
            "project_name": None,
            "ticket_inbound_line_key": "gupshup:4526325251",
            "ticket_inbound_line_phone": "+4526325251",
            "last_message_text": "hola",
            "stage": "En seguimiento",
            "phone_e164": "+5491333333333",
        },
    ]
    _wire_dashboard_stubs(monkeypatch, rows)

    payload = services.dashboard(cliente=None)
    tickets = payload.get("tickets") or []

    by_ticket_id = {row.get("ticket_id"): row for row in tickets}
    assert by_ticket_id["T-2"].get("project_label") == "General 1"
    assert by_ticket_id["T-1"].get("project_label") == "General 2"
    assert by_ticket_id["T-3"].get("project_label") == "General 2"


def test_dashboard_project_label_for_real_projects(monkeypatch) -> None:
    rows = [
        {
            "ticket_id": "T-10",
            "project_code": "BULNES_966_ALMAGRO",
            "project_name": "Bulnes 966",
            "ticket_inbound_line_key": "gupshup:4526325250",
            "ticket_inbound_line_phone": "+4526325250",
            "last_message_text": "hola",
            "stage": "Nuevo",
            "phone_e164": "+5491444444444",
        }
    ]
    _wire_dashboard_stubs(monkeypatch, rows)

    payload = services.dashboard(cliente=None)
    tickets = payload.get("tickets") or []

    assert len(tickets) == 1
    assert tickets[0].get("project_label") == "BULNES_966_ALMAGRO"
