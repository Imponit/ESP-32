"""Тонкий интерфейс фоновых задач (SPEC.md, раздел 2).

Сейчас — asyncio.create_task внутри процесса backend; при росте нагрузки
реализацию можно заменить (например, на отдельный воркер), не меняя сервисы.
Celery/RQ/Redis не используем намеренно.
"""

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any, Protocol

logger = logging.getLogger("task_runner")


class TaskRunner(Protocol):
    def submit(self, coro: Coroutine[Any, Any, Any]) -> None: ...


class AsyncioTaskRunner:
    """Запускает корутину фоновой asyncio-задачей в текущем event loop."""

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task] = set()

    def submit(self, coro: Coroutine[Any, Any, Any]) -> None:
        task = asyncio.get_running_loop().create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._on_done)

    def _on_done(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        if not task.cancelled() and task.exception():
            logger.exception("Фоновая задача упала", exc_info=task.exception())


class InlineTaskRunner:
    """Для тестов: выполняет задачу сразу (await)."""

    async def submit_and_wait(self, coro: Coroutine[Any, Any, Any]) -> None:
        await coro

    def submit(self, coro: Coroutine[Any, Any, Any]) -> None:
        asyncio.get_event_loop().create_task(coro)


task_runner = AsyncioTaskRunner()
