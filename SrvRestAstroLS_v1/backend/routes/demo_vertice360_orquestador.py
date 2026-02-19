from __future__ import annotations

from typing import Any

from litestar import Router, get, post
from litestar.exceptions import HTTPException

from backend.modules.vertice360_orquestador_demo import services
from backend.modules.vertice360_orquestador_demo.schemas import (
    IngestMessageRequest,
    SupervisorSendRequest,
    VisitConfirmRequest,
    VisitProposeRequest,
    VisitRescheduleRequest,
)


def _map_service_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        detail = exc.args[0] if exc.args else "Not found"
        return HTTPException(status_code=404, detail=str(detail))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, RuntimeError):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@get("/bootstrap")
async def bootstrap() -> dict[str, Any]:
    try:
        return services.bootstrap()
    except Exception as exc:  # noqa: BLE001
        raise _map_service_error(exc) from exc


@get("/dashboard")
async def dashboard(cliente: str | None = None) -> dict[str, Any]:
    try:
        return services.dashboard(cliente)
    except Exception as exc:  # noqa: BLE001
        raise _map_service_error(exc) from exc


@get("/ticket/{ticket_id:str}")
async def ticket_detail(ticket_id: str) -> dict[str, Any]:
    try:
        return services.ticket_detail(ticket_id=ticket_id)
    except Exception as exc:  # noqa: BLE001
        raise _map_service_error(exc) from exc


@post("/ingest_message", status_code=200)
async def ingest_message(data: IngestMessageRequest) -> dict[str, Any]:
    try:
        return services.ingest_message(
            phone=data.phone,
            text=data.text,
            project_code=data.project_code,
            source=data.source,
        )
    except Exception as exc:  # noqa: BLE001
        raise _map_service_error(exc) from exc


@post("/visit/propose", status_code=200)
async def visit_propose(data: VisitProposeRequest) -> dict[str, Any]:
    try:
        return services.propose_visit(
            ticket_id=data.ticket_id,
            advisor_name=data.advisor_name,
            option1=data.option1,
            option2=data.option2,
            option3=data.option3,
            message_out=data.message_out,
            mode=data.mode,
        )
    except Exception as exc:  # noqa: BLE001
        raise _map_service_error(exc) from exc


@post("/visit/confirm", status_code=200)
async def visit_confirm(data: VisitConfirmRequest) -> dict[str, Any]:
    try:
        return services.confirm_visit(
            proposal_id=data.proposal_id,
            confirmed_option=data.confirmed_option,
            confirmed_by=data.confirmed_by,
        )
    except Exception as exc:  # noqa: BLE001
        raise _map_service_error(exc) from exc


@post("/visit/reschedule", status_code=200)
async def visit_reschedule(data: VisitRescheduleRequest) -> dict[str, Any]:
    try:
        return services.reschedule_visit(
            ticket_id=data.ticket_id,
            advisor_name=data.advisor_name,
            option1=data.option1,
            option2=data.option2,
            option3=data.option3,
            message_out=data.message_out,
        )
    except Exception as exc:  # noqa: BLE001
        raise _map_service_error(exc) from exc


@post("/supervisor/send", status_code=200)
async def supervisor_send(data: SupervisorSendRequest) -> dict[str, Any]:
    try:
        return services.supervisor_send(
            ticket_id=data.ticket_id,
            target=data.target,
            text=data.text,
        )
    except Exception as exc:  # noqa: BLE001
        raise _map_service_error(exc) from exc


router = Router(
    path="/api/demo/vertice360-orquestador",
    route_handlers=[
        bootstrap,
        dashboard,
        ticket_detail,
        ingest_message,
        visit_propose,
        visit_confirm,
        visit_reschedule,
        supervisor_send,
    ],
)
