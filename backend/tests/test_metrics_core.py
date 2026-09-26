"""Tests for the canonical performance metrics in metrics_core.

These formulas were duplicated across six backtester modules, and the
versions disagreed. The tests below pin the single shared definition.
"""

import math
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.metrics_core import (
    annualize_return,
    build_metrics,
    calmar_ratio,
    max_drawdown,
    max_drawdown_from_prices,
    periods_per_year,
    sharpe_ratio,
    sortino_ratio,
)


class TestPeriodsPerYear:
    def test_known_intervals(self):
        assert periods_per_year("1h") == 8_760
        assert periods_per_year("1d") == 365
        assert periods_per_year("4h") == 2_190

    def test_unknown_defaults_to_hourly(self):
        assert periods_per_year("7s") == 8_760

    def test_all_intervals_are_ordered(self):
        order = ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"]
        values = [periods_per_year(i) for i in order]
        assert values == sorted(values, reverse=True)


class TestMaxDrawdown:
    def test_monotonic_increase_is_zero(self):
        assert max_drawdown([100, 101, 102, 103]) == 0.0

    def test_known_drawdown(self):
        # 100 -> 80 is a 20% decline.
        assert max_drawdown([100, 90, 80, 95]) == pytest.approx(-0.20)

    def test_peak_is_not_reset_by_new_highs(self):
        # 100 -> 50 -> 100 -> 50 must report -50%, not -0%.
        curve = [100, 50, 100, 50]
        assert max_drawdown(curve) == pytest.approx(-0.50)

    def test_too_short(self):
        assert max_drawdown([]) == 0.0
        assert max_drawdown([100]) == 0.0

    def test_from_prices(self):
        assert max_drawdown_from_prices([100, 80, 120]) == pytest.approx(-0.20)


class TestAnnualizeReturn:
    def test_one_year_is_identity(self):
        assert annualize_return(0.12, 8_760, 8_760) == pytest.approx(0.12)

    def test_six_months_roughly_squares(self):
        annual = annualize_return(0.06, 4_380, 8_760)
        assert annual == pytest.approx(0.1233, abs=1e-3)

    def test_not_absurd_over_a_short_backtest(self):
        """The old formula returned ~236% for +6% over 6 monthly periods."""
        annual = annualize_return(0.06, 6, 12)
        assert 0.10 < annual < 0.15

    def test_ruin_returns_minus_one(self):
        assert annualize_return(-1.0, 12, 12) == -1.0

    def test_zero_periods(self):
        assert annualize_return(0.10, 0, 12) == 0.0


class TestCalmar:
    def test_no_drawdown_is_undefined(self):
        assert calmar_ratio(0.5, 0.0, 12, 12) == 0.0

    def test_simple_case(self):
        # +12% over a year against a 6% drawdown -> 2.0
        assert calmar_ratio(0.12, -0.06, 12, 12) == pytest.approx(2.0, abs=0.01)

    def test_short_backtest_is_not_inflated(self):
        value = calmar_ratio(0.06, -0.06, 6, 12)
        assert 1.0 < value < 2.2

    def test_wipeout_returns_zero(self):
        assert calmar_ratio(-1.0, -0.9, 12, 12) == 0.0


class TestSortino:
    def test_too_few_returns(self):
        assert sortino_ratio([], 365) == 0.0
        assert sortino_ratio([0.01], 365) == 0.0

    def test_no_downside_is_zero_not_infinite(self):
        assert sortino_ratio([0.01, 0.02, 0.03], 365) == 0.0

    def test_single_loss_is_not_dropped(self):
        """A single losing period used to be discarded and return 0.0."""
        returns = [0.05, 0.05, 0.05, 0.05, -0.05]
        assert sortino_ratio(returns, 1) > 0

    def test_single_loss_wins_over_no_loss(self):
        with_loss = sortino_ratio([0.05, 0.05, 0.05, 0.05, -0.05], 1)
        without = sortino_ratio([0.05, 0.05, 0.05, 0.05], 1)
        assert without == 0.0  # no downside -> undefined, reported as 0
        assert with_loss > 0

    def test_uses_downside_deviation_not_loss_dispersion(self):
        # Same number of losses, much larger magnitude -> lower ratio.
        small = sortino_ratio([0.01, 0.01, 0.01, -0.01], 1)
        large = sortino_ratio([0.01, 0.01, 0.01, -0.10], 1)
        assert large < small

    def test_target_is_respected(self):
        returns = [0.03, 0.03, 0.00, 0.03]
        assert sortino_ratio(returns, 1, target=0.0) == 0.0
        assert sortino_ratio(returns, 1, target=0.01) > 0


class TestSharpe:
    def test_zero_volatility(self):
        assert sharpe_ratio([0.01, 0.01, 0.01], 365) == 0.0

    def test_annualizes_once(self):
        # A constant-drift series annualizes to about sqrt(365) * drift/stdev.
        returns = [0.001, 0.002, -0.001, 0.002, 0.001, 0.0]
        result = sharpe_ratio(returns, 365)
        expected = (sum(returns) / len(returns)) / _stdev(returns) * math.sqrt(365)
        assert result == pytest.approx(round(expected, 4), abs=1e-3)

    def test_risk_free_subtracted(self):
        returns = [0.01, 0.02, -0.01, 0.02]
        assert sharpe_ratio(returns, 1, risk_free=0.005) < sharpe_ratio(returns, 1)


def _stdev(values):
    from statistics import stdev
    return stdev(values)


class TestBuildMetrics:
    def test_consistent_block(self):
        equity = [1000, 1100, 1050, 1200]
        returns = [0.1, -0.045, 0.143]
        metrics = build_metrics(equity, returns, trades=3, wins=2, interval="1h", initial_capital=1000)
        assert metrics["final_equity"] == 1200
        assert metrics["total_return"] == pytest.approx(0.2)
        assert metrics["max_drawdown"] < 0
        assert metrics["max_drawdown_pct"] == pytest.approx(metrics["max_drawdown"] * 100, abs=0.01)
        assert 0 <= metrics["win_rate"] <= 1
        assert metrics["win_rate"] == pytest.approx(2 / 3, abs=1e-6)

    def test_zero_trades_has_zero_win_rate(self):
        metrics = build_metrics([1000], [], trades=0, wins=0, interval="1h", initial_capital=1000)
        assert metrics["win_rate"] == 0.0
        assert metrics["trade_count"] == 0


class TestUnifiedAcrossBacktesters:
    """Every backtester must now return the same number for the same input."""

    def test_all_modules_delegate_to_metrics_core(self):
        from app import backtesting, backtesting_smc, backtesting_advanced, indicators
        from app.metrics_core import max_drawdown as core_dd
        from app.metrics_core import sortino_ratio as core_sortino

        assert backtesting.sharpe_ratio is sharpe_ratio
        assert backtesting.sortino_ratio is core_sortino
        assert backtesting.sharpe_ratio is sharpe_ratio
        assert backtesting_smc.sharpe_ratio is sharpe_ratio
        assert backtesting_smc.sortino_ratio is core_sortino
        assert backtesting_smc.max_drawdown is core_dd
        assert backtesting_advanced._sharpe([0.01, 0.02], 365) == sharpe_ratio([0.01, 0.02], 365)
        assert indicators.sortino_ratio([0.01, -0.02], 365) == core_sortino([0.01, -0.02], 365)
        assert indicators.periods_per_year("4h") == periods_per_year("4h")
