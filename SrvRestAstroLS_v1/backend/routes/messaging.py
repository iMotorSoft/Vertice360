from typing import Dict, Any
import hashlib
import hmac
import json
import time
import uuid

from litestar import Router, post, get, Controller, Request
from litestar.exceptions import HTTPException
from litestar.response import Response
from litestar.enums import MediaType

import globalVar
from backend.modules.messaging.providers.meta.whatsapp import send_message
from backend.modules.messaging.providers.meta.whatsapp.mapper import (
    extract_inbound_messages,
    extract_status_updates,
)
from backend.modules.agui_stream import broadcaster
from backend.modules.vertice360_workflow_demo.services import process_inbound_message

class MessagingController(Controller):
    path = "/api/v1/messaging"
    tags = ["Messaging"]
    
    # Placeholder for future V1 endpoints
    # @post("/send")
    # async def send_v1(self, data: Dict[str, Any]) -> Dict[str, Any]:
    #     ...

class DemoMessagingController(Controller):
    path = "/api/demo/messaging"
    tags = ["Demo Messaging"]

    @post("/meta/whatsapp/send")
    async def send_whatsapp_demo(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Demo endpoint to send a WhatsApp message via Meta Cloud API.
        Body: {"to": "...", "text": "..."}
        """
        to = data.get("to")
        text = data.get("text")
        
        if not to or not text:
            return {"error": "Missing 'to' or 'text' in body"}

        # 1. Send via Provider
        result = await send_message(to, text)
        
        # 2. Broadcast event to AG-UI stream (if success or attempt)
        # We broadcast the result so the frontend can show it.
        await broadcaster.publish(
            "messaging.outbound",
            {
                "provider": "meta",
                "service": "whatsapp",
                "to": to,
                "text": text,
                "result": result
            }
        )

        return result


def _epoch_ms() -> int:
    return int(time.time() * 1000)


def _to_epoch_ms(value: str | int | None) -> int:
    if value is None:
        return _epoch_ms()
    try:
        ts = int(value)
    except (TypeError, ValueError):
        return _epoch_ms()
    if ts < 10**12:
        ts *= 1000
    return ts


def _custom_event(name: str, value: Dict[str, Any], correlation_id: str | None) -> Dict[str, Any]:
    return {
        "type": "CUSTOM",
        "timestamp": _epoch_ms(),
        "name": name,
        "value": value,
        "correlationId": correlation_id or str(uuid.uuid4()),
    }


def _compact_value(value: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if item not in (None, "", [], {})
    }


class MetaWhatsAppWebhookController(Controller):
    path = "/webhooks/messaging/meta/whatsapp"
    tags = ["Messaging Webhooks"]

    @get()
    async def verify_webhook(self, request: Request) -> Response:
        params = request.query_params
        mode = params.get("hub.mode")
        token = params.get("hub.verify_token")
        challenge = params.get("hub.challenge")

        if mode == "subscribe" and token == globalVar.META_VERTICE360_VERIFY_TOKEN:
            return Response(content=challenge or "", media_type=MediaType.TEXT)
        
        raise HTTPException(status_code=403, detail="Forbidden")

    @post()
    async def receive_webhook(self, request: Request) -> Dict[str, Any]:
        print("\n" + "="*40)
        print(f"DEBUG: Webhook POST received at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"DEBUG: Remote IP: {request.client.host if request.client else 'Unknown'}")
        
        raw_body = await request.body()
        body_str = raw_body.decode('utf-8')
        print(f"DEBUG: Raw Body: {body_str}")
        print(f"DEBUG: Headers: {dict(request.headers)}")

        try:
            payload = json.loads(body_str)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            print(f"DEBUG: JSON Parse Error: {exc}")
            raise HTTPException(status_code=400, detail="Invalid JSON") from exc

        app_secret = globalVar.META_APP_SECRET_IMOTORSOFT
        signature = request.headers.get("X-Hub-Signature-256")
        
        print(f"DEBUG: App Secret exists: {bool(app_secret)}")
        print(f"DEBUG: signature header: {signature}")

        if app_secret and signature:
            expected = "sha256=" + hmac.new(
                app_secret.encode("utf-8"), raw_body, hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(expected, signature):
                print(f"DEBUG: SIG FAIL! Expected: {expected} | Received: {signature}")
                raise HTTPException(status_code=403, detail="Invalid signature")
            print("DEBUG: SIG OK")
        elif not signature:
            print("DEBUG: WARNING - No signature header found in request.")

        inbound_messages = extract_inbound_messages(payload)
        status_updates = extract_status_updates(payload)
        
        print(f"DEBUG: Inbound messages found: {len(inbound_messages)}")
        print(f"DEBUG: Status updates found: {len(status_updates)}")

        for message in inbound_messages:
            value = _compact_value(
                {
                    "provider": "meta",
                    "service": "whatsapp",
                    "wa_id": message.get("wa_id"),
                    "from": message.get("from"),
                    "to": message.get("to"),
                    "text": message.get("text"),
                    "timestamp": message.get("timestamp"),
                    "message_id": message.get("message_id"),
                    "media_count": message.get("media_count"),
                    "raw": message.get("raw"),
                }
            )
            print(f"DEBUG: Broadcasting inbound message from {value.get('from')}")
            wf_inbound = {
                "provider": "meta_whatsapp",
                "channel": "whatsapp",
                "from": message.get("from") or message.get("wa_id") or "",
                "to": message.get("to") or "",
                "messageId": message.get("message_id") or "",
                "text": message.get("text") or "",
                "timestamp": _to_epoch_ms(message.get("timestamp")),
                "mediaCount": message.get("media_count") or 0,
            }
            ticket_id = None
            try:
                wf_result = await process_inbound_message(wf_inbound)
                ticket_id = wf_result.get("ticketId")
            except Exception as exc:  # noqa: BLE001 - best-effort webhook
                ticket_id = wf_inbound.get("ticketId")
                print(
                    "ERROR: workflow demo inbound failed",
                    {
                        "message_id": message.get("message_id"),
                        "from": message.get("from"),
                        "error": str(exc),
                    },
                )
                error_value = _compact_value(
                    {
                        "ticketId": ticket_id,
                        "messageId": message.get("message_id"),
                        "from": message.get("from"),
                        "error": str(exc),
                    }
                )
                correlation_id = ticket_id or "workflow"
                await broadcaster.publish(
                    "workflow.error",
                    _custom_event("workflow.error", error_value, correlation_id),
                )

            await broadcaster.publish(
                "messaging.inbound.raw",
                _custom_event("messaging.inbound.raw", value, message.get("message_id")),
            )

        for status in status_updates:
            value = _compact_value(
                {
                    "provider": "meta",
                    "service": "whatsapp",
                    "wa_id": status.get("wa_id"),
                    "message_id": status.get("message_id"),
                    "status": status.get("status"),
                    "timestamp": status.get("timestamp"),
                    "raw": status.get("raw"),
                }
            )
            await broadcaster.publish(
                "messaging.status",
                _custom_event("messaging.status", value, status.get("message_id")),
            )

        return {"ok": True}


messaging_router = Router(
    path="/",
    route_handlers=[MessagingController, DemoMessagingController, MetaWhatsAppWebhookController]
)
