"""Herramientas funcionales para los agentes especialistas.

Cada herramienta utiliza esquemas de Pydantic (@tool(args_schema=...))
con docstrings descriptivos para permitir la invocación autónoma.
"""
from __future__ import annotations

import json
from pydantic import BaseModel, Field
from langchain_core.tools import tool


# ============================================================================
# Base de Conocimiento Técnica Simulada (Servidores e Infraestructura Cloud)
# ============================================================================

_KNOWLEDGE_BASE = {
    "cloud-cluster-prod": {
        "cluster_id": "cloud-cluster-prod",
        "region": "us-east-1",
        "total_nodes": 24,
        "active_nodes": 22,
        "failed_nodes": 2,
        "total_requests_hour": 850000,
        "error_responses_hour": 4250,
        "average_latency_ms": 142.5,
        "peak_latency_ms": 620.0,
        "cpu_utilization_pct": 88.4,
        "memory_utilization_pct": 91.2,
        "incident_logs": [
            "OOM killer disparado en nodo-08 a las 02:14 UTC",
            "Fallo de heartbeat en nodo-17 tras saturación de red",
            "Alerta de umbral P99 > 500ms activada",
        ],
        "last_audit": "2026-10-15T22:00:00Z",
    },
    "api-gateway-latam": {
        "cluster_id": "api-gateway-latam",
        "region": "sa-east-1",
        "total_nodes": 12,
        "active_nodes": 12,
        "failed_nodes": 0,
        "total_requests_hour": 320000,
        "error_responses_hour": 160,
        "average_latency_ms": 45.0,
        "peak_latency_ms": 110.0,
        "cpu_utilization_pct": 48.0,
        "memory_utilization_pct": 52.3,
        "incident_logs": [],
        "last_audit": "2026-10-15T23:30:00Z",
    },
}


# ============================================================================
# Esquemas Pydantic de Validación de Entrada
# ============================================================================

class QueryMetricsInput(BaseModel):
    """Contrato de entrada para la consulta de telemetría de un clúster."""

    cluster_id: str = Field(
        ...,
        description="Identificador único del clúster a inspeccionar (ej: 'cloud-cluster-prod' o 'api-gateway-latam')."
    )


class ComputeAvailabilityInput(BaseModel):
    """Contrato de entrada para el cálculo numérico de disponibilidad y tasa de error."""

    total_requests: int = Field(
        ...,
        ge=0,
        description="Cantidad total de peticiones procesadas en la ventana de tiempo."
    )
    error_requests: int = Field(
        ...,
        ge=0,
        description="Cantidad de peticiones con código de error (4xx / 5xx)."
    )


class ComputeResourceStressInput(BaseModel):
    """Contrato de entrada para computar el índice de estrés de recursos."""

    cpu_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Porcentaje de utilización de CPU (0.0 a 100.0)."
    )
    memory_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Porcentaje de utilización de Memoria RAM (0.0 a 100.0)."
    )


# ============================================================================
# Herramientas del Agente de Búsqueda/Investigación
# ============================================================================

@tool(args_schema=QueryMetricsInput)
def query_cluster_metrics(cluster_id: str) -> str:
    """Consulta la telemetría técnica, estado de nodos y logs de incidentes de un clúster de infraestructura.

    CUÁNDO USAR:
    - Utilízala cuando necesites recolectar métricas de rendimiento, errores, nodos activos o incidentes de un clúster.
    - Especializada para la fase de Búsqueda/Investigación inicial.

    PARÁMETROS:
    - cluster_id (str): ID del clúster ('cloud-cluster-prod' o 'api-gateway-latam').

    RETORNO:
    - JSON con métricas de solicitudes, nodos, latencia, CPU, memoria y logs de fallos.
    """
    clean_id = cluster_id.strip().lower()
    data = _KNOWLEDGE_BASE.get(clean_id)
    if not data:
        return json.dumps(
            {
                "error": f"Clúster '{clean_id}' no encontrado en la base de datos de telemetría.",
                "available_clusters": list(_KNOWLEDGE_BASE.keys()),
            },
            ensure_ascii=False,
        )

    return json.dumps(data, ensure_ascii=False)


# ============================================================================
# Herramientas del Agente de Análisis/Cómputo
# ============================================================================

@tool(args_schema=ComputeAvailabilityInput)
def calculate_availability_score(total_requests: int, error_requests: int) -> str:
    """Calcula matemáticamente la tasa de éxito (disponibilidad) y porcentaje de error de un servicio.

    CUÁNDO USAR:
    - Utilízala cuando dispongas de total de peticiones y errores y necesites el porcentaje de disponibilidad estricto.
    - Especializada para el Agente de Cómputo/Análisis.

    PARÁMETROS:
    - total_requests (int): Número total de solicitudes.
    - error_requests (int): Número de solicitudes erróneas.

    RETORNO:
    - JSON con porcentaje de disponibilidad (SLO) y tasa de error.
    """
    if total_requests == 0:
        return json.dumps({"error": "total_requests no puede ser 0 para calcular disponibilidad."})

    error_rate = (error_requests / total_requests) * 100.0
    availability = 100.0 - error_rate

    return json.dumps(
        {
            "total_requests": total_requests,
            "error_requests": error_requests,
            "availability_pct": round(availability, 4),
            "error_rate_pct": round(error_rate, 4),
            "sla_compliant": availability >= 99.5,
        },
        ensure_ascii=False,
    )


@tool(args_schema=ComputeResourceStressInput)
def calculate_resource_stress_index(cpu_pct: float, memory_pct: float) -> str:
    """Calcula el índice de estrés ponderado de recursos de infraestructura (0.0 a 100.0).

    CUÁNDO USAR:
    - Utilízala para determinar cuantitativamente el nivel de saturación del hardware.
    - Ponderación: 40% CPU + 60% Memoria (para cargas I/O e In-Memory).
    """
    stress_index = (cpu_pct * 0.40) + (memory_pct * 0.60)
    categoria = "BAJO"
    if stress_index >= 85.0:
        categoria = "CRITICO"
    elif stress_index >= 70.0:
        categoria = "ALTO"
    elif stress_index >= 50.0:
        categoria = "MEDIO"

    return json.dumps(
        {
            "cpu_pct": cpu_pct,
            "memory_pct": memory_pct,
            "stress_index": round(stress_index, 2),
            "categoria_estres": categoria,
        },
        ensure_ascii=False,
    )


RESEARCHER_TOOLS = [query_cluster_metrics]
ANALYST_TOOLS = [calculate_availability_score, calculate_resource_stress_index]
ALL_TOOLS = RESEARCHER_TOOLS + ANALYST_TOOLS
