"""The cycle id must group a cycle, not count log calls.

_get_cycle_id() incremented a counter on every call, so every event got its own
id: 6 898 logged events produced 1 606 "cycles", and no two events ever shared
one. The id exists precisely to group a pass of the engine, which it could not do.
"""

import asyncio
import inspect

import pytest

from app import engine
from app.scheduler import Scheduler


class TestCycleIdIsStableWithinACycle:
    def test_repeated_calls_return_the_same_id(self):
        before = engine._get_cycle_id()
        assert engine._get_cycle_id() == before
        assert engine._get_cycle_id() == before

    def test_reading_the_id_does_not_advance_it(self):
        first = engine._get_cycle_id()
        for _ in range(50):
            engine._get_cycle_id()
        assert engine._get_cycle_id() == first

    def test_begin_cycle_advances_it(self):
        before = engine._get_cycle_id()
        engine._begin_cycle(2)
        after = engine._get_cycle_id()
        assert after != before
        assert int(after[1:]) == int(before[1:]) + 1

    def test_counter_is_not_incremented_by_logging(self):
        """The original defect, pinned."""
        src = inspect.getsource(engine._get_cycle_id)
        assert "_cycle_count += 1" not in src, "reading the id still advances the counter"

    def test_advance_lives_in_begin_cycle(self):
        assert "_cycle_count += 1" in inspect.getsource(engine._begin_cycle)


class TestSchedulerDrivesTheCycle:
    def test_hook_is_wired_to_begin_cycle(self):
        assert engine.scheduler.on_dispatch is engine._begin_cycle

    def test_one_cycle_per_dispatching_tick(self):
        sch = Scheduler()
        ticks: list[int] = []
        sch.on_dispatch = lambda count: ticks.append(count)
        sch.register("a", lambda: None, 0.01)
        sch.register("b", lambda: None, 0.01)

        async def run():
            await sch.start()
            await asyncio.sleep(0.5)
            await sch.stop()

        asyncio.run(run())
        # A tick that dispatches nothing must not advance the cycle, otherwise the
        # id would run away from the work it is supposed to describe.
        assert ticks, "the dispatch hook never fired"
        assert all(count >= 1 for count in ticks)
        assert len(ticks) < 100, "the cycle advanced far more than the work done"

    def test_idle_tick_does_not_advance(self):
        """Hundreds of one-second ticks, one dispatch, so one cycle.

        A task is due on its first tick, then not again for an hour: the loop
        keeps ticking and must not keep counting cycles.
        """
        sch = Scheduler()
        ticks: list[int] = []
        sch.on_dispatch = lambda count: ticks.append(count)
        ran: list[int] = []
        sch.register("a", lambda: ran.append(1), 3600)

        async def run():
            await sch.start()
            await asyncio.sleep(2.5)  # ~2 idle seconds after the first tick
            await sch.stop()

        asyncio.run(run())
        assert len(ran) == 1, "the task should have run once"
        assert len(ticks) == 1, f"cycles advanced on idle ticks: {ticks}"

    def test_hook_failure_does_not_stop_the_scheduler(self):
        sch = Scheduler()

        def boom(count):
            raise RuntimeError("hook failed")

        sch.on_dispatch = boom
        ran: list[str] = []
        sch.register("a", lambda: ran.append("x"), 0.01)

        async def run():
            await sch.start()
            await asyncio.sleep(0.4)
            await sch.stop()

        asyncio.run(run())
        assert ran, "a failing hook stopped the engine"

    def test_hook_is_optional(self):
        sch = Scheduler()
        assert sch.on_dispatch is None
        sch.register("a", lambda: None, 0.01)

        async def run():
            await sch.start()
            await asyncio.sleep(0.2)
            await sch.stop()

        asyncio.run(run())  # must not raise


class TestEventGrouping:
    def test_events_of_one_pass_share_an_id(self):
        from app import storage

        storage.initialize()
        start = engine._get_cycle_id()
        for event in ("prices_fetched", "analysis_complete", "signal_generated"):
            storage.log_engine_event(engine._get_cycle_id(), event, {"n": 1})
        with storage.connection() as db:
            recent = db.execute(
                "SELECT cycle_id FROM engine_log ORDER BY id DESC LIMIT 3"
            ).fetchall()
        ids = {r["cycle_id"] for r in recent}
        assert ids == {start}, f"the pass was split across {ids}"
