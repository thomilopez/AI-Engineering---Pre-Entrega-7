# Worker Asincrono Desacoplado
from __future__ import annotations

import asyncio
import logging
import traceback
from datetime import datetime, timezone
from typing import Any, Optional
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from app.state import MultiAgentState
from app.graph import build_multi_agent_graph
from app.redis_state import redis_manager

logger = logging.getLogger('worker')


async def execute_task_background(job_id: str, prompt: str) -> None:
    logger.info('[Worker] Iniciando procesamiento para job_id: ' + str(job_id))
    start_time = datetime.now(timezone.utc).isoformat()

    try:
        await redis_manager.update_task_status(
            job_id=job_id,
            status='RUNNING',
            extra={'started_at': start_time}
        )

        checkpointer = await redis_manager.get_checkpointer()
        graph = build_multi_agent_graph(checkpointer=checkpointer)

        thread_config = 'configurable'
        config_dict = {thread_config: {'thread_id': job_id}}

        initial_state: MultiAgentState = {
            'messages': [HumanMessage(content=prompt)],
            'task_description': prompt,
            'next_agent': 'supervisor',
            'iterations': 0,
            'researcher_output': None,
            'analyst_output': None,
            'validation_output': None,
        }

        final_state: Optional[dict[str, Any]] = None
        async for chunk in graph.astream(initial_state, config=config_dict, stream_mode='values'):
            final_state = chunk

        snapshot = await graph.aget_state(config_dict)
        if snapshot and snapshot.tasks:
            for task in snapshot.tasks:
                if task.interrupts:
                    details = task.interrupts[0].value
                    logger.info('Grafo pausado en HITL en job ' + str(job_id))
                    await redis_manager.update_task_status(
                        job_id=job_id,
                        status='WAITING_APPROVAL',
                        extra={
                            'approval_pending': True,
                            'interrupt_details': details,
                        }
                    )
                    return

        completed_at = datetime.now(timezone.utc).isoformat()
        serialized_result = _extract_task_summary(final_state)

        await redis_manager.update_task_status(
            job_id=job_id,
            status='DONE',
            result=serialized_result,
            extra={
                'completed_at': completed_at,
                'approval_pending': False,
            }
        )
        logger.info('Tarea finalizada con exito DONE: ' + str(job_id))

    except Exception as e:
        error_msg = str(e)
        stack = traceback.format_exc()
        logger.error('ERROR critico procesando tarea ' + str(job_id) + ': ' + error_msg)

        await redis_manager.update_task_status(
            job_id=job_id,
            status='FAILED',
            error=error_msg,
            extra={
                'failed_at': datetime.now(timezone.utc).isoformat(),
                'stack_trace': stack,
            }
        )


async def resume_task_after_approval(
    job_id: str,
    approved: bool,
    comments: str = '',
    approver: str = 'operador_humano'
) -> dict[str, Any]:
    logger.info('Reanudando tarea tras decision HITL: ' + str(job_id))

    checkpointer = await redis_manager.get_checkpointer()
    graph = build_multi_agent_graph(checkpointer=checkpointer)
    thread_config = 'configurable'
    config_dict = {thread_config: {'thread_id': job_id}}

    await redis_manager.update_task_status(
        job_id=job_id,
        status='RUNNING',
        extra={'last_approval_decision': {'approved': approved, 'approver': approver, 'comments': comments}}
    )

    try:
        resume_command = Command(resume={
            'approved': approved,
            'comments': comments,
            'approver': approver,
        })

        final_state: Optional[dict[str, Any]] = None
        async for chunk in graph.astream(resume_command, config=config_dict, stream_mode='values'):
            final_state = chunk

        completed_at = datetime.now(timezone.utc).isoformat()
        serialized_result = _extract_task_summary(final_state)

        updated = await redis_manager.update_task_status(
            job_id=job_id,
            status='DONE',
            result=serialized_result,
            extra={
                'completed_at': completed_at,
                'approval_pending': False,
            }
        )
        logger.info('Tarea reanudada y finalizada con exito: ' + str(job_id))
        return updated

    except Exception as e:
        error_msg = str(e)
        logger.error('Error reanudando tarea: ' + error_msg)
        return await redis_manager.update_task_status(
            job_id=job_id,
            status='FAILED',
            error=error_msg,
            extra={'failed_at': datetime.now(timezone.utc).isoformat()}
        )


def _serialize_artifact(artifact: Any) -> Any:
    if artifact is None:
        return None
    if hasattr(artifact, 'model_dump'):
        return artifact.model_dump()
    if isinstance(artifact, dict):
        return artifact
    return str(artifact)


def _extract_task_summary(state: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not state:
        return {'summary': 'Sin datos de salida'}

    last_message = ''
    messages = state.get('messages', [])
    if messages:
        last = messages[-1]
        last_message = last.content if hasattr(last, 'content') else str(last)

    summary: dict[str, Any] = {
        'final_message': last_message,
        'iterations': state.get('iterations', 0),
        'researcher_output': _serialize_artifact(state.get('researcher_output')),
        'analyst_output': _serialize_artifact(state.get('analyst_output')),
        'validation_output': _serialize_artifact(state.get('validation_output')),
    }
    return summary