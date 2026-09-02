"""
Asynchronous background task runner and worker pool.
"""
import asyncio
from typing import Any, Callable, Coroutine, List

from loguru import logger


class AsyncTaskRunner:
    """
    Manages non-blocking concurrent task executions.
    """

    def __init__(self, max_concurrent: int = 5):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.running_tasks: List[asyncio.Task] = []

    async def submit(self, coro_func: Callable[[], Coroutine[Any, Any, Any]], task_name: str = "task"):
        async def _wrapper():
            async with self.semaphore:
                try:
                    logger.debug(f"Starting async task: {task_name}")
                    res = await coro_func()
                    return res
                except Exception as e:
                    logger.error(f"Task {task_name} error: {e}")

        t = asyncio.create_task(_wrapper())
        self.running_tasks.append(t)
        return t

    async def wait_all(self):
        if self.running_tasks:
            await asyncio.gather(*self.running_tasks, return_exceptions=True)
            self.running_tasks.clear()
