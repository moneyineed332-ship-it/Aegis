"""Lightweight async scheduler for periodic engine tasks.

Uses asyncio tasks with configurable intervals. No external dependencies.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ScheduledTask:
    """A single periodic task."""
    name: str
    func: callable
    interval: float  # seconds
    last_run: float = 0.0
    task: asyncio.Task | None = None
    enabled: bool = True
    running: bool = False
    error_count: int = 0
    last_error: str | None = None


class Scheduler:
    """Async scheduler that runs tasks at fixed intervals."""

    def __init__(self):
        self._tasks: dict[str, ScheduledTask] = {}
        self._running = False
        self._loop_task: asyncio.Task | None = None

    def register(self, name: str, func: callable, interval: float) -> None:
        """Register a periodic task."""
        self._tasks[name] = ScheduledTask(name=name, func=func, interval=interval)
        logger.info("Registered task '%s' with interval %ds", name, interval)

    def unregister(self, name: str) -> None:
        """Unregister a task."""
        task = self._tasks.pop(name, None)
        if task and task.task and not task.task.done():
            task.task.cancel()

    def update_interval(self, name: str, interval: float) -> None:
        """Update a task's interval."""
        if name in self._tasks:
            self._tasks[name].interval = interval
            logger.info("Updated task '%s' interval to %ds", name, interval)

    def enable(self, name: str) -> None:
        if name in self._tasks:
            self._tasks[name].enabled = True

    def disable(self, name: str) -> None:
        if name in self._tasks:
            self._tasks[name].enabled = False

    async def start(self) -> None:
        """Start the scheduler loop."""
        if self._running:
            return
        self._running = True
        self._loop_task = asyncio.create_task(self._loop())
        logger.info("Scheduler started with %d tasks", len(self._tasks))

    async def stop(self) -> None:
        """Stop the scheduler gracefully."""
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        # Cancel all pending tasks
        for task in self._tasks.values():
            if task.task and not task.task.done():
                task.task.cancel()
        logger.info("Scheduler stopped")

    async def _loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            now = time.monotonic()
            for task in self._tasks.values():
                if not task.enabled:
                    continue
                if task.running:
                    continue
                if now - task.last_run >= task.interval:
                    task.running = True
                    task.last_run = now
                    task.task = asyncio.create_task(self._run_task(task))
            await asyncio.sleep(1)  # Tick every second

    async def _run_task(self, task: ScheduledTask) -> None:
        """Execute a single task with error handling."""
        try:
            if asyncio.iscoroutinefunction(task.func):
                await task.func()
            else:
                task.func()
            task.error_count = 0
            task.last_error = None
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            task.error_count += 1
            task.last_error = str(exc)
            logger.error("Task '%s' error (#%d): %s", task.name, task.error_count, exc, exc_info=True)
        finally:
            task.running = False

    def get_status(self) -> dict:
        """Get scheduler and task status."""
        return {
            "running": self._running,
            "tasks": {
                name: {
                    "interval": task.interval,
                    "enabled": task.enabled,
                    "last_run": task.last_run,
                    "error_count": task.error_count,
                    "last_error": task.last_error,
                }
                for name, task in self._tasks.items()
            },
        }

    def trigger_now(self, name: str) -> bool:
        """Immediately schedule a task for execution."""
        task = self._tasks.get(name)
        if not task or task.running:
            return False
        task.last_run = 0  # Force immediate execution
        return True


# Global scheduler instance
scheduler = Scheduler()
