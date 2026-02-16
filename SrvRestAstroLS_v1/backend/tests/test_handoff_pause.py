from __future__ import annotations

import asyncio

from backend.modules.vertice360_workflow_demo import services, store


def test_handoff_required_pauses_auto_reply(event_recorder, mock_meta_send) -> None:
    ticket = asyncio.run(
        store.create_or_get_ticket_from_inbound(
            {
                "ticketId": "VTX-HANDOFF-01",
                "provider": "meta_whatsapp",
                "channel": "whatsapp",
                "customer": {
                    "from": "+5491112340002",
                    "to": "+5491100000000",
                    "provider": "meta_whatsapp",
                    "channel": "whatsapp",
                },
                "subject": "Handoff pause",
            }
        )
    )
    store.set_handoff_required(ticket["ticketId"], True, "schedule_visit")

    result = asyncio.run(
        services.process_inbound_message(
            {
                "ticketId": "VTX-HANDOFF-01",
                "provider": "meta_whatsapp",
                "channel": "whatsapp",
                "from": "+5491112340002",
                "to": "+5491100000000",
                "messageId": "wamid.handoff.pause.1",
                "text": "Hola, sigo por acá",
                "timestamp": 1711111112000,
                "mediaCount": 0,
            }
        )
    )

    assert "HANDOFF_WAITING_OPERATOR" in (result.get("actions") or [])
    assert len(mock_meta_send) == 0

    event_names = [event.get("name") for event in event_recorder]
    assert "messaging.inbound" in event_names
    assert "human.action_required" in event_names
    assert "messaging.outbound" not in event_names


def test_handoff_operator_engaged_stage_pauses_auto_reply(event_recorder, mock_meta_send) -> None:
    ticket = asyncio.run(
        store.create_or_get_ticket_from_inbound(
            {
                "ticketId": "VTX-HANDOFF-02",
                "provider": "meta_whatsapp",
                "channel": "whatsapp",
                "customer": {
                    "from": "+5491112340003",
                    "to": "+5491100000000",
                    "provider": "meta_whatsapp",
                    "channel": "whatsapp",
                },
                "subject": "Handoff engaged pause",
            }
        )
    )
    store.set_handoff_stage(ticket["ticketId"], "operator_engaged", "Laura")
    # Defensive: ensure stage pause logic is used even if required flag drifts.
    store.tickets[ticket["ticketId"]]["handoffRequired"] = False

    result = asyncio.run(
        services.process_inbound_message(
            {
                "ticketId": "VTX-HANDOFF-02",
                "provider": "meta_whatsapp",
                "channel": "whatsapp",
                "from": "+5491112340003",
                "to": "+5491100000000",
                "messageId": "wamid.handoff.pause.2",
                "text": "¿Hay novedades?",
                "timestamp": 1711111113000,
                "mediaCount": 0,
            }
        )
    )

    assert "HANDOFF_WAITING_OPERATOR" in (result.get("actions") or [])
    assert len(mock_meta_send) == 0
