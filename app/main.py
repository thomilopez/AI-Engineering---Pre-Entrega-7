# API REST Asincrona con FastAPI - Preentrega 7
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any, Optional
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from app.observability import setup_observability
from app.redis_state import redis_manager
from app.worker import execute_task_background, resume_task_after_approval
from app.hitl import ApprovalRequest

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger('api')


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info('Iniciando servicios de API y persistencia...')
    obs_status = setup_observability()
    logger.info(f'Observabilidad: {obs_status}')
    await redis_manager.connect()
    yield
    logger.info('Cerrando conexiones de API...')
    await redis_manager.close()


app = FastAPI(
    title='Orquestador Multi-Agente Asincrono - Pre-entrega 7',
    description='API REST de produccion con FastAPI, Redis, HITL y Observabilidad.',
    version='1.0.0',
    lifespan=lifespan,
)


class CreateTaskRequest(BaseModel):
    prompt: str = Field(..., min_length=5, description='Descripcion de la tarea a ejecutar.')


class TaskResponse(BaseModel):
    job_id: str
    status: str
    created_at: str
    message: str


class TaskStatusResponse(BaseModel):
    job_id: str
    status: str
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    failed_at: Optional[str] = None
    approval_pending: Optional[bool] = False
    interrupt_details: Optional[Any] = None
    result: Optional[Any] = None
    error: Optional[str] = None


@app.get('/', tags=['Health'])
async def root():
    return {
        'service': 'Multi-Agent Async Orchestrator API',
        'module': 'Pre-entrega 7 - AI Engineering',
        'status': 'ONLINE',
        'docs_url': '/docs',
    }


@app.get('/health', tags=['Health'])
async def health_check():
    return {
        'status': 'healthy',
        'redis_connected': not redis_manager._use_in_memory,
        'storage_mode': 'Redis' if not redis_manager._use_in_memory else 'InMemoryCompatible',
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }


@app.post('/tasks', response_model=TaskResponse, status_code=status.HTTP_202_ACCEPTED, tags=['Tasks'])
async def create_task(request: CreateTaskRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    initial_payload = {
        'job_id': job_id,
        'prompt': request.prompt,
        'status': 'PENDING',
        'created_at': created_at,
        'approval_pending': False,
        'result': None,
        'error': None,
    }
    await redis_manager.set_task_state(job_id, initial_payload)

    background_tasks.add_task(execute_task_background, job_id, request.prompt)
    logger.info(f'[API] Tarea encolada: job_id={job_id}')

    return TaskResponse(
        job_id=job_id,
        status='PENDING',
        created_at=created_at,
        message='Tarea encolada correctamente. Consulte /tasks/{id} para seguir su evolucion.',
    )


@app.get('/tasks/{job_id}', response_model=TaskStatusResponse, tags=['Tasks'])
async def get_task_status(job_id: str):
    task_data = await redis_manager.get_task_state(job_id)
    if not task_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'No se encontro la tarea con job_id {job_id}.'
        )
    return task_data


@app.post('/tasks/{job_id}/approve', response_model=TaskStatusResponse, tags=['Human-in-the-Loop'])
async def approve_task(job_id: str, request: ApprovalRequest):
    task_data = await redis_manager.get_task_state(job_id)
    if not task_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'No se encontro la tarea con job_id {job_id}.'
        )

    current_status = task_data.get('status')
    if current_status != 'WAITING_APPROVAL':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'La tarea no se encuentra esperando aprobacion. Estado actual: {current_status}.'
        )

    resumed_data = await resume_task_after_approval(
        job_id=job_id,
        approved=request.approved,
        comments=request.comments,
        approver=request.approver,
    )
    return resumed_data
