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
    # None means "never run", and _loop treats that as due immediately.
    #
    # This was 0.0, which is wrong for a monotonic clock. time.monotonic() on
    # Windows is milliseconds since boot, not seconds since the epoch, so 0.0 is
    # not "infinitely long ago" but "at boot". A task registered with a 3600 s
    # interval was therefore not due on the first tick until the machine had been
    # up for an hour: `learning` sat idle for up to ENGINE_INTERVAL_OPTIMIZE
    # seconds after every restart, and the delay was longest on a freshly booted
    # machine, which is exactly what a deploy produces.
    last_run: float | None = None
    task: asyncio.Task | None = None
    enabled: bool = True
    running: bool = False
    error_count: int = 0
    last_error: str | None = None


class Scheduler:
    """Async scheduler that runs tasks at fixed intervals.

    Task bodies are serialized on a single lock. Engine jobs share mutable
    module state (prices, analyses, signals, the ICT position manager) and
    ``monitor_positions`` ticks every 10s alongside ``execute_trades``; running
    two of them at once could double-sell or double-count. The lock makes that
    guarantee explicit instead of relying on the bodies happening to contain no
    await points.

    Serialization must not mean blocking the event loop: the task bodies perform
    synchronous network and disk I/O, which is why they are awaited in a worker
    thread (see ``_run_task``). Holding the lock across that await keeps the
    jobs mutually exclusive while leaving the HTTP server free to answer.
    """

    def __init__(self):
        self._tasks: dict[str, ScheduledTask] = {}
        self._running = False
        self._loop_task: asyncio.Task | None = None
        self._run_lock = asyncio.Lock()
        # Called when a tick dispatches work. The engine uses it to advance the
        # cycle id, so every event written during that tick shares one id.
        self.on_dispatch = None

    def _on_dispatch(self, task_count: int) -> None:
        if self.on_dispatch is not None:
            try:
                self.on_dispatch(task_count)
            except Exception:  # pragma: no cover - a hook must not stop the engine
                logger.exception("Dispatch hook failed")


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
            dispatched: list[ScheduledTask] = []
            for task in self._tasks.values():
                if not task.enabled:
                    continue
                if task.running:
                    continue
                if task.last_run is None or now - task.last_run >= task.interval:
                    dispatched.append(task)
            if dispatched:
                # One cycle per tick that actually did work. The cycle id is what
                # groups a pass of the engine in the log, so it has to advance
                # when work starts, not when something is logged.
                self._on_dispatch(len(dispatched))
                for task in dispatched:
                    task.running = True
                    task.last_run = now
                    task.task = asyncio.create_task(self._run_task(task))
            await asyncio.sleep(1)  # Tick every second

    async def _run_task(self, task: ScheduledTask) -> None:
        """Execute a single task with error handling."""
        try:
            async with self._run_lock:
                if asyncio.iscoroutinefunction(task.func):
                    await task.func()
                else:
                    # A plain callable may be blocking I/O. Handing it to a
                    # worker thread is what keeps the event loop responsive;
                    # calling it inline would stall every concurrent request,
                    # including the orchestrator's liveness probe.
                    await asyncio.to_thread(task.func)
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
        # Reset to "never run" rather than to 0, which on a monotonic clock means
        # "at boot" and would leave a long-interval task not due yet.
        task.last_run = None  # Force immediate execution
        return True


# Global scheduler instance
scheduler = Scheduler()
