from __future__ import annotations

import hashlib
import hmac
import json

from backend import globalVar
from backend.modules.vertice360_ai_workflow_demo import store as ai_store


def test_inbound_webhook_creates_ai_workflow_run(client):
    ai_store.reset_store()
    inbound_text = "Necesito precio y ubicacion para esta semana"
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {
                                "phone_number_id": "123",
                                "display_phone_number": "+5491100000000",
                            },
                            "contacts": [{"wa_id": "+5491111111111"}],
                            "messages": [
                                {
                                    "from": "+5491111111111",
                                    "id": "wamid.bridge.1",
                                    "timestamp": "1710000300",
                                    "text": {"body": inbound_text},
                                    "type": "text",
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }

    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if globalVar.META_APP_SECRET_IMOTORSOFT:
        signature = "sha256=" + hmac.new(
            globalVar.META_APP_SECRET_IMOTORSOFT.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
        headers["X-Hub-Signature-256"] = signature

    response = client.post("/webhooks/messaging/meta/whatsapp", content=body, headers=headers)
    assert response.status_code == 201
    assert response.json().get("ok") is True

    response = client.get("/api/demo/vertice360-ai-workflow/runs")
    assert response.status_code == 200
    runs = response.json()
    assert runs

    matching = [run for run in runs if inbound_text in (run.get("input") or "")]
    assert matching
    output = matching[0].get("output") or {}
    assert output.get("responseText")
