# Capa de Persistencia con Redis: Gestor de Estado y Checkpointer para LangGraph
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional
import redis.asyncio as aioredis
from langgraph.checkpoint.base import BaseCheckpointSaver

logger = logging.getLogger('redis_store')
TASK_PREFIX = 'preentrega7:job:'


class RedisStateManager:
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        self._redis_client: Optional[aioredis.Redis] = None
        self._use_in_memory: bool = False
        self._memory_store: dict[str, str] = {}
        self._checkpointer: Optional[BaseCheckpointSaver] = None

    async def connect(self) -> None:
        try:
            client = aioredis.from_url(self.redis_url, decode_responses=True)
            await client.ping()
            self._redis_client = client
            self._use_in_memory = False
            logger.info(f'[RedisStateManager] Conectado a Redis en {self.redis_url}')
        except Exception as e:
            logger.warning(
                f'[RedisStateManager] No se pudo conectar a Redis ({e}). '
                'Activando almacenamiento compatible en memoria.'
            )
            self._use_in_memory = True

    async def close(self) -> None:
        if self._redis_client:
            await self._redis_client.close()

    async def set_task_state(self, job_id: str, state_data: dict[str, Any], ttl_seconds: int = 86400) -> None:
        key = f'{TASK_PREFIX}{job_id}'
        serialized = json.dumps(state_data, ensure_ascii=False)
        if not self._use_in_memory and self._redis_client:
            await self._redis_client.set(key, serialized, ex=ttl_seconds)
        else:
            self._memory_store[key] = serialized

    async def get_task_state(self, job_id: str) -> Optional[dict[str, Any]]:
        key = f'{TASK_PREFIX}{job_id}'
        if not self._use_in_memory and self._redis_client:
            raw = await self._redis_client.get(key)
        else:
            raw = self._memory_store.get(key)

        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    async def update_task_status(
        self,
        job_id: str,
        status: str,
        result: Optional[Any] = None,
        error: Optional[str] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        current = await self.get_task_state(job_id) or {'job_id': job_id}
        current['status'] = status
        if result is not None:
            current['result'] = result
        if error is not None:
            current['error'] = error
        if extra:
            current.update(extra)

        await self.set_task_state(job_id, current)
        return current

    async def get_checkpointer(self) -> BaseCheckpointSaver:
        if self._checkpointer is not None:
            return self._checkpointer

        if not self._use_in_memory and self._redis_client:
            try:
                from langgraph.checkpoint.redis.aio import AsyncRedisSaver
                saver = AsyncRedisSaver(redis_url=self.redis_url)
                await saver.setup()
                self._checkpointer = saver
                logger.info('[RedisStateManager] AsyncRedisSaver configurado correctamente.')
                return saver
            except Exception as ex:
                logger.warning(f'[RedisStateManager] AsyncRedisSaver error ({ex}), usando SQLite.')

        try:
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
            import aiosqlite
            db_path = os.getenv('SQLITE_CHECKPOINT_DB', 'state_checkpoints.db')
            conn = await aiosqlite.connect(db_path)
            saver = AsyncSqliteSaver(conn)
            self._checkpointer = saver
            logger.info(f'[RedisStateManager] Checkpointer SQLite activo en {db_path}')
            return saver
        except Exception:
            from langgraph.checkpoint.memory import MemorySaver
            saver = MemorySaver()
            self._checkpointer = saver
            return saver


redis_manager = RedisStateManager()
