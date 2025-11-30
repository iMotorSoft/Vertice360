# DEMO – Generado con Antigravity (AG-UI) para Pozo360 (NO PRODUCCIÓN)

from dataclasses import dataclass
from typing import Optional

@dataclass
class ProyectoDemo:
    id_proyecto: str
    nombre: str
    barrio: str
    ciudad: str
    estado: str
    moneda: str
    precio_desde: float
    precio_hasta: float
    fecha_entrega_estimada: str

@dataclass
class UnidadDemo:
    id_unidad: str
    id_proyecto: str
    piso: int
    ambiente: str
    m2_cubiertos: float
    m2_totales: float
    precio_lista: float
    moneda: str
    estado_unidad: str

@dataclass
class InversorDemo:
    id_inversor: str
    nombre: str
    tipo_inversor: str
    email: str
    pais: str

@dataclass
class OperacionDemo:
    id_operacion: str
    id_inversor: str
    id_unidad: str
    tipo_operacion: str
    fecha: str
    monto: float
    moneda: str
