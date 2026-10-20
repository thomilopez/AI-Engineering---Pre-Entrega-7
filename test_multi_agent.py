"""Suite de Pruebas Unitarias para el Orquestador Multi-Agente (Módulo 6).

Verifica la arquitectura, contratos Pydantic, herramientas funcionales
y el flujo de delegación sin gastar tokens de LLM.
Uso:
    python test_multi_agent.py
"""
from __future__ import annotations

import json
import unittest
from langgraph.graph.message import MessagesState

from state import MultiAgentState, ResearchArtifact, AnalysisArtifact, ValidationArtifact
from tools import (
    query_cluster_metrics,
    calculate_availability_score,
    calculate_resource_stress_index,
    RESEARCHER_TOOLS,
    ANALYST_TOOLS,
)
from agents.validator import deterministic_validator_node
from graph import build_multi_agent_graph


class TestMultiAgentSystem(unittest.TestCase):
    """Valida los criterios de aceptación y contratos de ingeniería del Módulo 6."""

    def test_01_estado_hereda_messages_state(self) -> None:
        """MultiAgentState debe heredar de MessagesState para soportar add_messages."""
        self.assertTrue(
            MessagesState in getattr(MultiAgentState, "__orig_bases__", ()) or "messages" in MultiAgentState.__annotations__,
            "MultiAgentState debe heredar formalmente de MessagesState."
        )

    def test_02_contrato_research_artifact(self) -> None:
        """ResearchArtifact debe validar tipos, listas y confidence_score en [0.0, 1.0]."""
        artifact = ResearchArtifact(
            topic="Auditoría de nodos",
            fuentes_consultadas=["telemetry_db:prod"],
            datos_extraidos={"total_nodes": 24, "active_nodes": 22},
            resumen_investigacion="2 nodos caídos por fallo OOM.",
            confidence_score=0.95,
        )
        self.assertEqual(artifact.confidence_score, 0.95)
        self.assertEqual(len(artifact.fuentes_consultadas), 1)

    def test_03_contrato_analysis_artifact(self) -> None:
        """AnalysisArtifact debe admitir únicamente valores categóricos de riesgo válidos."""
        artifact = AnalysisArtifact(
            metrica_principal="Tasa de Éxito de Peticiones",
            resultado_calculo=99.5,
            evaluacion_riesgo="ALTO",
            conclusiones=["Saturación de memoria > 90%"],
            confidence_score=0.98,
        )
        self.assertEqual(artifact.evaluacion_riesgo, "ALTO")

    def test_04_herramienta_researcher_metricas(self) -> None:
        """query_cluster_metrics debe devolver JSON válido con telemetría de clúster."""
        raw_res = query_cluster_metrics.invoke({"cluster_id": "cloud-cluster-prod"})
        data = json.loads(raw_res)
        self.assertEqual(data["cluster_id"], "cloud-cluster-prod")
        self.assertEqual(data["total_nodes"], 24)
        self.assertIn("error_responses_hour", data)

    def test_05_herramientas_analyst_calculos(self) -> None:
        """calculate_availability_score y stress_index deben calcular métricas exactas."""
        raw_avail = calculate_availability_score.invoke({
            "total_requests": 1000,
            "error_requests": 10,
        })
        data_avail = json.loads(raw_avail)
        self.assertEqual(data_avail["availability_pct"], 99.0)
        self.assertEqual(data_avail["error_rate_pct"], 1.0)

        raw_stress = calculate_resource_stress_index.invoke({
            "cpu_pct": 80.0,
            "memory_pct": 90.0,
        })
        data_stress = json.loads(raw_stress)
        self.assertEqual(data_stress["stress_index"], 86.0)
        self.assertEqual(data_stress["categoria_estres"], "CRITICO")

    def test_06_validador_deterministico_aprobado(self) -> None:
        """Validador debe aprobar si las métricas computadas son consistentes con la investigación."""
        dummy_state: MultiAgentState = {
            "messages": [],
            "task_description": "Test",
            "next_agent": "validator",
            "iterations": 1,
            "researcher_output": ResearchArtifact(
                topic="Test",
                fuentes_consultadas=["source"],
                datos_extraidos={"total_requests_hour": 100000, "error_responses_hour": 500},
                resumen_investigacion="Resumen",
                confidence_score=0.95,
            ),
            "analyst_output": AnalysisArtifact(
                metrica_principal="Disponibilidad",
                resultado_calculo=99.5,
                evaluacion_riesgo="BAJO",
                conclusiones=["Métricas en rango"],
                confidence_score=0.95,
            ),
            "validation_output": None,
        }
        res = deterministic_validator_node(dummy_state)
        val: ValidationArtifact = res["validation_output"]
        self.assertTrue(val.valido)
        self.assertEqual(len(val.conflictos_detectados), 0)

    def test_07_validador_detecta_conflicto_y_contradicion(self) -> None:
        """Validador debe detectar contradicción si hay saturación severa pero el riesgo dice BAJO."""
        dummy_state: MultiAgentState = {
            "messages": [],
            "task_description": "Test",
            "next_agent": "validator",
            "iterations": 1,
            "researcher_output": ResearchArtifact(
                topic="Test",
                fuentes_consultadas=["source"],
                datos_extraidos={"cpu_utilization_pct": 95.0, "memory_utilization_pct": 92.0},
                resumen_investigacion="Resumen",
                confidence_score=0.9,
            ),
            "analyst_output": AnalysisArtifact(
                metrica_principal="Disponibilidad",
                resultado_calculo=99.9,
                evaluacion_riesgo="BAJO",
                conclusiones=["Todo excelente"],
                confidence_score=0.9,
            ),
            "validation_output": None,
        }
        res = deterministic_validator_node(dummy_state)
        val: ValidationArtifact = res["validation_output"]
        self.assertFalse(val.valido)
        self.assertTrue(val.requiere_escalacion_humana)

    def test_08_topologia_del_grafo(self) -> None:
        """El grafo compilado debe contar con los 4 nodos esenciales: supervisor, researcher, analyst, validator."""
        graph = build_multi_agent_graph()
        nodes = list(graph.get_graph().nodes.keys())
        for expected in ("supervisor", "researcher", "analyst", "validator"):
            self.assertIn(expected, nodes, f"El nodo '{expected}' debe estar registrado en el StateGraph.")


if __name__ == "__main__":
    unittest.main()
