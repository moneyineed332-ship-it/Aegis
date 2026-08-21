"""Tests for execution module — orders, trailing stops, position sizing."""

import pytest

from . import execution


@pytest.fixture(autouse=True)
def _clear_trailing_stops():
    """Clear trailing stops between tests."""
    execution._trailing_stops.clear()
    yield
    execution._trailing_stops.clear()


class TestMarketOrder:
    def test_buy_order(self):
        result = execution.market_order("BTCUSDT", "buy", 0.1, 50000)
        assert result["status"] == "filled"
        assert result["side"] == "buy"
        assert result["fill_price"] > 50000  # slippage for buy

    def test_sell_order(self):
        result = execution.market_order("BTCUSDT", "sell", 0.1, 50000)
        assert result["status"] == "filled"
        assert result["side"] == "sell"
        assert result["fill_price"] < 50000  # slippage for sell

    def test_fee_calculation(self):
        result = execution.market_order("BTCUSDT", "buy", 1.0, 50000, fee_bps=10)
        expected_fee = 50000 * 10 / 10_000
        assert result["fee"] == round(expected_fee, 4)

    def test_notional(self):
        result = execution.market_order("BTCUSDT", "buy", 0.5, 50000)
        assert result["notional"] == 25000.0


class TestLimitOrder:
    def test_buy_fills_when_favorable(self):
        result = execution.limit_order("BTCUSDT", "buy", 0.1, 50000, 49000)
        assert result["status"] == "filled"

    def test_buy_pending_when_unfavorable(self):
        result = execution.limit_order("BTCUSDT", "buy", 0.1, 50000, 51000)
        assert result["status"] == "pending"

    def test_sell_fills_when_favorable(self):
        result = execution.limit_order("BTCUSDT", "sell", 0.1, 50000, 51000)
        assert result["status"] == "filled"

    def test_sell_pending_when_unfavorable(self):
        result = execution.limit_order("BTCUSDT", "sell", 0.1, 50000, 49000)
        assert result["status"] == "pending"


class TestFractionedOrder:
    def test_basic(self):
        result = execution.fractioned_order("BTCUSDT", "buy", 1.0, 50000, chunks=3)
        assert result["chunks_filled"] == 3
        assert result["status"] == "filled"
        assert abs(result["total_filled"] - 1.0) < 1e-6

    def test_single_chunk(self):
        result = execution.fractioned_order("BTCUSDT", "buy", 0.5, 50000, chunks=1)
        assert result["chunks_filled"] == 1

    def test_fills_list(self):
        result = execution.fractioned_order("BTCUSDT", "buy", 1.0, 50000, chunks=3)
        assert len(result["fills"]) == 3


class TestEstimateSlippage:
    def test_small_order(self):
        result = execution.estimate_slippage(1000, 100000)
        assert result >= 0

    def test_large_order(self):
        result = execution.estimate_slippage(50000, 100000)
        assert result > 0

    def test_zero_depth(self):
        result = execution.estimate_slippage(1000, 0)
        assert result == 0.0


class TestTrailingStop:
    def test_create(self):
        result = execution.create_trailing_stop("BTCUSDT", "buy", 50000, 0.05)
        assert result["created"] is True
        assert result["symbol"] == "BTCUSDT"

    def test_update_long价格上涨(self):
        execution.create_trailing_stop("BTCUSDT", "buy", 50000, 0.05)
        result = execution.update_trailing_stop("BTCUSDT", "buy", 55000)
        assert result["stop_price"] > 47500  # trail from higher price

    def test_update_short价格下跌(self):
        execution.create_trailing_stop("BTCUSDT", "sell", 50000, 0.05)
        result = execution.update_trailing_stop("BTCUSDT", "sell", 45000)
        assert result["stop_price"] < 52500

    def test_trigger_long(self):
        execution.create_trailing_stop("BTCUSDT", "buy", 50000, 0.05)
        execution.update_trailing_stop("BTCUSDT", "buy", 55000)
        result = execution.update_trailing_stop("BTCUSDT", "buy", 47000)
        assert result["triggered"] is True

    def test_trigger_short(self):
        execution.create_trailing_stop("BTCUSDT", "sell", 50000, 0.05)
        execution.update_trailing_stop("BTCUSDT", "sell", 45000)
        result = execution.update_trailing_stop("BTCUSDT", "sell", 53000)
        assert result["triggered"] is True

    def test_remove(self):
        execution.create_trailing_stop("BTCUSDT", "buy", 50000)
        result = execution.remove_trailing_stop("BTCUSDT", "buy")
        assert result["removed"] is True

    def test_remove_nonexistent(self):
        result = execution.remove_trailing_stop("BTCUSDT", "buy")
        assert "error" in result

    def test_get_all(self):
        execution.create_trailing_stop("BTCUSDT", "buy", 50000)
        execution.create_trailing_stop("ETHUSDT", "sell", 3000)
        stops = execution.get_all_trailing_stops()
        assert len(stops) == 2

    def test_check_triggers(self):
        execution.create_trailing_stop("BTCUSDT", "buy", 50000, 0.05)
        execution.update_trailing_stop("BTCUSDT", "buy", 55000)
        triggered = execution.check_trailing_stops({"BTCUSDT": 47000})
        assert len(triggered) == 1
        assert triggered[0]["triggered"] is True


class TestPositionSizing:
    def test_basic(self):
        result = execution.calculate_position_size(10000, 0.02, 50000, 49000)
        assert result["quantity"] > 0
        assert result["position_value"] > 0
        assert result["risk_amount"] == 200.0

    def test_no_stop_loss(self):
        result = execution.calculate_position_size(10000, 0.02, 50000)
        assert result["quantity"] > 0
        assert result["position_value"] <= 2500

    def test_invalid_entry_price(self):
        result = execution.calculate_position_size(10000, 0.02, 0)
        assert result["error"] == "Invalid entry price"

    def test_max_position_cap(self):
        result = execution.calculate_position_size(10000, 0.02, 50000, 49000, max_position_pct=0.25)
        assert result["position_value"] <= 2500

    def test_risk_based_sizing(self):
        result = execution.calculate_position_size(10000, 0.02, 50000, 45000)
        # risk = 200, risk_per_unit = 5000, qty = 200/5000 = 0.04
        assert result["quantity"] == 0.04
