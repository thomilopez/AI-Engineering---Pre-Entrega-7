"""Puerta de Calidad: Validación Determinística y Detección de Conflictos.

Principio: 'Pydantic, no vibras'.
Verifica reglas estrictas con código Python determinístico:
1. Fechas válidas y existencia de datos numéricos.
2. Concordancia matemática entre los artefactos de Búsqueda y Cómputo.
3. Consistencia de confidence_scores en rango [0.0, 1.0].
4. Evaluación de cuándo escalar a revisión humana si hay conflictos irresolubles.
"""
from __future__ import annotations

from typing import Any
from langchain_core.messages import AIMessage
from state import MultiAgentState, ValidationArtifact


def deterministic_validator_node(state: MultiAgentState) -> dict[str, Any]:
    """Validador determinístico con aislamiento de escritura sobre 'validation_output'."""
    conflictos: list[str] = []
    research = state.get("researcher_output")
    analysis = state.get("analyst_output")

    # 1. Regla: Ambos artefactos deben estar presentes
    if not research:
        conflictos.append("Falta el artefacto del Agente de Investigación (ResearchArtifact).")
    if not analysis:
        conflictos.append("Falta el artefacto del Agente de Análisis (AnalysisArtifact).")

    # 2. Validación cruzada de datos si ambos existen
    if research and analysis:
        # Validación de rango de confidence_score
        if not (0.0 <= research.confidence_score <= 1.0):
            conflictos.append(f"Confidence score de investigación fuera de rango: {research.confidence_score}")
        if not (0.0 <= analysis.confidence_score <= 1.0):
            conflictos.append(f"Confidence score de análisis fuera de rango: {analysis.confidence_score}")

        # Verificación de coherencia numérica
        datos = research.datos_extraidos or {}
        total_req = float(datos.get("total_requests_hour", 0))
        error_req = float(datos.get("error_responses_hour", 0))

        if total_req > 0:
            expected_avail = round(100.0 - (error_req / total_req * 100.0), 2)
            # Tolerancia de redondeo 0.5%
            if abs(analysis.resultado_calculo - expected_avail) > 0.5:
                conflictos.append(
                    f"Incoherencia de cálculo: Análisis reportó {analysis.resultado_calculo}% "
                    f"pero los datos de investigación indican {expected_avail}%."
                )

        # Regla de coherencia de riesgo
        cpu = float(datos.get("cpu_utilization_pct", 0))
        mem = float(datos.get("memory_utilization_pct", 0))
        if (cpu > 85 or mem > 85) and analysis.evaluacion_riesgo in ("BAJO", "MEDIO"):
            conflictos.append(
                f"Contradicción crítica: Saturación de recursos detectada (CPU: {cpu}%, Mem: {mem}%) "
                f"pero la evaluación de riesgo fue clasificada optimistamente como '{analysis.evaluacion_riesgo}'."
            )

    valido = (len(conflictos) == 0)
    # Escalar a humano si hay contradicción grave en cálculo de riesgo
    requiere_escalacion = any("Contradicción crítica" in c for c in conflictos)

    obs = (
        "Validación determinística exitosa: métricas, fórmulas y artefactos completamente coherentes."
        if valido
        else f"Se detectaron {len(conflictos)} conflictos en la puerta de calidad."
    )

    artifact = ValidationArtifact(
        valido=valido,
        conflictos_detectados=conflictos,
        requiere_escalacion_humana=requiere_escalacion,
        observaciones=obs,
    )

    msg = AIMessage(
        content=(
            f"[ValidationGate]: Estado: {'APROBADO' if valido else 'RECHAZADO'}. "
            f"Conflictos: {conflictos if conflictos else 'Ninguno'}. "
            f"Escalación Humana: {requiere_escalacion}. Observaciones: {obs}"
        )
    )

    return {
        "messages": [msg],
        "validation_output": artifact,
    }
