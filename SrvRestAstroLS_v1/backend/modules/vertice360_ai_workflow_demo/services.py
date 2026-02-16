from __future__ import annotations

import datetime as dt
from typing import Any

from backend.modules.vertice360_ai_workflow_demo import events, store
from backend import globalVar
from backend.modules.vertice360_ai_workflow_demo.langgraph_flow import (
    WORKFLOW_ID,
    workflow_definition,
    workflow_graph,
)

DEFAULT_MODE = "heuristic"
ALLOWED_MODES = {"heuristic", "llm"}


def _epoch_ms() -> int:
    return int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)


def list_workflows() -> list[dict[str, Any]]:
    return [workflow_definition()]


def get_workflow(workflow_id: str) -> dict[str, Any] | None:
    if workflow_id == WORKFLOW_ID:
        return workflow_definition()
    return None


def llm_provider_configured() -> bool:
    return bool(globalVar.OpenAI_Key)


async def run_workflow(
    workflow_id: str,
    input_text: str,
    mode: str | None = None,
    metadata: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if workflow_id != WORKFLOW_ID:
        raise ValueError("workflow not found")

    resolved_mode = (mode or DEFAULT_MODE).strip().lower()
    if resolved_mode not in ALLOWED_MODES:
        raise ValueError("invalid mode")

    run = store.create_run(workflow_id, input_text, resolved_mode, metadata=metadata)
    run_id = run["runId"]
    inbound_message_id = None
    if metadata:
        inbound_message_id = metadata.get("inboundMessageId") or metadata.get("wamid")
    if inbound_message_id:
        print(f"INFO: AI workflow run started from inbound wamid={inbound_message_id} runId={run_id}")
    await events.emit_run_started(run_id, workflow_id, input_text, run["startedAt"])

    state = {
        "run_id": run_id,
        "workflow_id": workflow_id,
        "input": input_text,
        "mode": mode,
    }
    if isinstance(metadata, dict):
        ticket_id = metadata.get("ticketId")
        if ticket_id:
            state["ticket_id"] = str(ticket_id)
    if isinstance(context, dict):
        intent_hint = context.get("intentHint") or context.get("intent") or context.get("primaryIntentLocked")
        if intent_hint:
            state["intent_hint"] = str(intent_hint)
        commercial_slots = context.get("commercialSlots") or context.get("commercial_slots")
        if isinstance(commercial_slots, dict):
            state["commercial_slots"] = commercial_slots
        provider = context.get("provider")
        if provider:
            state["provider"] = str(provider)
    try:
        final_state = await workflow_graph.ainvoke(state)
    except Exception as exc:
        error_message = str(exc)
        failed = store.fail_run(run_id, error_message)
        await events.emit_run_failed(run_id, error_message, failed.get("endedAt") or _epoch_ms())
        raise

    primary_intent = final_state.get("primary_intent") or final_state.get("intent") or "general"
    used_fallback = bool(final_state.get("used_fallback") or not llm_provider_configured())
    fallback_reason = final_state.get("fallback_reason")
    if used_fallback and not fallback_reason and not llm_provider_configured():
        fallback_reason = "openai_key_missing"

    output = {
        "responseText": final_state.get("response_text"),
        "intent": primary_intent,
        "primaryIntent": primary_intent,
        "secondaryIntents": final_state.get("secondary_intents") or [],
        "intents": final_state.get("intents") or [],
        "decision": final_state.get("decision"),
        "entities": final_state.get("entities") or {},
        "normalizedInput": final_state.get("normalized_input"),
        "pragmatics": final_state.get("pragmatics") or {},
        "missingSlotsCount": (final_state.get("pragmatics") or {}).get("missingSlotsCount"),
        "recommendedQuestion": final_state.get("recommended_question")
        or (final_state.get("pragmatics") or {}).get("recommendedQuestion"),
        "recommendedQuestions": final_state.get("recommended_questions")
        or (final_state.get("pragmatics") or {}).get("recommendedQuestions")
        or [],
        "usedFallback": used_fallback,
        "fallbackReason": fallback_reason,
        "model": final_state.get("response_model"),
        "commercial": final_state.get("commercial_slots") or final_state.get("commercial"),
        "summary": final_state.get("summary"),
        "nextActionQuestion": final_state.get("next_action_question"),
        "handoffRequired": bool(final_state.get("handoff_required")),
        "humanActionRequired": final_state.get("human_action_required"),
    }
    completed = store.complete_run(run_id, output)
    await events.emit_run_completed(run_id, output, completed.get("endedAt") or _epoch_ms())
    return store.get_run(run_id) or completed


async def start_run(
    workflow_id: str,
    input_text: str,
    mode: str | None = None,
    metadata: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return await run_workflow(workflow_id, input_text, mode, metadata=metadata, context=context)


def list_runs() -> list[dict[str, Any]]:
    return store.list_runs()


def get_run(run_id: str) -> dict[str, Any] | None:
    return store.get_run(run_id)


async def reset_demo(reason: str | None = None) -> dict[str, Any]:
    store.reset_store()
    await events.emit_workflow_reset(reason or "manual")
    return {"ok": True}
