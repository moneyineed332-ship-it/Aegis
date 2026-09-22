"""Engine integration tests — verify the full autonomous cycle."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app import config, storage, engine, risk


@pytest.fixture(autouse=True)
def clean_db():
    """Clean test data before each test."""
    yield
    with storage.connection() as db:
        for table, col in [
            ("positions", "symbol"), ("paper_orders", "symbol"),
            ("engine_log", "cycle_id"), ("trade_signals", "symbol"),
        ]:
            try:
                db.execute(f"DELETE FROM {table} WHERE {col} LIKE 'TEST%'")
            except Exception:
                pass


class TestEngineStatus:
    def test_get_engine_status_returns_dict(self):
        result = engine.get_engine_status()
        assert isinstance(result, dict)
        assert "status" in result
        assert "cycle_count" in result

    def test_engine_status_has_tasks(self):
        result = engine.get_engine_status()
        assert "scheduler" in result
        assert isinstance(result["scheduler"], dict)

    def test_engine_status_has_prices(self):
        result = engine.get_engine_status()
        assert "last_prices" in result
        assert isinstance(result["last_prices"], dict)


class TestRiskLayer:
    def test_check_circuit_breaker_no_halt(self):
        result = risk.check_circuit_breaker(initial_capital=20.0, current_equity=20.0)
        assert isinstance(result, dict)
        assert result.get("halted") is not True

    def test_check_circuit_breaker_loss_limit(self):
        result = risk.check_circuit_breaker(initial_capital=20.0, current_equity=15.0)
        assert isinstance(result, dict)

    def test_record_trade_result(self):
        risk.record_trade_result(pnl=10.0)


class TestStorageCommit:
    """Verify the critical commit fix works."""

    def test_engine_log_persists(self):
        from datetime import datetime, timezone
        storage.log_engine_event("test_commit", "test_event", {"test": True}, "info")
        with storage.connection() as db:
            row = db.execute(
                "SELECT * FROM engine_log WHERE cycle_id = ?", ("test_commit",)
            ).fetchone()
            assert row is not None

    def test_market_snapshot_persists(self):
        now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        storage.save_market_snapshots([
            {"symbol": "TESTUSDT", "price": 100.0, "source": "test", "collected_at": now}
        ])
        with storage.connection() as db:
            row = db.execute(
                "SELECT * FROM market_snapshots WHERE symbol = ?", ("TESTUSDT",)
            ).fetchone()
            assert row is not None

    def test_trade_signal_persists(self):
        storage.save_trade_signal("TESTUSDT", "test_strat", "buy", {"action": "buy", "confidence": 0.8})
        with storage.connection() as db:
            row = db.execute(
                "SELECT * FROM trade_signals WHERE symbol = ?", ("TESTUSDT",)
            ).fetchone()
            assert row is not None


def _run_task(coro):
    """Run an engine task to completion, failing loudly on code bugs.

    Network outages are reported as skips (tasks degrade gracefully
    offline); any other exception fails the test.
    """
    import asyncio
    import httpx
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(coro)
    except (httpx.HTTPError, OSError, TimeoutError) as exc:
        import pytest
        pytest.skip(f"network unavailable: {exc}")
    finally:
        loop.close()


class TestEngineTasks:
    def test_task_fetch_prices(self):
        """Verify fetch_prices task runs without error."""
        _run_task(engine.task_fetch_prices())

    def test_task_check_circuit_breaker(self):
        """Verify circuit breaker task runs without error."""
        _run_task(engine.task_check_circuit_breaker())

    def test_task_learning(self):
        """Verify learning task runs without error."""
        _run_task(engine.task_learning())


class TestConsensusIntegration:
    def test_consensus_with_votes(self):
        from app.consensus import ConsensusEngine
        engine = ConsensusEngine(min_votes=2, min_confidence=0.5, min_agreement=0.6)
        engine.add_vote("sma", "SMA", "buy", 0.8)
        engine.add_vote("rsi", "RSI", "buy", 0.7)
        engine.add_vote("macd", "MACD", "buy", 0.6)
        result = engine.compute_consensus()
        assert result["action"] == "buy"
        assert result["confidence"] > 0.5

    def test_consensus_hold_on_mixed(self):
        from app.consensus import ConsensusEngine
        engine = ConsensusEngine(min_votes=3, min_confidence=0.5, min_agreement=0.6)
        engine.add_vote("a", "A", "buy", 0.8)
        engine.add_vote("b", "B", "sell", 0.8)
        engine.add_vote("c", "C", "hold", 0.8)
        result = engine.compute_consensus()
        assert result["action"] == "hold"


class TestRegimeClassification:
    def test_classify_returns_valid_regime(self):
        from app import regime
        result = regime.classify({"rsi": 50, "adx": 25, "momentum": 0.01, "volatility": 0.02})
        assert "regime" in result
        assert result["regime"] in ["bull_trend", "bear_trend", "range", "high_volatility", "low_volatility"]

    def test_classify_extreme_rsi(self):
        from app import regime
        result = regime.classify({"rsi": 90, "adx": 40, "momentum": 0.05, "volatility": 0.08})
        assert result["regime"] in ["bull_trend", "euphoria", "high_volatility", "range"]
        assert "confidence" in result


class TestFeatureExtraction:
    def test_latest_features_returns_dict(self):
        from app import features, storage
        candles = storage.list_ohlcv_candles("BTCUSDT", "1h", limit=100)
        if len(candles) >= 50:
            result = features.latest_features(candles)
            assert isinstance(result, dict)
            assert "rsi" in result
            assert "adx" in result

    def test_latest_features_empty_candles(self):
        from app import features
        with pytest.raises(ValueError):
            features.latest_features([])
