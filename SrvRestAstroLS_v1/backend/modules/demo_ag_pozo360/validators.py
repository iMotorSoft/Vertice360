# DEMO – Generado con Antigravity (AG-UI) para Pozo360 (NO PRODUCCIÓN)

from litestar.exceptions import NotFoundException
from backend.db import demo_pozo360_data

def ensure_project_exists(id_proyecto: str) -> None:
    projects = demo_pozo360_data.get_demo_projects()
    if not any(p["id_proyecto"] == id_proyecto for p in projects):
        raise NotFoundException(detail=f"Proyecto {id_proyecto} no encontrado")

def ensure_investor_exists(id_inversor: str) -> None:
    investors = demo_pozo360_data.get_demo_investors()
    if not any(i["id_inversor"] == id_inversor for i in investors):
        raise NotFoundException(detail=f"Inversor {id_inversor} no encontrado")
