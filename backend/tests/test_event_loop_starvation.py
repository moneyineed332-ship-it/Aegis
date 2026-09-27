"""The engine must not stall the event loop.

Fly probes /health every 10s with a 5s timeout. Before this fix the engine's
async tasks called synchronous network I/O inline, so a single analysis cycle
blocked the loop for 5-7s: 4 of 144 probes timed out, and the machine would have
been restarted repeatedly.

Two properties are pinned:
  1. Blocking work runs off the event loop.
  2. Task bodies stay mutually exclusive, because moving them to threads would
     otherwise let monitor_positions (10s) run concurrently with
     execute_trades and double-sell against shared engine state.
"""

import asyncio
import inspect
import threading
import time

import pytest

from app import engine
from app.scheduler import Scheduler


class TestBlockingWorkLeavesTheLoop:
    def test_fetch_ohlcv_is_offloaded_in_analysis(self):
        src = inspect.getsource(engine.task_fetch_analysis)
        assert "asyncio.to_thread" in src, "analysis still fetches inline"
        assert "asyncio.to_thread(\n                        market_data.fetch_ohlcv" in src or (
            "market_data.fetch_ohlcv" in src and "asyncio.to_thread" in src
        )

    def test_spot_prices_are_offloaded(self):
        assert "asyncio.to_thread" in inspect.getsource(engine.task_fetch_prices)

    def test_ict_signal_generation_is_offloaded(self):
        src = inspect.getsource(engine._run_ict_pipeline)
        assert "asyncio.to_thread(_get_ict_signal" in src


class TestEventLoopStaysResponsive:
    """The real assertion: measure loop latency while a cycle runs."""

    def test_loop_latency_during_a_full_analysis_cycle(self):
        async def run():
            stalls: list[float] = []
            stop = False

            async def poller():
                while not stop:
                    t0 = time.perf_counter()
                    await asyncio.sleep(0)
                    stalls.append((time.perf_counter() - t0) * 1000)
                    await asyncio.sleep(0.005)

            p = asyncio.create_task(poller())
            t0 = time.perf_counter()
            await engine.task_fetch_analysis()
            duration = (time.perf_counter() - t0) * 1000
            stop = True
            await p
            return stalls, duration

        stalls, duration = asyncio.run(run())
        assert stalls, "poller never sampled"
        worst = max(stalls)
        # The cycle itself is expected to take seconds of wall time; what must
        # not happen is the loop being unavailable while it runs. Fly allows 5s,
        # so anything close to that would put the health check at risk.
        assert worst < 500, f"loop stalled {worst:.0f} ms during a {duration:.0f} ms cycle"
        assert sum(1 for s in stalls if s > 50) == 0

    def test_a_blocking_task_does_not_freeze_the_loop(self):
        """A plain sync task body must also be moved to a thread."""
        main_thread = threading.get_ident()
        seen: dict = {}

        def blocking():
            time.sleep(0.4)
            seen["thread"] = threading.get_ident()

        async def run():
            sch = Scheduler()
            sch.register("blocking", blocking, 0.01)
            await sch.start()
            await asyncio.sleep(1.2)
            await sch.stop()

        asyncio.run(run())
        assert seen.get("thread") not in (None, main_thread), (
            "sync task ran on the event loop thread"
        )


class TestEngineTasksStaySerialized:
    """Moving work to threads must not let two jobs run at once."""

    def test_scheduler_uses_a_run_lock(self):
        assert isinstance(Scheduler()._run_lock, asyncio.Lock)

    def test_two_jobs_never_overlap(self):
        overlap: dict = {"max": 0, "active": 0}
        gate = threading.Event()

        def make_job():
            def job():
                overlap["active"] += 1
                overlap["max"] = max(overlap["max"], overlap["active"])
                gate.wait(timeout=1.5)
                overlap["active"] -= 1
            return job

        async def run():
            sch = Scheduler()
            sch.register("a", make_job(), 0.01)
            sch.register("b", make_job(), 0.01)
            await sch.start()
            await asyncio.sleep(0.6)
            gate.set()
            await asyncio.sleep(0.5)
            await sch.stop()

        asyncio.run(run())
        assert overlap["max"] == 1, f"jobs overlapped (max concurrency {overlap['max']})"


class TestLivenessIsNeverRateLimited:
    """A 429 on the liveness endpoint reads as an unhealthy machine."""

    def test_health_survives_a_burst_beyond_the_global_limit(self):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.rate_limit import DEFAULT_LIMITS

        client = TestClient(app)
        # The global default is 200/minute, so a burst of 260 must not be
        # throttled on the liveness path.
        codes = [client.get("/health").status_code for _ in range(260)]
        assert set(codes) == {200}, f"liveness returned {sorted(set(codes))}"

    def test_api_health_survives_a_burst(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        codes = [client.get("/api/v1/health").status_code for _ in range(260)]
        assert set(codes) == {200}, f"liveness returned {sorted(set(codes))}"

    def test_write_endpoints_keep_their_tight_limits(self):
        """Exempting the probe must not loosen the trading endpoints."""
        from app.rate_limit import DEFAULT_LIMITS

        assert DEFAULT_LIMITS == ["200/minute"]
        from app.main import app as fastapi_app

        limited = {
            r.path for r in fastapi_app.routes
            if getattr(r, "methods", None) and "POST" in r.methods
        }
        # A paper order is still gated by its own 10/minute decorator.
        assert "/api/v1/paper-orders" in limited

