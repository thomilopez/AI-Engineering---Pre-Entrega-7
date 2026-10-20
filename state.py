"""Definición del estado compartido y modelos Pydantic de contratos de datos.

Módulo 6: Sistemas Multi-Agente - Colaboración y Especialización
Principios aplicados:
1. Contratos de Interfaz: Pydantic valida la estructura y calidad antes de inyectar datos al estado.
2. Aislamiento de Escritura: Cada especialista escribe únicamente en su parcela (researcher_output, analyst_output, validation_output).
3. Herencia de MessagesState: Mantiene el historial de diálogo sin sobrescribir mensajes previos (add_messages).
4. Tipado Estático y Robustez en Python 3.12+.
"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field
from langgraph.graph.message import MessagesState


# ============================================================================
# Contratos de Datos (Pydantic Artifacts)
# ============================================================================

class ResearchArtifact(BaseModel):
    """Contrato de datos emitido exclusivamente por el Agente de Búsqueda/Investigación."""

    topic: str = Field(
        ...,
        description="Tema, entidad o consulta técnica investigada."
    )
    fuentes_consultadas: list[str] = Field(
        default_factory=list,
        description="Lista de fuentes, repositorios o módulos consultados."
    )
    datos_extraidos: dict[str, str | int | float | list[str]] = Field(
        default_factory=dict,
        description="Datos cuantitativos y cualitativos estructurados extraídos de las fuentes."
    )
    resumen_investigacion: str = Field(
        ...,
        description="Síntesis detallada de los hallazgos técnicos o comerciales."
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Nivel de confianza en la información obtenida (entre 0.0 y 1.0)."
    )


class AnalysisArtifact(BaseModel):
    """Contrato de datos emitido exclusivamente por el Agente de Análisis/Cómputo."""

    metrica_principal: str = Field(
        ...,
        description="Métrica clave analizada (ej: 'Tasa de Disponibilidad', 'Crecimiento MoM', 'Índice de Latencia')."
    )
    resultado_calculo: float = Field(
        ...,
        description="Resultado numérico calculado de forma determinística sobre los datos de investigación."
    )
    evaluacion_riesgo: Literal["BAJO", "MEDIO", "ALTO", "CRITICO"] = Field(
        ...,
        description="Clasificación categórica del riesgo detectado."
    )
    conclusiones: list[str] = Field(
        ...,
        min_length=1,
        description="Lista de conclusiones analíticas basadas estrictamente en la evidencia."
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Nivel de confianza en el análisis computado (entre 0.0 y 1.0)."
    )


class ValidationArtifact(BaseModel):
    """Contrato de datos emitido por la Puerta de Calidad / Validador Determinístico."""

    valido: bool = Field(
        ...,
        description="True si todos los artefactos cumplen las reglas de negocio y consistencia; False si hay conflicto."
    )
    conflictos_detectados: list[str] = Field(
        default_factory=list,
        description="Lista de discrepancias, valores fuera de rango o contradicciones detectadas."
    )
    requiere_escalacion_humana: bool = Field(
        default=False,
        description="Indica si el conflicto es irresoluble y debe escalarse a supervisión humana."
    )
    observaciones: str = Field(
        ...,
        description="Detalle técnico del resultado de la verificación de calidad."
    )


# ============================================================================
# Esquema de Ruteo del Supervisor
# ============================================================================

SupervisorDecision = Literal["researcher", "analyst", "validator", "FINISH"]


class SupervisorRoute(BaseModel):
    """Decisión de delegación dinámica tomada por el Supervisor con with_structured_output()."""

    next_agent: SupervisorDecision = Field(
        ...,
        description="Próximo especialista al cual delegar ('researcher', 'analyst', 'validator') o 'FINISH' para finalizar."
    )
    reasoning: str = Field(
        ...,
        description="Justificación concisa de por qué se toma esta decisión de delegación o cierre."
    )


# ============================================================================
# Estado Compartido del Grafo Multi-Agente
# ============================================================================

class MultiAgentState(MessagesState):
    """Estado compartido tipado del sistema multi-agente.

    Hereda de MessagesState (LangGraph) garantizando el historial inmutable de mensajes:
        messages: Annotated[list[BaseMessage], add_messages]

    Campos estructurados con aislamiento de escritura:
    - researcher_output: únicamente modificado por el research_agent.
    - analyst_output: únicamente modificado por el analyst_agent.
    - validation_output: únicamente modificado por el nodo validador determinístico.
    - next_agent: actualizado por el Supervisor para gobernar las aristas condicionales.
    - iterations: contador de seguridad anti bucle infinito.
    """

    task_description: str
    next_agent: str
    iterations: int
    researcher_output: ResearchArtifact | None
    analyst_output: AnalysisArtifact | None
    validation_output: ValidationArtifact | None
