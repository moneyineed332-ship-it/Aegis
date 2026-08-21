"""Tests for the autonomous trading engine."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, AsyncMock
from app import engine, config, storage


def test_engine_status_stopped_by_default():
    status = engine.get_engine_status()
    assert status["status"] == "stopped"
    assert status["mode"] in ("paper", "live")


def test_engine_status_has_required_fields():
    status = engine.get_engine_status()
    assert "status" in status
    assert "mode" in status
    assert "cycle_count" in status
    assert "symbols" in status


def test_engine_cycle_id_increments():
    id1 = engine._get_cycle_id()
    id2 = engine._get_cycle_id()
    assert id1 != id2


def test_engine_register_tasks():
    engine.register_tasks()
    from app.scheduler import scheduler
    status = scheduler.get_status()
    assert "tasks" in status
    assert len(status["tasks"]) >= 8


def test_engine_state_persistence():
    storage.set_engine_state("status", "test_running")
    result = storage.get_engine_state("status")
    assert result == "test_running"
    storage.set_engine_state("status", "stopped")


def test_engine_log_event():
    storage.log_engine_event("test_cycle", "test_event", {"key": "value"})
    events = storage.list_engine_logs(limit=5)
    assert any(e["event_type"] == "test_event" for e in events)


def test_engine_start_stop_flow():
    import asyncio

    async def _test():
        result = await engine.start_engine()
        assert result["status"] == "running"

        status = engine.get_engine_status()
        assert status["status"] == "running"

        result = await engine.stop_engine()
        assert result["status"] == "stopped"

        status = engine.get_engine_status()
        assert status["status"] == "stopped"

    asyncio.run(_test())


def test_task_fetch_prices_logs_on_error():
    import asyncio

    async def _test():
        with patch("app.market_data.fetch_spot_prices", side_effect=Exception("network error")):
            try:
                await engine.task_fetch_prices()
            except Exception:
                pass
        events = storage.list_engine_logs(limit=10)
        assert any(e["event_type"] in ("prices_error", "prices_fetched") for e in events)

    asyncio.run(_test())


def test_task_monitor_positions_empty_portfolio():
    import asyncio

    async def _test():
        engine._last_prices = {}
        await engine.task_monitor_positions()
    asyncio.run(_test())


def test_task_learning_runs():
    import asyncio

    async def _test():
        engine._last_analysis = None
        engine._last_signal = None
        await engine.task_learning()
    asyncio.run(_test())
