# Observabilidad y Trazado: Arize Phoenix + LangSmith
from __future__ import annotations

import logging
import os
import io
import sys
import functools
from typing import Any, Callable

# Proteccion para Windows CP1252 ante caracteres de Phoenix
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

logger = logging.getLogger('observability')
_instrumented = False
_phoenix_session = None


def setup_observability() -> dict[str, Any]:
    global _instrumented, _phoenix_session
    status = {
        'phoenix_active': False,
        'phoenix_ui_url': None,
        'langsmith_active': False,
        'langsmith_project': None,
    }

    # 1. LangSmith (OpenAI / DeepSeek / LangChain Native)
    langsmith_api_key = os.getenv('LANGCHAIN_API_KEY')
    langsmith_tracing = os.getenv('LANGCHAIN_TRACING_V2', 'false').lower() == 'true'
    if langsmith_api_key and langsmith_tracing:
        project = os.getenv('LANGCHAIN_PROJECT', 'preentrega-7-mas-api')
        status['langsmith_active'] = True
        status['langsmith_project'] = project
        logger.info(f'[Observabilidad] LangSmith activo en proyecto {project}')

    # 2. Arize Phoenix
    enable_phoenix = os.getenv('ENABLE_PHOENIX', 'true').lower() == 'true'
    if enable_phoenix and not _instrumented:
        try:
            import phoenix as px
            from openinference.instrumentation.langchain import LangChainInstrumentor

            port = int(os.getenv('PHOENIX_PORT', '6006'))
            try:
                _phoenix_session = px.launch_app(port=port)
                ui_url = f'http://localhost:{port}'
                status['phoenix_ui_url'] = ui_url
                logger.info(f'[Observabilidad] Arize Phoenix UI iniciado en: {ui_url}')
            except Exception as ex:
                logger.info(f'[Observabilidad] Servidor Phoenix activo en puerto {port} ({ex})')
                ui_url = f'http://localhost:{port}'
                status['phoenix_ui_url'] = ui_url

            # Instrumentar LangChain con Phoenix
            LangChainInstrumentor().instrument()
            _instrumented = True
            status['phoenix_active'] = True
            logger.info('[Observabilidad] Phoenix LangChainInstrumentor activo.')
        except Exception as e:
            logger.error(f'[Observabilidad] Error configurando Arize Phoenix: {e}')

    return status


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