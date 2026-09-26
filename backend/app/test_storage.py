"""Tests for storage module — SQLite persistence layer."""

import json
import os
import tempfile
from datetime import datetime, timezone

import pytest

from . import config, storage


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Use a temporary database for each test."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("app.config.DB_PATH", db_path)
    monkeypatch.setattr(storage, "DATABASE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(storage, "_db_connection", None)
    monkeypatch.setattr(storage, "_initialized", False)
    storage.initialize()
    yield
    if storage._db_connection:
        storage._db_connection.close()
        storage._db_connection = None


class TestPositions:
    def test_list_positions_empty(self):
        assert storage.list_positions() == []

    def test_save_order_and_position(self):
        order = {"symbol": "BTCUSDT", "side": "buy", "quantity": 0.1, "reference_price": 50000, "notional": 5000}
        position = {"symbol": "BTCUSDT", "quantity": 0.1, "average_price": 50000}
        result = storage.save_order_and_position(order, position)
        assert result["status"] == "filled_simulated"
        assert result["symbol"] == "BTCUSDT"

    def test_list_positions_after_save(self):
        order = {"symbol": "BTCUSDT", "side": "buy", "quantity": 0.1, "reference_price": 50000, "notional": 5000}
        position = {"symbol": "BTCUSDT", "quantity": 0.1, "average_price": 50000}
        storage.save_order_and_position(order, position)
        positions = storage.list_positions()
        assert len(positions) == 1
        assert positions[0]["symbol"] == "BTCUSDT"

    def test_save_order_deletes_position_when_none(self):
        order = {"symbol": "BTCUSDT", "side": "buy", "quantity": 0.1, "reference_price": 50000, "notional": 5000}
        position = {"symbol": "BTCUSDT", "quantity": 0.1, "average_price": 50000}
        storage.save_order_and_position(order, position)
        storage.save_order_and_position(order, None)
        assert storage.list_positions() == []


class TestOrders:
    def test_list_recent_orders_empty(self):
        assert storage.list_recent_orders() == []

    def test_list_recent_orders_limit(self):
        order = {"symbol": "BTCUSDT", "side": "buy", "quantity": 0.1, "reference_price": 50000, "notional": 5000}
        for _ in range(5):
            storage.save_order_and_position(order, None)
        assert len(storage.list_recent_orders(3)) == 3


class TestMarketSnapshots:
    def test_save_and_list(self):
        snapshots = [
            {"symbol": "BTCUSDT", "price": 50000, "source": "test", "collected_at": "2025-01-01T00:00:00"},
            {"symbol": "ETHUSDT", "price": 3000, "source": "test", "collected_at": "2025-01-01T00:00:00"},
        ]
        storage.save_market_snapshots(snapshots)
        result = storage.list_market_snapshots()
        assert len(result) == 2

    def test_list_market_snapshots_limit(self):
        snapshots = [{"symbol": "BTCUSDT", "price": 50000, "source": "test", "collected_at": "2025-01-01T00:00:00"}]
        storage.save_market_snapshots(snapshots)
        assert len(storage.list_market_snapshots(1)) == 1


class TestOHLCV:
    def test_save_and_list(self):
        candles = [
            {"symbol": "BTCUSDT", "interval": "1h", "open_time": 1000, "close_time": 1001,
             "open": 100, "high": 110, "low": 90, "close": 105, "volume": 1000, "source": "test"},
        ]
        storage.save_ohlcv_candles(candles)
        result = storage.list_ohlcv_candles("BTCUSDT", "1h", 10)
        assert len(result) == 1
        assert result[0]["close"] == 105

    def test_upsert_on_conflict(self):
        candles = [
            {"symbol": "BTCUSDT", "interval": "1h", "open_time": 1000, "close_time": 1001,
             "open": 100, "high": 110, "low": 90, "close": 105, "volume": 1000, "source": "test"},
        ]
        storage.save_ohlcv_candles(candles)
        candles[0]["close"] = 200
        storage.save_ohlcv_candles(candles)
        result = storage.list_ohlcv_candles("BTCUSDT", "1h", 10)
        assert len(result) == 1
        assert result[0]["close"] == 200

    def test_list_ohlcv_returns_ascending_order(self):
        candles = [
            {"symbol": "BTCUSDT", "interval": "1h", "open_time": 3000, "close_time": 3001,
             "open": 100, "high": 110, "low": 90, "close": 105, "volume": 1000, "source": "test"},
            {"symbol": "BTCUSDT", "interval": "1h", "open_time": 1000, "close_time": 1001,
             "open": 100, "high": 110, "low": 90, "close": 105, "volume": 1000, "source": "test"},
        ]
        storage.save_ohlcv_candles(candles)
        result = storage.list_ohlcv_candles("BTCUSDT", "1h", 10)
        assert result[0]["open_time"] < result[1]["open_time"]


class TestBacktests:
    def test_save_and_list(self):
        result = storage.save_backtest("sma_crossover", "BTCUSDT", "1h", {"fast": 10}, {"sharpe": 1.5})
        assert result["strategy"] == "sma_crossover"
        backtests = storage.list_recent_backtests()
        assert len(backtests) == 1
        assert backtests[0]["parameters"] == {"fast": 10}


class TestDecisions:
    def test_save_and_list(self):
        result = storage.save_decision("BTCUSDT", "1h", {"action": "buy"})
        assert result["symbol"] == "BTCUSDT"
        decisions = storage.list_recent_decisions()
        assert len(decisions) == 1
        assert decisions[0]["decision"] == {"action": "buy"}


class TestKillSwitch:
    def test_default_off(self):
        assert storage.get_kill_switch() is False

    def test_set_on(self):
        storage.set_kill_switch(True, "Emergency stop test")
        assert storage.get_kill_switch() is True

    def test_set_off(self):
        storage.set_kill_switch(True, "test")
        storage.set_kill_switch(False, "Resume")
        assert storage.get_kill_switch() is False

    def test_missing_row_fails_closed(self):
        """An unknown switch state must halt trading, never re-enable it."""
        with storage.connection() as database:
            database.execute("DELETE FROM system_controls WHERE name = 'kill_switch'")
        assert storage.get_kill_switch() is True

    def test_read_error_fails_closed(self, monkeypatch):
        def boom():
            raise RuntimeError("database locked")

        monkeypatch.setattr(storage, "connection", boom)
        assert storage.get_kill_switch() is True


class TestCleanupStalePositions:
    def _insert(self, symbol, price):
        with storage.connection() as database:
            database.execute(
                "INSERT INTO positions (symbol, quantity, average_price) VALUES (?, ?, ?)",
                (symbol, 1.0, price),
            )

    def test_keeps_forex_position_below_one(self):
        """EURUSD trades near 1.08 — a low price is not corruption."""
        self._insert("EURUSD", 1.0850)
        assert storage.cleanup_stale_positions() == 0
        assert [p["symbol"] for p in storage.list_positions()] == ["EURUSD"]

    def test_keeps_microcap_position(self):
        self._insert("SHIBUSDT", 0.00001234)
        assert storage.cleanup_stale_positions() == 0
        assert len(storage.list_positions()) == 1

    def test_removes_zero_price(self):
        self._insert("BTCUSDT", 0.0)
        assert storage.cleanup_stale_positions() == 1
        assert storage.list_positions() == []

    def test_keeps_implausible_price_but_logs(self):
        """A BTC quoted at 75 is suspicious, not grounds for silent deletion."""
        self._insert("BTCUSDT", 75.0)
        assert storage.cleanup_stale_positions() == 0
        assert [p["symbol"] for p in storage.list_positions()] == ["BTCUSDT"]

    def test_removes_non_normalized_symbol(self):
        self._insert("BTC/USDT", 50000.0)
        assert storage.cleanup_stale_positions() == 1
        assert storage.list_positions() == []


class TestEquityCurve:
    def test_empty_orders(self):
        curve = storage.compute_equity_curve(10000, [], [])
        assert len(curve) == 1
        assert curve[0]["equity"] == 10000

    def test_with_orders(self):
        orders = [
            {"id": 1, "symbol": "BTCUSDT", "side": "buy", "quantity": 0.01, "notional": 500, "fill_price": 50000, "created_at": "2025-01-01"},
            {"id": 2, "symbol": "BTCUSDT", "side": "sell", "quantity": 0.01, "notional": 600, "fill_price": 60000, "created_at": "2025-01-02"},
        ]
        curve = storage.compute_equity_curve(10000, [], orders)
        assert len(curve) >= 2

    def test_closed_trade_books_real_pnl_not_notional(self):
        """A round trip must book the actual gain, not the traded notional."""
        orders = [
            {"id": 1, "symbol": "BTCUSDT", "side": "buy", "quantity": 0.01, "notional": 500, "fill_price": 50000, "created_at": "2025-01-01"},
            {"id": 2, "symbol": "BTCUSDT", "side": "sell", "quantity": 0.01, "notional": 600, "fill_price": 60000, "created_at": "2025-01-02"},
        ]
        curve = storage.compute_equity_curve(10000, [], orders)
        # (60000 - 50000) * 0.01 = +100
        assert curve[-1]["equity"] == pytest.approx(10100, abs=0.01)

    def test_losing_trade_reduces_equity(self):
        orders = [
            {"id": 1, "symbol": "BTCUSDT", "side": "buy", "quantity": 0.01, "notional": 500, "fill_price": 50000, "created_at": "2025-01-01"},
            {"id": 2, "symbol": "BTCUSDT", "side": "sell", "quantity": 0.01, "notional": 400, "fill_price": 40000, "created_at": "2025-01-02"},
        ]
        curve = storage.compute_equity_curve(10000, [], orders)
        assert curve[-1]["equity"] == pytest.approx(9900, abs=0.01)

    def test_fees_are_charged(self):
        base = [
            {"id": 1, "symbol": "BTCUSDT", "side": "buy", "quantity": 0.01, "notional": 500, "fill_price": 50000, "created_at": "2025-01-01"},
        ]
        with_fee = [{**base[0], "fee": 2.5}]
        curve = storage.compute_equity_curve(10000, [], base)
        curve_fee = storage.compute_equity_curve(10000, [], with_fee)
        assert curve[-1]["equity"] - curve_fee[-1]["equity"] == pytest.approx(2.5, abs=0.01)

    def test_open_position_marked_to_market(self):
        orders = [
            {"id": 1, "symbol": "BTCUSDT", "side": "buy", "quantity": 0.01, "notional": 500, "fill_price": 50000, "created_at": "2025-01-01"},
        ]
        curve = storage.compute_equity_curve(10000, [], orders, {"BTCUSDT": 55000})
        # (55000 - 50000) * 0.01 = +50 on the final, live-marked point
        assert curve[-1]["equity"] == pytest.approx(10050, abs=0.01)

    def test_historical_points_use_their_own_price(self):
        """A current mark must not retroactively rewrite past points."""
        orders = [
            {"id": 1, "symbol": "BTCUSDT", "side": "buy", "quantity": 0.02, "notional": 1000, "fill_price": 50000, "created_at": "2025-01-01"},
        ]
        curve = storage.compute_equity_curve(10000, [], orders, {"BTCUSDT": 60000})
        assert curve[1]["equity"] == 10000
        assert curve[-1]["equity"] == pytest.approx(10200, abs=0.01)

    def test_partial_close_keeps_basis(self):
        orders = [
            {"id": 1, "symbol": "BTCUSDT", "side": "buy", "quantity": 0.02, "notional": 1000, "fill_price": 50000, "created_at": "2025-01-01"},
            {"id": 2, "symbol": "BTCUSDT", "side": "sell", "quantity": 0.01, "notional": 600, "fill_price": 60000, "created_at": "2025-01-02"},
        ]
        curve = storage.compute_equity_curve(10000, [], orders, {"BTCUSDT": 60000})
        # realized (60000-50000)*0.01 = +100, remaining 0.01 @ basis 50000 marked 60000 = +100
        assert curve[-1]["equity"] == pytest.approx(10200, abs=0.01)

    def test_order_without_price_is_skipped(self):
        orders = [
            {"id": 1, "symbol": "BTCUSDT", "side": "buy", "quantity": 0.01, "notional": 500, "created_at": "2025-01-01"},
        ]
        curve = storage.compute_equity_curve(10000, [], orders)
        assert curve[-1]["equity"] == 10000


class TestFearGreed:
    def test_save_and_list(self):
        data = {"value": 25, "classification": "Fear", "source": "test", "collected_at": "2025-01-01"}
        storage.save_fear_greed(data)
        result = storage.list_fear_greed()
        assert len(result) == 1
        assert result[0]["value"] == 25


class TestFundingRates:
    def test_save_and_list(self):
        data = {"symbol": "BTCUSDT", "mark_price": 50000, "index_price": 49990,
                "funding_rate": 0.0001, "next_funding_time": 1000, "source": "test", "collected_at": "2025-01-01"}
        storage.save_funding_rate(data)
        result = storage.list_funding_rates("BTCUSDT")
        assert len(result) == 1

    def test_list_all(self):
        data = {"symbol": "BTCUSDT", "mark_price": 50000, "index_price": 49990,
                "funding_rate": 0.0001, "next_funding_time": 1000, "source": "test", "collected_at": "2025-01-01"}
        storage.save_funding_rate(data)
        assert len(storage.list_funding_rates()) == 1


class TestOpenInterest:
    def test_save_and_list(self):
        data = {"symbol": "BTCUSDT", "open_interest": 1000, "open_interest_usd": 50000000,
                "price": 50000, "source": "test", "collected_at": "2025-01-01"}
        storage.save_open_interest(data)
        result = storage.list_open_interest("BTCUSDT")
        assert len(result) == 1


class TestMemoryEpisodes:
    def test_save_and_list(self):
        result = storage.save_memory_episode("BTCUSDT", "sma", {"rsi": 50}, {"pnl": 0.05}, "fp123")
        assert result["fingerprint"] == "fp123"
        episodes = storage.list_memory_episodes()
        assert len(episodes) == 1

    def test_list_by_symbol(self):
        storage.save_memory_episode("BTCUSDT", "sma", {"rsi": 50}, None, "fp1")
        storage.save_memory_episode("ETHUSDT", "sma", {"rsi": 50}, None, "fp2")
        assert len(storage.list_memory_episodes("BTCUSDT")) == 1
