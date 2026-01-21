from __future__ import annotations

import datetime as dt
import uuid
from collections import deque
from typing import Any


MAX_RUNS = 50
runs: dict[str, dict[str, Any]] = {}
inbound_message_index: dict[str, str] = {}
_run_order: deque[str] = deque()


def _epoch_ms() -> int:
    return int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)


def _trim_runs() -> None:
    while len(_run_order) > MAX_RUNS:
        run_id = _run_order.popleft()
        runs.pop(run_id, None)
        if inbound_message_index:
            stale_keys = [key for key, value in inbound_message_index.items() if value == run_id]
            for key in stale_keys:
                inbound_message_index.pop(key, None)


def create_run(
    workflow_id: str,
    input_text: str,
    mode: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    now_ms = _epoch_ms()
    run = {
        "runId": run_id,
        "workflowId": workflow_id,
        "input": input_text,
        "mode": mode,
        "status": "RUNNING",
        "startedAt": now_ms,
        "endedAt": None,
        "updatedAt": now_ms,
        "steps": [],
        "output": None,
        "error": None,
    }
    if metadata:
        run["metadata"] = metadata
        inbound_message_id = metadata.get("inboundMessageId")
        if inbound_message_id:
            inbound_message_index[str(inbound_message_id)] = run_id
    runs[run_id] = run
    _run_order.append(run_id)
    _trim_runs()
    return run


def add_step(run_id: str, step: dict[str, Any]) -> dict[str, Any]:
    run = runs.get(run_id)
    if not run:
        raise KeyError("run not found")
    run.setdefault("steps", []).append(step)
    run["updatedAt"] = _epoch_ms()
    return step


def complete_run(run_id: str, output: dict[str, Any]) -> dict[str, Any]:
    run = runs.get(run_id)
    if not run:
        raise KeyError("run not found")
    now_ms = _epoch_ms()
    run["status"] = "COMPLETED"
    run["endedAt"] = now_ms
    run["updatedAt"] = now_ms
    run["output"] = output
    run["error"] = None
    return run


def fail_run(run_id: str, error: str) -> dict[str, Any]:
    run = runs.get(run_id)
    if not run:
        raise KeyError("run not found")
    now_ms = _epoch_ms()
    run["status"] = "FAILED"
    run["endedAt"] = now_ms
    run["updatedAt"] = now_ms
    run["error"] = error
    return run


def list_runs() -> list[dict[str, Any]]:
    items = sorted(runs.values(), key=lambda run: run.get("startedAt") or 0, reverse=True)
    summaries = []
    for run in items:
        summaries.append(
            {
                "runId": run.get("runId"),
                "workflowId": run.get("workflowId"),
                "status": run.get("status"),
                "startedAt": run.get("startedAt"),
                "endedAt": run.get("endedAt"),
                "input": run.get("input"),
                "output": run.get("output"),
                "stepCount": len(run.get("steps") or []),
            }
        )
    return summaries


def get_run(run_id: str) -> dict[str, Any] | None:
    return runs.get(run_id)


def reset_store() -> None:
    runs.clear()
    inbound_message_index.clear()
    _run_order.clear()
