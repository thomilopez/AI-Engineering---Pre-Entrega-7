"""Especialista en Búsqueda e Investigación Técnica.

Responsabilidad única: Consultar fuentes de telemetría e infraestructura,
extraer métricas y evidencia empírica, y estructurar el artefacto ResearchArtifact.
"""
from __future__ import annotations

import json
import os
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI

from state import MultiAgentState, ResearchArtifact
from tools import RESEARCHER_TOOLS

SYSTEM_PROMPT = """Eres el Especialista de Búsqueda e Investigación Técnica de Infraestructura.
Tu única función es:
1. Analizar la tarea asignada y determinar qué clúster o sistema consultar.
2. Invocar la herramienta 'query_cluster_metrics' con el identificador adecuado.
3. Extraer los datos brutos (nodos, peticiones, errores, latencia, CPU, memoria, logs).
4. Sintetizar la evidencia recopilada para que el Agente Analista pueda computar métricas y riesgos.
5. Devolver un JSON estrictamente estructurado que satisfaga el esquema ResearchArtifact.

NO inventes métricas. Todo dato debe provenir de las herramientas.
"""


async def research_agent_node(state: MultiAgentState) -> dict[str, Any]:
    """Nodo ejecutor del agente de investigación con ciclo de invocación y estructuración Pydantic."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("Falta 'OPENAI_API_KEY' en el entorno.")

    model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")
    llm = ChatOpenAI(model=model_name, temperature=0.0)
    llm_with_tools = llm.bind_tools(RESEARCHER_TOOLS)

    # Contexto mínimo: sólo la tarea asignada para evitar contaminación de contexto
    task_desc = state.get("task_description") or "Auditar clúster cloud-cluster-prod"
    user_prompt = f"Tarea de Investigación: {task_desc}. Realiza la consulta de telemetría y extrae todos los datos clave."

    # 1. Invocación al modelo para decidir y ejecutar tool call
    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)]
    ai_response = await llm_with_tools.ainvoke(messages)

    raw_data: dict[str, Any] = {}
    fuentes: list[str] = []

    # 2. Ejecución de la herramienta invocada
    if ai_response.tool_calls:
        for tc in ai_response.tool_calls:
            if tc["name"] == "query_cluster_metrics":
                fuentes.append(f"telemetry_db:{tc['args'].get('cluster_id')}")
                tool_output_str = RESEARCHER_TOOLS[0].invoke(tc["args"])
                try:
                    raw_data = json.loads(tool_output_str)
                except Exception:
                    raw_data = {"raw": tool_output_str}
    else:
        # Fallback determinístico si el LLM no emitió tool_call
        fuentes.append("telemetry_db:cloud-cluster-prod")
        raw_data = json.loads(RESEARCHER_TOOLS[0].invoke({"cluster_id": "cloud-cluster-prod"}))

    # 3. Estructuración formal mediante Pydantic (ResearchArtifact)
    structured_llm = llm.with_structured_output(ResearchArtifact)
    structuring_prompt = (
        f"Convierte la siguiente evidencia recolectada en un ResearchArtifact válido:\n"
        f"Tema: {task_desc}\n"
        f"Fuentes: {fuentes}\n"
        f"Datos Brutos: {json.dumps(raw_data, ensure_ascii=False)}\n"
        f"Asegúrate de asignar un confidence_score coherente (ej: 0.95 si los datos están completos)."
    )
    artifact = await structured_llm.ainvoke([HumanMessage(content=structuring_prompt)])

    # 4. Aislamiento de Escritura: sólo actualizamos 'researcher_output' y agregamos un mensaje
    summary_msg = AIMessage(
        content=(
            f"[ResearchAgent]: Investigación completada sobre '{artifact.topic}'. "
            f"Nodos activos: {raw_data.get('active_nodes')}/{raw_data.get('total_nodes')}. "
            f"Peticiones/h: {raw_data.get('total_requests_hour')}. "
            f"Errores/h: {raw_data.get('error_responses_hour')}. "
            f"CPU: {raw_data.get('cpu_utilization_pct')}%, Memoria: {raw_data.get('memory_utilization_pct')}%. "
            f"Confidence: {artifact.confidence_score}."
        )
    )

    return {
        "messages": [summary_msg],
        "researcher_output": artifact,
    }
