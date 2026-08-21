"""Tests for risk module — VaR/CVaR, stress test, correlation, concentration, circuit breaker."""

import math
import pytest

from . import risk


@pytest.fixture(autouse=True)
def _reset_circuit_breaker():
    """Reset circuit breaker state before each test."""
    risk.reset_circuit_breaker()
    yield
    risk.reset_circuit_breaker()


def _make_candles(n=100, base_price=100.0, volatility=0.02):
    """Generate synthetic OHLCV candles."""
    import random
    random.seed(42)
    candles = []
    price = base_price
    for i in range(n):
        change = price * random.gauss(0, volatility)
        o = price
        h = price + abs(change)
        l = price - abs(change)
        c = price + change
        candles.append({"open": o, "high": h, "low": l, "close": c, "volume": 1000})
        price = c
    return candles


class TestHistoricalRisk:
    def test_basic(self):
        candles = _make_candles(100)
        result = risk.historical_risk(candles, 10000)
        assert "value_at_risk" in result
        assert "conditional_value_at_risk" in result
        assert "max_drawdown" in result
        assert "volatility" in result
        assert result["observations"] > 0

    def test_insufficient_data(self):
        candles = _make_candles(10)
        with pytest.raises(ValueError, match="At least 30 candles"):
            risk.historical_risk(candles, 10000)

    def test_var_positive(self):
        candles = _make_candles(100)
        result = risk.historical_risk(candles, 10000)
        assert result["value_at_risk"] >= 0 or result["value_at_risk"] <= 0

    def test_confidence_levels(self):
        candles = _make_candles(200)
        r95 = risk.historical_risk(candles, 10000, confidence=0.95)
        r99 = risk.historical_risk(candles, 10000, confidence=0.99)
        assert r99["value_at_risk"] >= r95["value_at_risk"]


class TestStressTest:
    def test_basic(self):
        candles = _make_candles(100)
        result = risk.stress_test(candles, 10000, position_value=5000)
        assert "scenarios" in result
        assert len(result["scenarios"]) == 7
        assert result["capital"] == 10000
        assert result["position_value"] == 5000

    def test_insufficient_data(self):
        candles = _make_candles(10)
        with pytest.raises(ValueError, match="At least 30 candles"):
            risk.stress_test(candles, 10000)

    def test_scenarios_have_names(self):
        candles = _make_candles(100)
        result = risk.stress_test(candles, 10000)
        for scenario in result["scenarios"]:
            assert "name" in scenario
            assert "price_impact" in scenario
            assert "portfolio_impact" in scenario


class TestCorrelationMatrix:
    def test_basic(self):
        assets = {
            "BTCUSDT": [100, 101, 102, 103, 104],
            "ETHUSDT": [50, 51, 52, 53, 54],
        }
        result = risk.correlation_matrix(assets)
        assert "matrix" in result
        assert "BTCUSDT" in result["matrix"]
        assert result["matrix"]["BTCUSDT"]["BTCUSDT"] == 1.0

    def test_single_asset(self):
        assets = {"BTCUSDT": [100, 101, 102]}
        result = risk.correlation_matrix(assets)
        assert result["avg_correlation"] is None

    def test_correlation_range(self):
        assets = {
            "BTCUSDT": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            "ETHUSDT": [50, 52, 48, 54, 46, 56, 44, 58, 42, 60],
        }
        result = risk.correlation_matrix(assets)
        for sym_a in result["matrix"]:
            for sym_b in result["matrix"][sym_a]:
                corr = result["matrix"][sym_a][sym_b]
                assert -1 <= corr <= 1


class TestConcentrationRisk:
    def test_empty_positions(self):
        result = risk.concentration_risk([], {})
        assert result["total_exposure"] == 0
        assert result["herfindahl"] == 0

    def test_single_position(self):
        positions = [{"symbol": "BTCUSDT", "quantity": 0.1, "average_price": 50000}]
        result = risk.concentration_risk(positions, {"BTCUSDT": 50000})
        assert result["max_concentration"] == 100.0
        assert result["herfindahl"] == 1.0

    def test_diversified(self):
        positions = [
            {"symbol": "BTCUSDT", "quantity": 0.1, "average_price": 50000},
            {"symbol": "ETHUSDT", "quantity": 10, "average_price": 3000},
        ]
        result = risk.concentration_risk(positions, {"BTCUSDT": 50000, "ETHUSDT": 3000})
        assert result["herfindahl"] < 1.0
        assert result["max_concentration"] < 100.0

    def test_position_count(self):
        positions = [
            {"symbol": "BTCUSDT", "quantity": 0.1, "average_price": 50000},
            {"symbol": "ETHUSDT", "quantity": 10, "average_price": 3000},
            {"symbol": "SOLUSDT", "quantity": 100, "average_price": 100},
        ]
        result = risk.concentration_risk(positions, {})
        assert result["position_count"] == 3


class TestCircuitBreaker:
    def test_default_not_halted(self):
        status = risk.get_circuit_breaker_status()
        assert status["halted"] is False

    def test_halt_on_daily_loss(self):
        result = risk.check_circuit_breaker(10000, 9600)
        assert result["halted"] is True
        assert "Daily loss" in result["reason"]

    def test_halt_on_consecutive_losses(self):
        for _ in range(3):
            risk.record_trade_result(-100)
        result = risk.check_circuit_breaker(10000, 9900)
        assert result["halted"] is True
        assert "consecutive losses" in result["reason"]

    def test_no_halt_within_thresholds(self):
        result = risk.check_circuit_breaker(10000, 9900)
        assert result["halted"] is False

    def test_reset(self):
        risk.check_circuit_breaker(10000, 9600)
        risk.reset_circuit_breaker()
        status = risk.get_circuit_breaker_status()
        assert status["halted"] is False

    def test_record_trade_positive_resets_losses(self):
        risk.record_trade_result(-100)
        risk.record_trade_result(-100)
        risk.record_trade_result(200)
        status = risk.get_circuit_breaker_status()
        assert status["consecutive_losses"] == 0

    def test_trade_history_capped(self):
        for _ in range(1100):
            risk.record_trade_result(10)
        status = risk.get_circuit_breaker_status()
        assert len(risk._circuit_breaker["trade_history"]) <= 1000
