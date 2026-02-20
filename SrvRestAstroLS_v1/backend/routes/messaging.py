from typing import Dict, Any
import hashlib
import hmac
import json
import logging
import time
import unicodedata
import uuid

from litestar import Router, post, get, Controller, Request
from litestar.exceptions import HTTPException
from litestar.response import Response
from litestar.enums import MediaType

import globalVar
from backend.modules.messaging.providers.meta.whatsapp import MetaWhatsAppSendError, send_text_message
from backend.modules.messaging.providers.meta.whatsapp.mapper import (
    extract_inbound_messages,
    extract_status_updates,
)
from backend.modules.messaging.providers.gupshup.whatsapp.client import (
    GupshupConfig,
    GupshupHTTPError,
    GupshupWhatsAppClient,
)
from backend.modules.messaging.providers.gupshup.whatsapp.service import (
    GupshupWhatsAppSendError,
    GupshupWhatsAppService,
)
from backend.modules.messaging.providers.gupshup.whatsapp.mapper import (
    parse_inbound as gupshup_parse_inbound,
    parse_status as gupshup_parse_status,
)
from backend.modules.messaging.providers.registry import normalize_provider
from backend.modules.agui_stream import broadcaster
from backend.modules.vertice360_ai_workflow_demo.bridge import maybe_start_ai_workflow_from_inbound
from backend.modules.vertice360_workflow_demo.services import process_inbound_message
from backend.modules.vertice360_workflow_demo import events as workflow_events
from backend.modules.vertice360_workflow_demo import store as workflow_store

logger = logging.getLogger(__name__)


class MessagingController(Controller):
    path = "/api/v1/messaging"
    tags = ["Messaging"]
    
    # Placeholder for future V1 endpoints
    # @post("/send")
    # async def send_v1(self, data: Dict[str, Any]) -> Dict[str, Any]:
    #     ...


def _normalize_for_match(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(stripped.lower().split())


def _operator_intro(operator_name: str) -> str:
    return f"Hola, soy {operator_name}, del equipo de visitas de Vértice360.\n"


def _with_operator_intro(text: str, operator_name: str) -> str:
    clean_text = str(text or "").strip()
    if not clean_text:
        return _operator_intro(operator_name)
    normalized = _normalize_for_match(clean_text)
    if "hola, soy" in normalized and "equipo de visitas de vertice360" in normalized:
        return clean_text
    return f"{_operator_intro(operator_name)}{clean_text}"


def _extract_gupshup_inbound_text(payload: dict[str, Any]) -> str:
    body = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    body_type = str(body.get("type") or "").strip().lower()
    if body_type != "text":
        return ""

    nested = body.get("payload")
    if isinstance(nested, dict):
        text = nested.get("text") or nested.get("body")
    else:
        text = body.get("text") or body.get("body")
    return str(text or "").strip()


async def _send_whatsapp_unified_payload(provider: str, to: str, text: str) -> tuple[int, Dict[str, Any]]:
    resolved_provider = normalize_provider(provider)

    if resolved_provider == "gupshup":
        config = GupshupConfig.from_env()
        env_debug = {
            "has_api_key": bool(config.api_key),
            "has_app_name": bool(config.app_name),
            "has_sender": bool(config.sender_e164),
            "sender": config.sender_e164,
            "base_url": config.base_url,
        }
        if not globalVar.gupshup_whatsapp_enabled():
            payload = {
                "ok": False,
                "provider": "gupshup",
                "vera_send_ok": False,
                "error": {
                    "type": "GupshupConfigError",
                    "message": "Gupshup WhatsApp not configured (missing env vars)",
                    "upstream_status": None,
                    "upstream_body": "Missing required env vars: "
                    + ", ".join(_missing_gupshup_env_keys(env_debug)),
                    "url": None,
                },
                "env": env_debug,
            }
            return 502, payload

        client = GupshupWhatsAppClient(config)
        service = GupshupWhatsAppService(client)
        try:
            ack = await service.send_text_message(to, text)
            message_id = str(ack.provider_message_id or f"gs-{uuid.uuid4().hex[:12]}")
            return 200, {
                "ok": True,
                "provider": "gupshup",
                "message_id": message_id,
                "raw": ack.raw,
            }
        except (GupshupWhatsAppSendError, GupshupHTTPError, ValueError, Exception) as exc:
            payload = {
                "ok": False,
                "provider": "gupshup",
                "error": _build_gupshup_error_payload(exc),
                "env": env_debug,
            }
            return 502, payload

    try:
        raw = await send_text_message(to, text)
    except MetaWhatsAppSendError as exc:
        return 502, {"ok": False, "provider": "meta", "error": _build_meta_error_payload(exc)}
    except ValueError as exc:
        return 502, {"ok": False, "provider": "meta", "error": _build_meta_error_payload(exc)}
    except Exception as exc:  # noqa: BLE001 - explicit payload for demo diagnostics
        return 502, {"ok": False, "provider": "meta", "error": _build_meta_error_payload(exc)}

    message_id = _extract_provider_message_id(raw) or f"meta-{uuid.uuid4().hex[:12]}"
    return 200, {"ok": True, "provider": "meta", "message_id": message_id, "raw": raw}


async def _emit_generic_outbound(provider: str, to: str, text: str, result: Dict[str, Any], correlation_id: str | None = None) -> None:
    value = _compact_value(
        {
            "provider": provider,
            "service": "whatsapp",
            "to": to,
            "text": text,
            "message_id": result.get("message_id"),
            "result": result,
        }
    )
    await broadcaster.publish(
        "messaging.outbound",
        _custom_event("messaging.outbound", value, correlation_id or result.get("message_id")),
    )


def _workflow_provider(provider: str) -> str:
    return "gupshup_whatsapp" if provider == "gupshup" else "meta_whatsapp"


class DemoMessagingController(Controller):
    path = "/api/demo/messaging"
    tags = ["Demo Messaging"]

    async def _send_gupshup_whatsapp(self, to: str, text: str) -> Response:
        status_code, result = await _send_whatsapp_unified_payload("gupshup", to, text)
        if status_code != 200:
            return Response(status_code=status_code, content=result, media_type=MediaType.JSON)
        await _emit_generic_outbound("gupshup", to, text, result)
        return Response(status_code=200, content=result, media_type=MediaType.JSON)

    @post("/whatsapp/send", status_code=200)
    async def send_whatsapp_unified_demo(self, data: Dict[str, Any]) -> Response:
        """
        Unified demo endpoint for WhatsApp sends across providers.
        Body: {"provider":"meta|gupshup","to":"...","text":"..."}
        """
        provider = normalize_provider(data.get("provider"))
        to = data.get("to")
        text = data.get("text")

        if not to or not text:
            raise HTTPException(status_code=400, detail="Missing 'to' or 'text' in body")

        if provider == "gupshup":
            return await self._send_gupshup_whatsapp(to, text)

        status_code, result = await _send_whatsapp_unified_payload(provider, to, text)
        if status_code != 200:
            return Response(status_code=status_code, content=result, media_type=MediaType.JSON)
        await _emit_generic_outbound("meta", to, text, result)
        return Response(status_code=200, content=result, media_type=MediaType.JSON)

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
        try:
            result = await send_text_message(to, text)
        except MetaWhatsAppSendError as exc:
            result = {"status": "error", "status_code": exc.status_code, "response": exc.err}
        except ValueError as exc:
            result = {"status": "error", "response": str(exc)}
        
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

    @post("/gupshup/whatsapp/send", status_code=200)
    async def send_gupshup_whatsapp_demo(self, data: Dict[str, Any]) -> Response:
        """
        Demo endpoint to send a WhatsApp message via Gupshup.
        Body: {"to": "...", "text": "..."}
        """
        to = data.get("to")
        text = data.get("text")

        if not to or not text:
            raise HTTPException(status_code=400, detail="Missing 'to' or 'text' in body")
        return await self._send_gupshup_whatsapp(to, text)


class OperatorWorkflowController(Controller):
    path = "/api/demo/workflow/operator"
    tags = ["Demo Workflow Operator"]

    @post("/send_whatsapp", status_code=200)
    async def send_whatsapp(self, data: Dict[str, Any]) -> Response:
        provider = normalize_provider(data.get("provider"))
        to = str(data.get("to") or "").strip()
        text = str(data.get("text") or "").strip()
        operator_name = str(data.get("operator_name") or "").strip()
        ticket_id = str(data.get("ticket_id") or data.get("ticketId") or "").strip() or None

        if not to or not text or not operator_name:
            raise HTTPException(status_code=400, detail="Missing 'to', 'text' or 'operator_name' in body")

        outbound_text = _with_operator_intro(text, operator_name)
        status_code, result = await _send_whatsapp_unified_payload(provider, to, outbound_text)
        if status_code != 200:
            return Response(status_code=status_code, content=result, media_type=MediaType.JSON)

        resolved_provider = result.get("provider") or provider or "meta"
        message_id = str(result.get("message_id") or f"operator-{uuid.uuid4().hex[:12]}")
        result["message_id"] = message_id

        if ticket_id:
            ticket = workflow_store.tickets.get(ticket_id)
            if ticket:
                channel = ticket.get("channel") or "whatsapp"
                workflow_provider = ticket.get("provider") or _workflow_provider(str(resolved_provider))
                await workflow_events.emit_messaging_outbound(
                    ticket_id=ticket_id,
                    provider=workflow_provider,
                    channel=channel,
                    messageId=message_id,
                    to=to,
                    text=outbound_text,
                    sentAt=_epoch_ms(),
                )
                workflow_store.add_message(
                    ticket_id,
                    {
                        "direction": "outbound",
                        "provider": workflow_provider,
                        "channel": channel,
                        "messageId": message_id,
                        "text": outbound_text,
                        "at": _epoch_ms(),
                        "mediaCount": 0,
                        "operatorName": operator_name,
                    },
                )
                workflow_store.set_handoff_stage(ticket_id, "operator_engaged", operator_name)
            else:
                await _emit_generic_outbound(
                    str(resolved_provider),
                    to,
                    outbound_text,
                    result,
                    correlation_id=ticket_id,
                )
        else:
            await _emit_generic_outbound(str(resolved_provider), to, outbound_text, result)

        payload = {
            "ok": True,
            "provider": resolved_provider,
            "message_id": message_id,
            "raw": result.get("raw"),
        }
        return Response(status_code=200, content=payload, media_type=MediaType.JSON)


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


def _missing_gupshup_env_keys(env_debug: Dict[str, Any]) -> list[str]:
    missing = []
    if not env_debug.get("has_api_key"):
        missing.append("GUPSHUP_API_KEY")
    if not env_debug.get("has_app_name"):
        missing.append("GUPSHUP_APP_NAME")
    if not env_debug.get("has_sender"):
        missing.append("GUPSHUP_WA_SENDER")
    return missing


def _truncate_error_text(text: str | None) -> str | None:
    if text is None:
        return None
    if len(text) <= 2000:
        return text
    return f"{text[:2000]}... [truncated]"


def _build_gupshup_error_payload(exc: Exception) -> Dict[str, Any]:
    upstream_status = getattr(exc, "upstream_status", None)
    if upstream_status is None:
        upstream_status = getattr(exc, "status_code", None)
    if isinstance(upstream_status, str) and upstream_status.isdigit():
        upstream_status = int(upstream_status)
    if not isinstance(upstream_status, int):
        upstream_status = None

    upstream_body = getattr(exc, "upstream_body", None)
    if upstream_body is None:
        upstream_body = getattr(exc, "response_text", None)
    if upstream_body is None:
        upstream_body = str(exc)

    url = getattr(exc, "url", None)
    if url is not None:
        url = str(url)

    return {
        "type": exc.__class__.__name__,
        "message": str(exc),
        "upstream_status": upstream_status,
        "upstream_body": _truncate_error_text(upstream_body),
        "url": url,
    }


def _extract_provider_message_id(raw: Dict[str, Any]) -> str:
    messages = raw.get("messages")
    if isinstance(messages, list) and messages:
        message_id = messages[0].get("id")
        if message_id:
            return str(message_id)
    message_id = raw.get("message_id") or raw.get("messageId") or raw.get("id")
    return str(message_id) if message_id else ""


def _meta_messages_url() -> str:
    return (
        f"https://graph.facebook.com/{globalVar.META_GRAPH_VERSION}/"
        f"{globalVar.META_VERTICE360_PHONE_NUMBER_ID}/messages"
    )


def _build_meta_error_payload(exc: Exception) -> Dict[str, Any]:
    upstream_status = getattr(exc, "status_code", None)
    if not isinstance(upstream_status, int):
        upstream_status = None

    err_body = getattr(exc, "err", None)
    if err_body is None:
        err_body = str(exc)

    message = str(exc)
    if isinstance(err_body, dict):
        maybe_message = (
            err_body.get("error", {}).get("message")
            if isinstance(err_body.get("error"), dict)
            else err_body.get("message")
        )
        if isinstance(maybe_message, str) and maybe_message.strip():
            message = maybe_message.strip()

    if isinstance(err_body, str):
        upstream_body = err_body
    else:
        try:
            upstream_body = json.dumps(err_body, ensure_ascii=False)
        except (TypeError, ValueError):
            upstream_body = str(err_body)

    return {
        "type": exc.__class__.__name__,
        "message": message,
        "upstream_status": upstream_status,
        "upstream_body": _truncate_error_text(upstream_body),
        "url": _meta_messages_url(),
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

        tenant_ctx = {
            "tenant_id": request.scope.get("tenant_id"),
            "tenant_host": request.scope.get("tenant_host"),
        }
        if not tenant_ctx["tenant_id"] and not tenant_ctx["tenant_host"]:
            tenant_ctx = None
        
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
                ai_result = await maybe_start_ai_workflow_from_inbound(message, broadcaster, tenant_ctx)
                if ai_result and ai_result.get("responseText"):
                    wf_inbound["aiResponseText"] = ai_result["responseText"]
                if ai_result and ai_result.get("decision"):
                    wf_inbound["aiDecision"] = ai_result["decision"]
                if ai_result and ai_result.get("handoffRequired") is not None:
                    wf_inbound["aiHandoffRequired"] = bool(ai_result.get("handoffRequired"))
                if ai_result and isinstance(ai_result.get("humanActionRequired"), dict):
                    wf_inbound["humanActionRequired"] = ai_result["humanActionRequired"]
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


class GupshupWhatsAppWebhookController(Controller):
    path = "/webhooks/messaging/gupshup/whatsapp"
    tags = ["Messaging Webhooks"]

    @post()
    async def receive_webhook(self, request: Request) -> Dict[str, Any]:
        received_at_ms = _to_epoch_ms(None)
        raw_body = await request.body()
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON") from exc

        event_type = str(payload.get("type") or "").strip().lower()
        gupshup_app = str(payload.get("app") or "").strip() or None
        logger.info(
            "GUPSHUP_WEBHOOK_RECEIVED received_at_ms=%s remote_ip=%s event_type=%s app=%s",
            received_at_ms,
            request.client.host if request.client else "-",
            event_type or "-",
            gupshup_app or "-",
        )
        if event_type != "message":
            logger.info("GUPSHUP_WEBHOOK ignored event_type=%s reason=non_inbound", event_type or "-")
            return {"ok": True}

        inbound_text = _extract_gupshup_inbound_text(payload)
        if not inbound_text:
            payload_type = ""
            if isinstance(payload.get("payload"), dict):
                payload_type = str(payload["payload"].get("type") or "").strip().lower()
            logger.info(
                "GUPSHUP_WEBHOOK ignored event_type=%s payload_type=%s reason=non_text_or_empty",
                event_type,
                payload_type or "-",
            )
            return {"ok": True}

        inbound_messages = gupshup_parse_inbound(payload)
        status_updates = gupshup_parse_status(payload)

        for message in inbound_messages:
            message_id = message.message_id or f"gupshup-noid-{uuid.uuid4().hex[:8]}"
            correlation_id = f"gupshup_whatsapp:{message_id}"
            value = _compact_value(
                {
                    "provider": message.provider,
                    "service": message.service,
                    "wa_id": message.wa_id,
                    "from": message.from_,
                    "to": message.to,
                    "text": message.text,
                    "timestamp": message.timestamp,
                    "message_id": message_id,
                    "raw": message.raw,
                }
            )

            ticket_id = None
            sanitized_from = "".join(filter(str.isdigit, message.from_ or message.wa_id or ""))
            sanitized_to = "".join(filter(str.isdigit, message.to or ""))

            wf_inbound = {
                "provider": "gupshup_whatsapp",
                "app": gupshup_app,
                "channel": "whatsapp",
                "from": sanitized_from,
                "to": sanitized_to,
                "messageId": message_id,
                "text": message.text or "",
                "timestamp": _to_epoch_ms(message.timestamp),
                "mediaCount": 0,
            }
            logger.info(
                "GUPSHUP_INBOUND_ACCEPTED correlation_id=%s received_at_ms=%s message_id=%s user_phone=%s",
                correlation_id,
                wf_inbound["timestamp"],
                message_id,
                sanitized_from,
            )

            try:
                wf_started_at = time.perf_counter()
                wf_result = await process_inbound_message(wf_inbound)
                workflow_ms = int((time.perf_counter() - wf_started_at) * 1000)
                ticket_id = wf_result.get("ticketId")
                logger.info(
                    "GUPSHUP_INBOUND_PROCESSED correlation_id=%s ticket_id=%s workflow_ms=%s duplicate=%s actions=%s",
                    correlation_id,
                    ticket_id or "-",
                    workflow_ms,
                    bool(wf_result.get("duplicate")),
                    wf_result.get("actions") or [],
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "GUPSHUP_INBOUND_FAILED correlation_id=%s message_id=%s user_phone=%s error=%s",
                    correlation_id,
                    message_id,
                    sanitized_from,
                    exc,
                )
                error_value = _compact_value(
                    {
                        "ticketId": wf_inbound.get("ticketId"),
                        "messageId": message_id,
                        "from": message.from_,
                        "error": str(exc),
                    }
                )
                await broadcaster.publish(
                    "workflow.error",
                    _custom_event("workflow.error", error_value, ticket_id or "workflow"),
                )

            await broadcaster.publish(
                "messaging.inbound",
                _custom_event("messaging.inbound", value, message_id),
            )
            await broadcaster.publish(
                "messaging.inbound.raw",
                _custom_event("messaging.inbound.raw", value, message_id),
            )

        for status in status_updates:
            value = _compact_value(
                {
                    "provider": status.provider,
                    "service": status.service,
                    "message_id": status.message_id,
                    "status": status.status,
                    "timestamp": status.timestamp,
                    "raw": status.raw,
                }
            )
            await broadcaster.publish(
                "messaging.status",
                _custom_event("messaging.status", value, status.message_id),
            )

        return {"ok": True}


messaging_router = Router(
    path="/",
    route_handlers=[
        MessagingController,
        DemoMessagingController,
        OperatorWorkflowController,
        MetaWhatsAppWebhookController,
        GupshupWhatsAppWebhookController,
    ],
)
