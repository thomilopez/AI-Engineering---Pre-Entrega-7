"""Construcción y compilación del StateGraph Multi-Agente con Topología Jerárquica.

Arquitectura:
                 +-------------------+
                 |    SUPERVISOR     |<-------------+
                 +-------------------+              |
                   |   |   |        \               |
                   |   |   |         \ (FINISH)     |
    +--------------+   |   +------+   \             |
    |                  |          |    v            |
    v                  v          v   (END)         |
[researcher]      [analyst]   [validator]           |
    |                  |          |                 |
    +------------------+----------+-----------------+
"""
from __future__ import annotations

from typing import Literal
from langgraph.graph import StateGraph, START, END

from state import MultiAgentState
from agents.supervisor import supervisor_node
from agents.research_agent import research_agent_node
from agents.analyst_agent import analyst_agent_node
from agents.validator import deterministic_validator_node


def route_supervisor(state: MultiAgentState) -> Literal["researcher", "analyst", "validator", "__end__"]:
    """Función de enrutamiento condicional basada en la decisión del supervisor."""
    target = state.get("next_agent", "FINISH")
    if target == "FINISH":
        return "__end__"
    elif target in ("researcher", "analyst", "validator"):
        return target
    return "__end__"


def build_multi_agent_graph():
    """Ensambla el grafo de agentes jerárquico con StateGraph(MultiAgentState)."""
    builder = StateGraph(MultiAgentState)

    # 1. Registrar nodos
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("researcher", research_agent_node)
    builder.add_node("analyst", analyst_agent_node)
    builder.add_node("validator", deterministic_validator_node)

    # 2. Entrada directa al supervisor
    builder.add_edge(START, "supervisor")

    # 3. Aristas condicionales de delegación desde el supervisor
    builder.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {
            "researcher": "researcher",
            "analyst": "analyst",
            "validator": "validator",
            "__end__": END,
        },
    )

    # 4. Todos los especialistas retornan su resultado al supervisor (cerrando el ciclo de supervisión)
    builder.add_edge("researcher", "supervisor")
    builder.add_edge("analyst", "supervisor")
    builder.add_edge("validator", "supervisor")

    return builder.compile()
