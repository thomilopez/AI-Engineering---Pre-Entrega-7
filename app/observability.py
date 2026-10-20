# Observabilidad y Trazado: Arize Phoenix + LangSmith
from __future__ import annotations

import logging
import os
import sys
import functools
from typing import Any, Callable

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

logger = logging.getLogger('observability')
_instrumented = False
_phoenix_session = None
_tracer_provider = None


def setup_observability() -> dict[str, Any]:
    global _instrumented, _phoenix_session, _tracer_provider
    status = {
        'phoenix_active': False,
        'phoenix_ui_url': None,
        'langsmith_active': False,
        'langsmith_project': None,
    }

    # 1. LangSmith (Trazabilidad cloud nativa)
    langsmith_api_key = os.getenv('LANGCHAIN_API_KEY')
    langsmith_tracing = os.getenv('LANGCHAIN_TRACING_V2', 'false').lower() == 'true'
    if langsmith_api_key and langsmith_tracing:
        project = os.getenv('LANGCHAIN_PROJECT', 'preentrega-7-mas-api')
        status['langsmith_active'] = True
        status['langsmith_project'] = project
        logger.info(f'[Observabilidad] LangSmith activo en proyecto {project}')

    # 2. Arize Phoenix (Servidor y exportador OpenTelemetry)
    enable_phoenix = os.getenv('ENABLE_PHOENIX', 'true').lower() == 'true'
    if enable_phoenix and not _instrumented:
        try:
            import phoenix as px
            from phoenix.otel import register
            from openinference.instrumentation.langchain import LangChainInstrumentor

            port = int(os.getenv('PHOENIX_PORT', '6006'))
            try:
                _phoenix_session = px.launch_app(port=port)
                ui_url = f'http://localhost:{port}'
                status['phoenix_ui_url'] = ui_url
                logger.info(f'[Observabilidad] Arize Phoenix UI iniciado en: {ui_url}')
            except Exception as ex:
                ui_url = f'http://localhost:{port}'
                status['phoenix_ui_url'] = ui_url
                logger.info(f'[Observabilidad] Conectando a Phoenix existente en: {ui_url} ({ex})')

            # Registrar tracer_provider hacia http://127.0.0.1:6006/v1/traces en proyecto default
            _tracer_provider = register(
                project_name='default',
                endpoint=f'http://127.0.0.1:{port}/v1/traces'
            )

            LangChainInstrumentor().instrument(tracer_provider=_tracer_provider)
            _instrumented = True
            status['phoenix_active'] = True
            logger.info('[Observabilidad] Phoenix LangChainInstrumentor registrado correctamente en proyecto default.')
        except Exception as e:
            logger.error(f'[Observabilidad] Error configurando Arize Phoenix: {e}')

    return status


def flush_phoenix_traces() -> None:
    global _tracer_provider
    if _tracer_provider is not None:
        try:
            _tracer_provider.force_flush()
        except Exception:
            pass


def trace_agent_execution(agent_name: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger.info(f'[TraceSpan:START] Componente {agent_name}')
            try:
                result = await func(*args, **kwargs)
                logger.info(f'[TraceSpan:SUCCESS] Componente {agent_name} finalizado exitosamente.')
                return result
            except Exception as exc:
                logger.error(f'[TraceSpan:ERROR] Fallo en {agent_name}: {exc}')
                raise exc
        return wrapper
    return decorator