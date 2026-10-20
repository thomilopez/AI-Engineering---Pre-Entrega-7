# StateGraph Multi-Agente con Topologia Jerarquica, Checkpoints y HITL
from __future__ import annotations

from typing import Literal, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.base import BaseCheckpointSaver

from app.state import MultiAgentState
from app.agents.supervisor import supervisor_node
from app.agents.research_agent import research_agent_node
from app.agents.analyst_agent import analyst_agent_node
from app.agents.validator import deterministic_validator_node
from app.hitl import human_approval_node


def route_supervisor(state: MultiAgentState) -> Literal['researcher', 'analyst', 'validator', 'human_approval']:
    target = state.get('next_agent', 'FINISH')
    if target == 'FINISH':
        return 'human_approval'
    elif target in ('researcher', 'analyst', 'validator'):
        return target
    return 'human_approval'


def build_multi_agent_graph(checkpointer: Optional[BaseCheckpointSaver] = None):
    builder = StateGraph(MultiAgentState)

    builder.add_node('supervisor', supervisor_node)
    builder.add_node('researcher', research_agent_node)
    builder.add_node('analyst', analyst_agent_node)
    builder.add_node('validator', deterministic_validator_node)
    builder.add_node('human_approval', human_approval_node)

    builder.add_edge(START, 'supervisor')

    builder.add_conditional_edges(
        'supervisor',
        route_supervisor,
        {
            'researcher': 'researcher',
            'analyst': 'analyst',
            'validator': 'validator',
            'human_approval': 'human_approval',
        },
    )

    builder.add_edge('researcher', 'supervisor')
    builder.add_edge('analyst', 'supervisor')
    builder.add_edge('validator', 'supervisor')
    builder.add_edge('human_approval', END)

    if checkpointer is not None:
        return builder.compile(checkpointer=checkpointer)
    return builder.compile()
