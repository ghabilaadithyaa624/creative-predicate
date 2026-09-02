"""
Periodic scheduler for market scans, reporting, and settlement checks.
"""
from datetime import datetime
from typing import Callable, List, Optional, Any
import asyncio
from loguru import logger


class ScheduledTask:
    def __init__(self, name: str, interval_seconds: float, action: Callable[[], Any]):
        self.name = name
        self.interval_seconds = interval_seconds
        self.action = action
        self.last_run: Optional[datetime] = None
        self.run_count: int = 0
        self.enabled: bool = True


class CronScheduler:
    """
    Async periodic task scheduler for autonomous trading loops.
    """

    def __init__(self):
        self.tasks: List[ScheduledTask] = []
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None

    def add_job(self, name: str, interval_seconds: float, action: Callable[[], Any]) -> ScheduledTask:
        task = ScheduledTask(name=name, interval_seconds=interval_seconds, action=action)
        self.tasks.append(task)
        return task

    async def start(self):
        self._running = True
        logger.info(f"CronScheduler started with {len(self.tasks)} jobs.")
        while self._running:
            now = datetime.now()
            for task in self.tasks:
                if not task.enabled:
                    continue

                should_run = False
                if task.last_run is None:
                    should_run = True
                else:
                    elapsed = (now - task.last_run).total_seconds()
                    if elapsed >= task.interval_seconds:
                        should_run = True

                if should_run:
                    task.last_run = now
                    task.run_count += 1
                    try:
                        res = task.action()
                        if asyncio.iscoroutine(res):
                            await res
                    except Exception as e:
                        logger.error(f"Error executing scheduled job '{task.name}': {e}")

            await asyncio.sleep(1.0)

    def stop(self):
        self._running = False
        logger.info("CronScheduler stopped.")
