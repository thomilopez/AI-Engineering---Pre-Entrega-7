"""Nodo Supervisor: Orquestador Central para Delegación Dinámica y Síntesis Final.

Responsabilidades:
1. Analizar el estado actual y decidir a qué especialista delegar la subtarea.
2. Evitar ser 'Supervisor Todólogo': NO realiza tareas de búsqueda ni cálculos, solo coordina.
3. Evaluar cuándo la tarea está completa y generar la síntesis ejecutiva final antes de ir a END.
4. Prevenir bucles infinitos con tope de iteraciones.
"""
from __future__ import annotations

import os
from typing import Any
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI

from state import MultiAgentState, SupervisorRoute

SUPERVISOR_ROUTING_PROMPT = """Eres el Supervisor de un Sistema Multi-Agente de Arquitectura de Software.
Tu responsabilidad es dirigir el flujo de trabajo entre los siguientes especialistas:

1. 'researcher' (Agente de Investigación):
   - Debe ser convocado PRIMERO si aún no se han recopilado datos brutos de infraestructura (nodos, métricas, peticiones).

2. 'analyst' (Agente de Cómputo y Análisis):
   - Debe ser convocado DESPUÉS de 'researcher' para calcular disponibilidad, estrés de recursos y evaluar riesgo.

3. 'validator' (Puerta de Calidad Determinística):
   - Debe ser convocado DESPUÉS de que 'researcher' y 'analyst' hayan completado sus artefactos, para verificar que no haya contradicciones ni errores de cálculo.

4. 'FINISH':
   - Debe elegirse ÚNICAMENTE cuando la validación sea exitosa ('valido: True') y ya se cuente con toda la evidencia necesaria para dar la síntesis final.

REGLAS DE ORO:
- Tú NO calculas números ni consultas herramientas directamente; delegas en los especialistas.
- Revisa el estado actual y los mensajes previos para decidir cuál es el próximo paso óptimo.
"""

SYNTHESIS_PROMPT = """Eres el Supervisor Técnico. Todos los especialistas han completado su trabajo y la validación fue aprobada.
Sintetiza un informe final claro, profesional y estructurado que responda a la solicitud del usuario, integrando:
1. Hallazgos del Agente de Investigación (telemetría y nodos).
2. Resultados cuantitativos del Agente de Análisis (disponibilidad %, estrés de hardware y nivel de riesgo).
3. Dictamen de la Puerta de Calidad (consistencia de datos).
4. Recomendación operativa directa para el equipo de infraestructura.
"""


async def supervisor_node(state: MultiAgentState) -> dict[str, Any]:
    """Nodo del Supervisor: decide el siguiente paso o produce la síntesis final."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("Falta 'OPENAI_API_KEY' en el entorno.")

    model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")
    llm = ChatOpenAI(model=model_name, temperature=0.0)

    current_iterations = state.get("iterations", 0) + 1
    has_research = state.get("researcher_output") is not None
    has_analysis = state.get("analyst_output") is not None
    val_artifact = state.get("validation_output")
    has_validation = val_artifact is not None and val_artifact.valido

    # Salvaguarda de tope de iteraciones (anti bucle infinito)
    if current_iterations >= 6:
        route = SupervisorRoute(
            next_agent="FINISH",
            reasoning="Se alcanzó el tope máximo de iteraciones de seguridad (6). Se fuerza el cierre."
        )
    elif not has_research:
        route = SupervisorRoute(
            next_agent="researcher",
            reasoning="Falta la información base de infraestructura. Se delega al ResearchAgent."
        )
    elif not has_analysis:
        route = SupervisorRoute(
            next_agent="analyst",
            reasoning="Investigación disponible. Se delega al AnalystAgent para cómputo numérico y análisis de riesgo."
        )
    elif not has_validation:
        route = SupervisorRoute(
            next_agent="validator",
            reasoning="Artefactos de investigación y análisis listos. Se delega al Validador para control determinístico."
        )
    else:
        # Validación aprobada: delegación estructurada a FINISH
        structured_supervisor = llm.with_structured_output(SupervisorRoute)
        decision_input = (
            f"Estado actual de la tarea: '{state.get('task_description')}'.\n"
            f"Research: Completado.\n"
            f"Analysis: Completado.\n"
            f"Validation: Aprobada con éxito.\n"
            f"Decide si es momento de FINISH o si se requiere refinar."
        )
        route = await structured_supervisor.ainvoke([
            SystemMessage(content=SUPERVISOR_ROUTING_PROMPT),
            HumanMessage(content=decision_input),
        ])

    update: dict[str, Any] = {
        "next_agent": route.next_agent,
        "iterations": current_iterations,
    }

    # Si la decisión es finalizar, el supervisor elabora la síntesis ejecutiva final
    if route.next_agent == "FINISH":
        synthesis_input = (
            f"Tarea: {state.get('task_description')}\n"
            f"Investigación: {state['researcher_output'].model_dump_json(indent=2)}\n"
            f"Análisis: {state['analyst_output'].model_dump_json(indent=2)}\n"
            f"Validación: {state['validation_output'].model_dump_json(indent=2)}\n"
        )
        synthesis_resp = await llm.ainvoke([
            SystemMessage(content=SYNTHESIS_PROMPT),
            HumanMessage(content=synthesis_input),
        ])
        supervisor_msg = AIMessage(
            content=f"[SUPERVISOR - SÍNTESIS FINAL]:\n{synthesis_resp.content}"
        )
        update["messages"] = [supervisor_msg]
    else:
        routing_msg = AIMessage(
            content=f"[SUPERVISOR]: Delegando a '{route.next_agent}'. Motivo: {route.reasoning}"
        )
        update["messages"] = [routing_msg]

    return update
