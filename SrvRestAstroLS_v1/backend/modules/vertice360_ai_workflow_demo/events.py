from __future__ import annotations

import datetime as dt
from typing import Any

from backend.modules.agui_stream import broadcaster


RUN_STARTED = "ai_workflow.run.started"
RUN_STEP = "ai_workflow.run.step"
RUN_COMPLETED = "ai_workflow.run.completed"
RUN_FAILED = "ai_workflow.run.failed"
WORKFLOW_RESET = "ai_workflow.workflow.reset"
MAX_STEP_SUMMARY = 160


def _epoch_ms() -> int:
    return int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)


def _normalize_run_id(run_id: str) -> str:
    run_id = str(run_id or "").strip()
    if not run_id:
        raise ValueError("runId is required")
    return run_id


def _shorten_summary(summary: str) -> str:
    if len(summary) <= MAX_STEP_SUMMARY:
        return summary
    return summary[: MAX_STEP_SUMMARY - 3].rstrip() + "..."


async def emit_event(name: str, run_id: str | None, value: dict[str, Any]) -> None:
    payload = {
        "type": "CUSTOM",
        "timestamp": _epoch_ms(),
        "name": name,
        "value": value,
        "correlationId": run_id,
    }
    await broadcaster.publish(name, payload)


async def emit_run_started(run_id: str, workflow_id: str, input_text: str, started_at: int) -> None:
    run_id = _normalize_run_id(run_id)
    value = {
        "runId": run_id,
        "workflowId": workflow_id,
        "input": input_text,
        "startedAt": started_at,
    }
    await emit_event(RUN_STARTED, run_id, value)


async def emit_run_step(
    run_id: str,
    node_id: str,
    status: str,
    started_at: int,
    ended_at: int,
    summary: str,
    data: dict[str, Any] | None = None,
) -> None:
    run_id = _normalize_run_id(run_id)
    value = {
        "runId": run_id,
        "nodeId": node_id,
        "status": status,
        "startedAt": started_at,
        "endedAt": ended_at,
        "summary": _shorten_summary(summary),
        "data": data or {},
    }
    await emit_event(RUN_STEP, run_id, value)


async def emit_run_completed(run_id: str, output: dict[str, Any], ended_at: int) -> None:
    run_id = _normalize_run_id(run_id)
    value = {"runId": run_id, "output": output, "endedAt": ended_at}
    await emit_event(RUN_COMPLETED, run_id, value)


async def emit_run_failed(run_id: str, error: str, at: int) -> None:
    run_id = _normalize_run_id(run_id)
    value = {"runId": run_id, "error": error, "at": at}
    await emit_event(RUN_FAILED, run_id, value)


async def emit_workflow_reset(reason: str) -> None:
    value = {"reason": reason, "at": _epoch_ms()}
    await emit_event(WORKFLOW_RESET, None, value)
