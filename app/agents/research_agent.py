"""Especialista en Investigacion y Telemetria."""
from __future__ import annotations

import json
import os
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from app.state import MultiAgentState, ResearchArtifact
from app.tools import RESEARCHER_TOOLS
from app.llm_factory import get_llm, invoke_structured

SYSTEM_PROMPT = """Eres el Especialista de Infraestructura. Responde siempre en formato JSON."""

async def research_agent_node(state: MultiAgentState) -> dict[str, Any]:
    llm = get_llm(temperature=0.0)
    llm_with_tools = llm.bind_tools(RESEARCHER_TOOLS)

    task_desc = state.get("task_description") or "Auditar cluster cloud-cluster-prod"
    user_prompt = f"Tarea de Investigacion: {task_desc}. Realiza la consulta de telemetria y extrae todos los datos clave."
    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)]
    ai_response = await llm_with_tools.ainvoke(messages)

    raw_data: dict[str, Any] = {}
    fuentes: list[str] = []

    if ai_response.tool_calls:
        for tc in ai_response.tool_calls:
            if tc['name'] == "query_cluster_metrics":
                fuentes.append(f"telemetry_db:{tc['args'].get('cluster_id')}")
                tool_output_str = RESEARCHER_TOOLS[0].invoke(tc["args"])
                try:
                    raw_data = json.loads(tool_output_str)
                except Exception:
                    raw_data = {"raw": tool_output_str}
    else:
        fuentes.append("telemetry_db:cloud-cluster-prod")
        raw_data = json.loads(RESEARCHER_TOOLS[0].invoke({"cluster_id": "cloud-cluster-prod"}))

    structuring_prompt = (
        f"Convierte la siguiente evidencia recolectada en un objeto JSON estructurado:\n"
        f"Tema: {task_desc}\n"
        f"Fuentes: {fuentes}\n"
        f"Datos Brutos: {json.dumps(raw_data, ensure_ascii=False)}\n"
        "Asegurate de asignar un confidence_score coherente (ej: 0.95 si los datos estan completos)."
    )
    artifact = await invoke_structured(llm, ResearchArtifact, [HumanMessage(content=structuring_prompt)])

    summary_msg = AIMessage(
        content=(
            f"[ResearchAgent]: Investigacion completada sobre '{artifact.topic}'. "
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
