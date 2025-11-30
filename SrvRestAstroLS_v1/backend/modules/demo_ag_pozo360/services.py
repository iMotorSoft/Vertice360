# DEMO – Generado con Antigravity (AG-UI) para Pozo360 (NO PRODUCCIÓN)

from backend.db import demo_pozo360_data
from backend.modules.demo_ag_pozo360.schemas import (
    ProyectoDemo,
    UnidadDemo,
    InversorDemo,
    OperacionDemo,
)

def list_demo_projects() -> list[ProyectoDemo]:
    raw_projects = demo_pozo360_data.get_demo_projects()
    return [
        ProyectoDemo(
            id_proyecto=p["id_proyecto"],
            nombre=p["nombre"],
            barrio=p["barrio"],
            ciudad=p["ciudad"],
            estado=p["estado"],
            moneda=p["moneda"],
            precio_desde=p["precio_desde"],
            precio_hasta=p["precio_hasta"],
            fecha_entrega_estimada=p["fecha_entrega_estimada"],
        )
        for p in raw_projects
    ]

def list_demo_units_for_project(id_proyecto: str) -> list[UnidadDemo]:
    raw_units = demo_pozo360_data.get_demo_units_for_project(id_proyecto)
    return [
        UnidadDemo(
            id_unidad=u["id_unidad"],
            id_proyecto=u["id_proyecto"],
            piso=u["piso"],
            ambiente=u["ambiente"],
            m2_cubiertos=u["m2_cubiertos"],
            m2_totales=u["m2_totales"],
            precio_lista=u["precio_lista"],
            moneda=u["moneda"],
            estado_unidad=u["estado_unidad"],
        )
        for u in raw_units
    ]

def list_demo_investors() -> list[InversorDemo]:
    raw_investors = demo_pozo360_data.get_demo_investors()
    return [
        InversorDemo(
            id_inversor=i["id_inversor"],
            nombre=i["nombre"],
            tipo_inversor=i["tipo_inversor"],
            email=i["email"],
            pais=i["pais"],
        )
        for i in raw_investors
    ]

def list_demo_operations_for_investor(id_inversor: str) -> list[OperacionDemo]:
    raw_ops = demo_pozo360_data.get_demo_operations_for_investor(id_inversor)
    return [
        OperacionDemo(
            id_operacion=o["id_operacion"],
            id_inversor=o["id_inversor"],
            id_unidad=o["id_unidad"],
            tipo_operacion=o["tipo_operacion"],
            fecha=o["fecha"],
            monto=o["monto"],
            moneda=o["moneda"],
        )
        for o in raw_ops
    ]
