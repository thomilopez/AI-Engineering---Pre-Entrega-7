"""Script principal asíncrono para ejecutar el Orquestador Multi-Agente y registrar trazas.

Módulo 6: Sistemas Multi-Agente - Colaboración y Especialización
Genera automáticamente:
- multi_agent_trace.json
- multi_agent_trace.log
- graph_diagram.png (Mermaid rendering visual si hay conectividad a red)
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any
from dotenv import load_dotenv

from langchain_core.messages import HumanMessage, BaseMessage
from graph import build_multi_agent_graph
from state import MultiAgentState

load_dotenv()

JSON_TRACE_FILE = "multi_agent_trace.json"
LOG_TRACE_FILE = "multi_agent_trace.log"


async def run_multi_agent_session() -> None:
    """Ejecuta una consulta compleja sobre el orquestador jerárquico y captura el flujo paso a paso."""
    print("=" * 80)
    print("EJECUTANDO ORQUESTADOR MULTI-AGENTE JERÁRQUICO (LANGGRAPH - MÓDULO 6)")
    print("=" * 80)

    task_prompt = (
        "Realizar una auditoría técnica completa del clúster de producción 'cloud-cluster-prod': "
        "recolectar telemetría de fallos y nodos, calcular disponibilidad y estrés de recursos, "
        "validar consistencia de datos y emitir informe de recomendaciones operativas."
    )

    print(f"Tarea asignada: {task_prompt}\n")

    graph = build_multi_agent_graph()

    # Intentar generar imagen Mermaid del grafo
    try:
        mermaid_png = graph.get_graph().draw_mermaid_png()
        with open("graph_diagram.png", "wb") as f:
            f.write(mermaid_png)
        print("[OK] Diagrama de arquitectura exportado a 'graph_diagram.png'.")
    except Exception as e:
        print(f"[INFO] Diagrama visual no generado ({e}), se mantiene representación Mermaid en README.")

    initial_state: MultiAgentState = {
        "messages": [HumanMessage(content=task_prompt)],
        "task_description": task_prompt,
        "next_agent": "supervisor",
        "iterations": 0,
        "researcher_output": None,
        "analyst_output": None,
        "validation_output": None,
    }

    trace_steps: list[dict[str, Any]] = []
    log_lines: list[str] = [
        "=" * 80,
        "TRAZA DE EJECUCIÓN MULTI-AGENTE: DELEGACIÓN JERÁRQUICA Y ESTADO COMPARTIDO",
        "=" * 80,
        f"Consulta Inicial: {task_prompt}\n",
    ]

    step_count = 0

    # Ejecución asíncrona mediante streaming de nodos (.astream)
    async for output in graph.astream(initial_state, stream_mode="updates"):
        step_count += 1
        node_name = list(output.keys())[0]
        node_data = output[node_name]

        step_info: dict[str, Any] = {
            "step": step_count,
            "node": node_name,
            "data": {},
        }

        log_lines.append(f"--- [PASO {step_count}] NODO EJECUTADO: '{node_name.upper()}' ---")

        # Registro de mensajes emitidos por el nodo
        if "messages" in node_data and node_data["messages"]:
            for m in node_data["messages"]:
                content = m.content if isinstance(m.content, str) else str(m.content)
                log_lines.append(f"  Mensaje: {content}")

        # Registro de artefactos Pydantic generados con aislamiento de escritura
        if "researcher_output" in node_data and node_data["researcher_output"]:
            art = node_data["researcher_output"]
            step_info["data"]["researcher_artifact"] = art.model_dump()
            log_lines.append(f"  [Artifact] ResearchArtifact generado (confidence={art.confidence_score}).")

        if "analyst_output" in node_data and node_data["analyst_output"]:
            art = node_data["analyst_output"]
            step_info["data"]["analyst_artifact"] = art.model_dump()
            log_lines.append(f"  [Artifact] AnalysisArtifact generado (riesgo={art.evaluacion_riesgo}, score={art.confidence_score}).")

        if "validation_output" in node_data and node_data["validation_output"]:
            art = node_data["validation_output"]
            step_info["data"]["validation_artifact"] = art.model_dump()
            log_lines.append(f"  [Artifact] ValidationArtifact generado (valido={art.valido}, conflictos={art.conflictos_detectados}).")

        if "next_agent" in node_data:
            step_info["data"]["next_agent"] = node_data["next_agent"]
            log_lines.append(f"  [Supervisor] Próxima delegación decidida: '{node_data['next_agent']}'.")

        log_lines.append("")
        trace_steps.append(step_info)

    log_lines.append("=" * 80)
    log_lines.append("FLUJO COMPLETADO CON ÉXITO")
    log_lines.append("=" * 80)

    # Imprimir log en consola
    print("\n".join(log_lines))

    # Guardar traza estructurada en JSON
    with open(JSON_TRACE_FILE, "w", encoding="utf-8") as f:
        json.dump(trace_steps, f, ensure_ascii=False, indent=2)
    print(f"[OK] Traza JSON exportada a '{JSON_TRACE_FILE}'.")

    # Guardar traza en LOG
    with open(LOG_TRACE_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))
    print(f"[OK] Traza legible exportada a '{LOG_TRACE_FILE}'.")


if __name__ == "__main__":
    asyncio.run(run_multi_agent_session())
