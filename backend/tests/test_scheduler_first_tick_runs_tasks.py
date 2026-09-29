"""A task must run on the scheduler's first tick, whatever the interval.

`_loop` decided whether a task was due with:

    if now - task.last_run >= task.interval:

and `ScheduledTask.last_run` started at `0.0`. That is only correct for a clock
measured from the epoch. `time.monotonic()` on Windows is milliseconds since
boot, so `0.0` does not mean "infinitely long ago" but "at boot", and a task
registered with a long interval was not due on the first tick until the machine
had been up for that long.

Measured on a machine with 3 146 s of uptime, a task registered at 3 600 s
(ENGINE_INTERVAL_OPTIMIZE, the `learning` job) never ran: `now - 0` fell short of
the interval by ~450 s, and the tick loop re-checked every second. The same
arithmetic made `trigger_now`, which set `last_run = 0` for the same reason, a
no-op for any interval longer than the uptime.

The production shape of this is a restart. A freshly booted machine has a
monotonic clock near zero, so the delay was longest exactly when it matters:
`learning` sat idle for up to a full hour after each deploy. The intervals
registered by the engine are 10, 15, 30, 60, 300, 600 and 3 600 seconds, so
`learning` was the one exposed; ENGINE_INTERVAL_DAILY_REPORT (86 400 s, not
currently registered) would have been delayed by up to a day.

These tests pin the invariant by simulating a boot, so they hold regardless of
how long the machine running them has been up. `test_idle_tick_does_not_advance`
in test_cycle_id.py caught this in practice, but only while that machine's
uptime happened to be under the interval.
"""

import asyncio
import time
import types

import pytest

from app import scheduler as scheduler_mod
from app.scheduler import Scheduler

# The scheduler's loop sleeps one real second per tick, so letting a tick
# happen takes real time. Anything under this starves the first tick.
TICK = 1.2


@pytest.fixture
def fresh_boot(monkeypatch):
    """Make the scheduler's clock look like a machine that just booted.

    Replaces the `time` name inside the scheduler module with a shim rather than
    patching `time.monotonic` itself: asyncio reads the same module for its own
    event loop clock, so patching the real one deadlocks every `await`.
    """
    fake = {"t": 0.0}
    shim = types.SimpleNamespace(monotonic=lambda: fake["t"])
    monkeypatch.setattr(scheduler_mod, "time", shim)
    return fake


async def _tick(fake, count=1):
    """Advance the fake clock across `count` real scheduler ticks."""
    for _ in range(count):
        await asyncio.sleep(TICK)
        fake["t"] += 1.0


@pytest.mark.parametrize("interval", [3600, 86400, 10, 60, 600])
def test_a_freshly_booted_machine_runs_its_tasks_immediately(fresh_boot, interval):
    """The first tick must find every registered task due.

    3 600 and 86 400 are the intervals that were affected: with `last_run = 0`
    against a monotonic clock starting near zero, neither could ever come due.
    """
    sch = Scheduler()
    ran: list[int] = []
    sch.register("job", lambda: ran.append(1), interval)

    async def drive():
        await sch.start()
        await _tick(fresh_boot)
        await sch.stop()

    asyncio.run(drive())
    assert ran == [1]


def test_a_long_interval_task_runs_again_only_after_its_interval(fresh_boot):
    """Fixing the startup case must not turn the interval into a no-op."""
    sch = Scheduler()
    ran: list[int] = []
    sch.register("learning", lambda: ran.append(1), 3600)

    async def drive():
        await sch.start()
        await _tick(fresh_boot)
        assert len(ran) == 1
        # Nine more ticks, still inside the 3 600 s interval.
        await _tick(fresh_boot, 9)
        assert len(ran) == 1
        fresh_boot["t"] += 3600
        await _tick(fresh_boot, 2)
        await sch.stop()

    asyncio.run(drive())
    assert len(ran) == 2


def test_trigger_now_forces_a_long_interval_task_to_run(fresh_boot):
    """`trigger_now` used to set last_run = 0, which means 'at boot', not 'now'."""
    sch = Scheduler()
    ran: list[int] = []
    sch.register("learning", lambda: ran.append(1), 3600)

    async def drive():
        await sch.start()
        await _tick(fresh_boot)
        assert len(ran) == 1
        assert sch.get_status()["tasks"]["learning"]["last_run"] is not None

        sch.trigger_now("learning")
        assert sch.get_status()["tasks"]["learning"]["last_run"] is None
        await _tick(fresh_boot, 2)
        await sch.stop()

    asyncio.run(drive())
    assert len(ran) == 2


def test_trigger_now_refuses_unknown_names(fresh_boot):
    sch = Scheduler()
    assert sch.trigger_now("missing") is False


def test_get_status_reports_never_run_as_null(fresh_boot):
    """None is the 'never run' sentinel; status must not imply a real timestamp."""
    sch = Scheduler()
    sch.register("job", lambda: None, 3600)
    assert sch.get_status()["tasks"]["job"]["last_run"] is None


def test_monotonic_on_this_platform_is_not_the_epoch():
    """The reason the sentinel was needed, pinned against the real clock.

    If a future change made 0.0 mean 'long ago' again, this fails loudly.
    """
    assert time.monotonic() < 1e10
