from __future__ import annotations

from typing import Any

from litestar import Router, get, post
from litestar.exceptions import HTTPException

from backend.modules.vertice360_ai_workflow_demo import services
from backend.modules.vertice360_ai_workflow_demo.schemas import ResetRequest, RunRequest, SendReplyRequest
from backend.modules.vertice360_workflow_demo import services as workflow_services


@get("/workflows")
async def list_workflows() -> list[dict[str, Any]]:
    return services.list_workflows()


@get("/workflows/{workflow_id:str}")
async def get_workflow(workflow_id: str) -> dict[str, Any]:
    workflow = services.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@post("/runs")
async def create_run(data: RunRequest) -> dict[str, Any]:
    if not data.input.strip():
        raise HTTPException(status_code=400, detail="input is required")
    mode = (data.mode or services.DEFAULT_MODE).strip().lower()
    if mode not in services.ALLOWED_MODES:
        raise HTTPException(status_code=400, detail="Invalid mode. Use heuristic or llm.")
    if mode == "llm" and not services.llm_provider_configured():
        raise HTTPException(
            status_code=400,
            detail="LLM mode requested but no provider configured. Set VERTICE360_OPENAI_KEY or OPENAI_API_KEY.",
        )
    try:
        return await services.run_workflow(data.workflowId, data.input, mode)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@get("/runs")
async def list_runs() -> list[dict[str, Any]]:
    return services.list_runs()


@get("/runs/{run_id:str}")
async def get_run(run_id: str) -> dict[str, Any]:
    run = services.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@post("/reset")
async def reset_demo(data: ResetRequest) -> dict[str, Any]:
    return await services.reset_demo(data.reason)


@post("/send-reply")
async def send_reply(data: SendReplyRequest) -> dict[str, Any]:
    text = data.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    try:
        return await workflow_services.send_demo_reply(data.ticketId, data.to, text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


router = Router(
    path="/api/demo/vertice360-ai-workflow",
    route_handlers=[
        list_workflows,
        get_workflow,
        create_run,
        list_runs,
        get_run,
        reset_demo,
        send_reply,
    ],
)
