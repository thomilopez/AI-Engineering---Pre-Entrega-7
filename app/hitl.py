# Flujo Human-in-the-Loop (HITL) para Aprobacion Humana en Tareas Criticas
from __future__ import annotations

import logging
from typing import Any
from pydantic import BaseModel, Field
from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from app.state import MultiAgentState

logger = logging.getLogger('hitl')


class ApprovalRequest(BaseModel):
    approved: bool = Field(..., description='Indica si el operador aprueba o rechaza la accion critica.')
    comments: str = Field(default='', description='Observaciones o justificacion del operador.')
    approver: str = Field(default='admin@system.local', description='Identificador del usuario que autoriza la accion.')


def is_task_critical(state: MultiAgentState) -> bool:
    analyst_out = state.get('analyst_output')
    if analyst_out and analyst_out.evaluacion_riesgo in ('ALTO', 'CRITICO'):
        return True

    task_desc = (state.get('task_description') or '').lower()
    critical_keywords = ['produccion', 'prod', 'cluster', 'reinicio', 'mitigacion', 'failover', 'alta criticidad']
    if any(k in task_desc for k in critical_keywords):
        return True

    return False


async def human_approval_node(state: MultiAgentState) -> dict[str, Any]:
    if not is_task_critical(state):
        return {
            'messages': [AIMessage(content='[HITL]: Tarea evaluada de bajo riesgo. No requiere pausa humana obligatoria.')]
        }

    logger.info('[HITL] Tarea CRITICA detectada. Solicitando aprobacion humana obligatoria...')

    analyst_out = state.get('analyst_output')
    risk = analyst_out.evaluacion_riesgo if analyst_out else 'ALTO'
    metric_val = analyst_out.resultado_calculo if analyst_out else 'N/A'

    interrupt_payload = {
        'type': 'HUMAN_APPROVAL_REQUIRED',
        'action': 'Aprobacion de informe de infraestructura y mitigaciones operativas',
        'reason': f'Riesgo detectado: {risk}. Metrica: {metric_val}',
        'requires_role': 'SRE_LEAD / SYSTEM_ADMIN',
    }

    decision: dict[str, Any] = interrupt(interrupt_payload)

    approved = decision.get('approved', False) if isinstance(decision, dict) else bool(decision)
    comments = decision.get('comments', '') if isinstance(decision, dict) else ''
    approver = decision.get('approver', 'humano_anonimo') if isinstance(decision, dict) else 'humano'

    logger.info(f'[HITL] Decision humana recibida: approved={approved}, approver={approver}, comments={comments}')

    status_str = 'APROBADO' if approved else 'RECHAZADO'
    hitl_message = AIMessage(
        content=f'[HITL - APROBACION HUMANA]: {status_str} por {approver}. Comentarios: {comments}'
    )

    return {
        'messages': [hitl_message],
    }
