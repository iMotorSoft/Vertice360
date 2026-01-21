from __future__ import annotations

from typing import Any

from backend.modules.vertice360_ai_workflow_demo import services
from backend.modules.vertice360_ai_workflow_demo.langgraph_flow import WORKFLOW_ID


def _clean_text(text: Any) -> str:
    if text is None:
        return ""
    return " ".join(str(text).split())


def _extract_text(inbound_event: dict[str, Any] | None) -> str:
    if not isinstance(inbound_event, dict):
        return ""
    text = inbound_event.get("text")
    if isinstance(text, dict):
        text = text.get("body") or text.get("text") or text.get("message") or text.get("value")
    if not text:
        text = inbound_event.get("body") or inbound_event.get("message") or inbound_event.get("message_text")
    return _clean_text(text)


def _extract_message_id(inbound_event: dict[str, Any] | None) -> str | None:
    if not isinstance(inbound_event, dict):
        return None
    for key in ("message_id", "messageId", "wamid", "id"):
        value = inbound_event.get(key)
        if value:
            return str(value)
    raw = inbound_event.get("raw")
    if isinstance(raw, dict):
        for key in ("message_id", "messageId", "id"):
            value = raw.get(key)
            if value:
                return str(value)
    return None


def _build_metadata(inbound_message_id: str | None, tenant_ctx: Any) -> dict[str, Any] | None:
    metadata: dict[str, Any] = {}
    if inbound_message_id:
        metadata["inboundMessageId"] = inbound_message_id
        if str(inbound_message_id).startswith("wamid"):
            metadata["wamid"] = inbound_message_id
    if isinstance(tenant_ctx, dict):
        tenant_id = tenant_ctx.get("tenant_id") or tenant_ctx.get("tenantId")
        tenant_host = tenant_ctx.get("tenant_host") or tenant_ctx.get("tenantHost")
        tenant_payload: dict[str, str] = {}
        if tenant_id:
            tenant_payload["tenantId"] = str(tenant_id)
        if tenant_host:
            tenant_payload["tenantHost"] = str(tenant_host)
        if tenant_payload:
            metadata["tenant"] = tenant_payload
    return metadata or None


async def maybe_start_ai_workflow_from_inbound(
    inbound_event: dict[str, Any] | None,
    broadcaster: Any,
    tenant_ctx: Any = None,
) -> dict[str, str] | None:
    text = _extract_text(inbound_event)
    if not text:
        return None

    inbound_message_id = _extract_message_id(inbound_event)
    metadata = _build_metadata(inbound_message_id, tenant_ctx)

    try:
        run = await services.start_run(WORKFLOW_ID, text, metadata=metadata)
    except Exception as exc:  # noqa: BLE001 - best-effort inbound hook
        print(
            "ERROR: AI workflow inbound trigger failed",
            {"message_id": inbound_message_id, "error": str(exc)},
        )
        return None

    run_id = run.get("runId") if isinstance(run, dict) else None
    if not run_id:
        return None
    response_text = None
    if isinstance(run, dict):
        output = run.get("output")
        if isinstance(output, dict):
            response_text = output.get("responseText")
    payload = {"runId": run_id}
    if response_text:
        payload["responseText"] = response_text
    return payload
