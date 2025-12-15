# DEMO – Generado con Antigravity (AG-UI) para Vertice360 (NO PRODUCCIÓN)

from litestar import Router, get
from backend.modules.demo_ag_vertice360 import services, validators
from backend.modules.demo_ag_vertice360.schemas import (
    ProyectoDemo,
    UnidadDemo,
    InversorDemo,
    OperacionDemo,
)

@get("/projects")
async def get_projects() -> list[ProyectoDemo]:
    """Devuelve la lista de proyectos de demo."""
    return services.list_demo_projects()

@get("/projects/{id_proyecto:str}/units")
async def get_project_units(id_proyecto: str) -> list[UnidadDemo]:
    """Devuelve la lista de unidades para el proyecto dado."""
    validators.ensure_project_exists(id_proyecto)
    return services.list_demo_units_for_project(id_proyecto)

@get("/investors")
async def get_investors() -> list[InversorDemo]:
    """Devuelve la lista de inversores de demo."""
    return services.list_demo_investors()

@get("/investors/{id_inversor:str}/operations")
async def get_investor_operations(id_inversor: str) -> list[OperacionDemo]:
    """Devuelve la lista de operaciones de ese inversor."""
    validators.ensure_investor_exists(id_inversor)
    return services.list_demo_operations_for_investor(id_inversor)

router = Router(
    path="/api/demo/ag",
    route_handlers=[
        get_projects,
        get_project_units,
        get_investors,
        get_investor_operations,
    ],
)
