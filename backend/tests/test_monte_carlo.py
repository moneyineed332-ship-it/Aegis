"""Tests for the Monte-Carlo resampler.

The simulation used to build synthetic trades from ``avg_trade_return``
(win = 1.2x avg, loss = -0.8x avg), which manufactured a positive edge out of
a breakeven strategy and annualized each trade return as if it were a period
return. These tests pin the resampling-of-real-trades behaviour.
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.backtesting_advanced import monte_carlo_simulation


def _breakeven(candles, params):
    """Wins and losses of equal size, 50% of the time. Real edge is zero."""
    return {
        "total_return": 0.0,
        "trade_count": 200,
        "win_rate": 0.5,
        "sharpe_ratio": 0.0,
        "avg_trade_return": 0.0,
        "trade_returns": [0.02] * 100 + [-0.02] * 100,
    }


def _edge(candles, params):
    return {
        "total_return": 0.4,
        "trade_count": 200,
        "win_rate": 0.55,
        "sharpe_ratio": 1.2,
        "avg_trade_return": 0.002,
        "trade_returns": [0.03] * 110 + [-0.02] * 90,
    }


def _losing(candles, params):
    return {
        "total_return": -0.5,
        "trade_count": 100,
        "win_rate": 0.3,
        "sharpe_ratio": -0.8,
        "avg_trade_return": -0.006,
        "trade_returns": [0.01] * 30 + [-0.02] * 70,
    }


def _no_series(candles, params):
    return {"total_return": 0.1, "trade_count": 10, "win_rate": 0.5, "avg_trade_return": 0.01}


def _no_trades(candles, params):
    return {"total_return": 0.0, "trade_count": 0, "win_rate": 0.0, "avg_trade_return": 0.0}


def _raises(candles, params):
    raise ValueError("not enough candles")


class TestNoManufacturedEdge:
    def test_breakeven_has_no_positive_expectation(self):
        result = monte_carlo_simulation([], _breakeven, {}, n_simulations=800, seed=42)
        assert result["return_distribution"]["mean"] < 0.05

    def test_breakeven_profit_probability_is_near_a_coin_flip(self):
        result = monte_carlo_simulation([], _breakeven, {}, n_simulations=800, seed=42)
        assert 0.3 < result["probability_of_profit"] < 0.7

    def test_breakeven_sharpe_is_not_inflated(self):
        result = monte_carlo_simulation([], _breakeven, {}, n_simulations=800, seed=42)
        assert abs(result["sharpe_distribution"]["mean"]) < 0.8

    def test_real_edge_is_preserved(self):
        result = monte_carlo_simulation([], _edge, {}, n_simulations=500, seed=42)
        assert result["return_distribution"]["mean"] > 0.3
        assert result["probability_of_profit"] > 0.9

    def test_losing_strategy_stays_losing(self):
        result = monte_carlo_simulation([], _losing, {}, n_simulations=500, seed=1)
        assert result["return_distribution"]["mean"] < 0
        assert result["probability_of_profit"] < 0.2
        assert result["probability_of_ruin"] > 0


class TestResamplingRealTrades:
    def test_reports_trades_per_simulation(self):
        result = monte_carlo_simulation([], _breakeven, {}, n_simulations=100, seed=3)
        assert result["trades_per_simulation"] == 200

    def test_win_rate_distribution_tracks_the_series(self):
        result = monte_carlo_simulation([], _edge, {}, n_simulations=400, seed=3)
        assert 0.45 < result["win_rate_distribution"]["mean"] < 0.65

    def test_drawdown_is_path_dependent_not_a_constant(self):
        result = monte_carlo_simulation([], _edge, {}, n_simulations=400, seed=3)
        percentiles = result["drawdown_distribution"]["percentiles"]
        assert percentiles["p5"] < percentiles["p95"], "drawdown distribution is degenerate"

    def test_rejects_strategy_without_trade_returns(self):
        result = monte_carlo_simulation([], _no_series, {}, n_simulations=10, seed=1)
        assert result["status"] == "no_trade_returns"
        assert "trade_returns" in result["error"]

    def test_reports_no_trades(self):
        result = monte_carlo_simulation([], _no_trades, {}, n_simulations=10, seed=1)
        assert result["status"] == "no_trades"

    def test_reports_backtest_failure(self):
        result = monte_carlo_simulation([], _raises, {}, n_simulations=10, seed=1)
        assert result["status"] == "backtest_failed"


class TestReproducibility:
    def test_same_seed_same_result(self):
        a = monte_carlo_simulation([], _edge, {}, n_simulations=200, seed=7)
        b = monte_carlo_simulation([], _edge, {}, n_simulations=200, seed=7)
        assert a["return_distribution"] == b["return_distribution"]
        assert a["drawdown_distribution"] == b["drawdown_distribution"]

    def test_different_seed_differs(self):
        a = monte_carlo_simulation([], _edge, {}, n_simulations=200, seed=1)
        b = monte_carlo_simulation([], _edge, {}, n_simulations=200, seed=2)
        assert a["return_distribution"] != b["return_distribution"]


class TestBacktestersPublishTradeReturns:
    """Every backtester must expose the series the resampler needs."""

    def test_sma_crossover(self):
        from app.backtesting import run_sma_crossover
        candles = _trend(120)
        metrics = run_sma_crossover(candles, {
            "fast_period": 5, "slow_period": 20, "initial_capital": 10000,
            "allocation": 0.5, "fee_bps": 10, "slippage_bps": 5, "atr_period": 14,
            "atr_trailing": 2.0,
        })
        assert isinstance(metrics.get("trade_returns"), list)

    def test_smc_ict(self):
        from app.backtesting import run_smc_ict
        candles = _trend(200)
        metrics = run_smc_ict(candles, {
            "initial_capital": 10000, "allocation": 0.5, "fee_bps": 10,
            "slippage_bps": 5, "interval": "1h", "min_score": 0,
            "atr_stop_multiplier": 2.0, "lookback": 40,
        })
        assert isinstance(metrics.get("trade_returns"), list)

    def test_grid(self):
        from app.grid import run_grid
        candles = _trend(150)
        metrics = run_grid(candles, {
            "grid_count": 5, "grid_spread_pct": 0.02, "initial_capital": 10000,
            "allocation": 0.5, "fee_bps": 10, "slippage_bps": 5, "interval": "1h",
            "atr_period": 14, "max_drawdown_stop": 0.2,
        })
        assert isinstance(metrics.get("trade_returns"), list)


def _trend(n: int = 150, base: float = 100.0) -> list[dict]:
    candles = []
    price = base
    for i in range(n):
        price *= 1.002
        candles.append({
            "symbol": "BTCUSDT", "interval": "1h",
            "open_time": i * 3_600_000, "close_time": (i + 1) * 3_600_000,
            "open": price * 0.999, "high": price * 1.004, "low": price * 0.996,
            "close": price, "volume": 1000,
        })
    return candles
