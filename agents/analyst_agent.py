"""Especialista en Análisis y Cómputo Cuantitativo.

Responsabilidad única: Tomar la evidencia aportada por el ResearchAgent,
ejecutar cálculos numéricos precisos con herramientas matemáticas (disponibilidad y estrés)
y emitir el artefacto AnalysisArtifact validado con Pydantic.
"""
from __future__ import annotations

import json
import os
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI

from state import MultiAgentState, AnalysisArtifact
from tools import calculate_availability_score, calculate_resource_stress_index, ANALYST_TOOLS

SYSTEM_PROMPT = """Eres el Especialista de Cómputo y Análisis Cuantitativo de Arquitectura.
Tu única función es:
1. Leer los datos numéricos extraídos por el Agente de Investigación.
2. Utilizar las herramientas de cálculo ('calculate_availability_score' y 'calculate_resource_stress_index')
   para obtener métricas determinísticas exactas.
3. Evaluar el nivel de riesgo global ('BAJO', 'MEDIO', 'ALTO', 'CRITICO') basándote en números y SLAs.
4. Generar conclusiones analíticas rigurosas y asignar un confidence_score.
5. Devolver un objeto estructurado según AnalysisArtifact.

REGLAS:
- Nunca inventes cálculos aritméticos de cabeza: invoca las herramientas matemáticas especializadas.
- Si la disponibilidad es inferior al 99.5% o el estrés de recursos supera 80%, el riesgo es ALTO o CRITICO.
"""


async def analyst_agent_node(state: MultiAgentState) -> dict[str, Any]:
    """Nodo ejecutor del agente analista con aislamiento de escritura sobre 'analyst_output'."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("Falta 'OPENAI_API_KEY' en el entorno.")

    model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")
    llm = ChatOpenAI(model=model_name, temperature=0.0)

    research_artifact = state.get("researcher_output")
    if not research_artifact:
        # Si no hay datos previos, no podemos computar
        err_msg = AIMessage(content="[AnalystAgent]: Error: No se encontraron datos de investigación previos en el estado.")
        return {"messages": [err_msg]}

    datos = research_artifact.datos_extraidos or {}
    total_req = int(datos.get("total_requests_hour", 850000))
    error_req = int(datos.get("error_responses_hour", 4250))
    cpu_pct = float(datos.get("cpu_utilization_pct", 88.4))
    mem_pct = float(datos.get("memory_utilization_pct", 91.2))

    # 1. Ejecución de herramientas matemáticas determinísticas
    avail_res_str = calculate_availability_score.invoke({
        "total_requests": total_req,
        "error_requests": error_req,
    })
    avail_res = json.loads(avail_res_str)

    stress_res_str = calculate_resource_stress_index.invoke({
        "cpu_pct": cpu_pct,
        "memory_pct": mem_pct,
    })
    stress_res = json.loads(stress_res_str)

    # 2. Generación estructurada de AnalysisArtifact con Pydantic
    structured_llm = llm.with_structured_output(AnalysisArtifact)
    analysis_prompt = (
        f"Genera un AnalysisArtifact riguroso basado en estos cómputos determinísticos realizados:\n"
        f"Datos Base: {json.dumps(datos, ensure_ascii=False)}\n"
        f"Cálculo de Disponibilidad: {avail_res_str}\n"
        f"Cálculo de Estrés de Recursos: {stress_res_str}\n"
        f"Establece la 'metrica_principal' como 'Disponibilidad y Tasa de Error', "
        f"'resultado_calculo' con la tasa de disponibilidad ({avail_res['availability_pct']}), "
        f"'evaluacion_riesgo' adecuada, conclusiones técnicas fundamentadas y un confidence_score (ej: 0.98)."
    )
    artifact = await structured_llm.ainvoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=analysis_prompt),
    ])

    # 3. Aislamiento de Escritura: sólo 'analyst_output'
    summary_msg = AIMessage(
        content=(
            f"[AnalystAgent]: Cómputo completado. Métrica: {artifact.metrica_principal} = {artifact.resultado_calculo}%. "
            f"Estrés de recursos: {stress_res['stress_index']}/100 ({stress_res['categoria_estres']}). "
            f"Riesgo: {artifact.evaluacion_riesgo}. Conclusiones: {'; '.join(artifact.conclusiones)}."
        )
    )

    return {
        "messages": [summary_msg],
        "analyst_output": artifact,
    }
