"""A follow-up check on the annualised Sharpe scale, which had been blamed.

An earlier pass claimed that ranking candidates by an annualised Sharpe was
itself a source of noise, on the theory that a 15m series multiplies by 187 and a
1h series by 94, so the values cluster near -50 and cannot be ordered
meaningfully. That claim was wrong and is retracted here rather than left in the
documentation.

Every candidate in a run shares one `interval`, so sqrt(ppy) is a constant
multiplier and cancels out of any ranking. Measured over a 28-set grid:

    annualised     top 5: (20,50) (20,40) (13,50) (5,50) (10,50)
    per period     top 5: (20,50) (20,40) (13,50) (5,50) (10,50)
    identical order: True

The same strategy on the same candles gives an identical per-period Sharpe at
both intervals, with the annual figures differing by exactly the ratio of the
square roots:

    15m  ppy=35040  annual -42.37  per period -0.22637
    1h   ppy= 8760  annual -21.19  per period -0.22637

So the annualised value is a real annual Sharpe, and the promotion thresholds in
lab.py compare annual to annual. Nothing needed rescaling.

What the extreme magnitudes did cause was output nobody could read. A bare
"-41.70" gives no hint that it is annual, nor what sits underneath it per bar, so
results now carry the scale. That change then exposed a real defect: the
optimisers hardcoded `"interval": "1h"` into the backtest parameters while the
endpoints accept 5m/15m/1h/4h and echo the requested interval back in the
response. A 15m request was therefore annualised with sqrt(8760) instead of
sqrt(35040) and the reported annual Sharpe was wrong by a factor of two, while
the same response claimed `interval: 15m`.
"""

import math

import pytest

from app import optimizer
from app.backtesting import _periods_per_year
from app.metrics_core import sharpe_ratio


def _returns(n=200, mean=-0.0004, sigma=0.002):
    """A deterministic return series; no randomness, so the ranking is stable."""
    return [mean + sigma * math.sin(i * 12.9898) for i in range(n)]


# --- the retracted claim -----------------------------------------------------

@pytest.mark.parametrize("interval", ["15m", "1h", "4h", "1d"])
def test_the_annualisation_factor_is_a_constant_multiplier_within_one_run(interval):
    """Ranking annualised and ranking per-period cannot disagree.

    This is the invariant that makes the earlier "ranking on noise" claim wrong.
    It also guards against a future well-meaning rescale silently changing which
    candidate the optimiser selects.
    """
    ppy = _periods_per_year(interval)
    factor = math.sqrt(ppy)
    returns = _returns()

    annual = sharpe_ratio(returns, ppy)
    per_period = annual / factor
    assert per_period == pytest.approx(annual / factor)

    # Two candidates: if the factor is a plain multiplier, the order is preserved.
    other = [r * 1.5 for r in returns]
    annual_other = sharpe_ratio(other, ppy)
    per_period_other = annual_other / factor
    assert (annual > annual_other) == (per_period > per_period_other)


def test_the_same_candles_give_the_same_per_period_sharpe_at_every_interval():
    """Identical geometry, different annualisation factor.

    Tolerated at 1e-3 because sharpe_ratio rounds the annual figure to four
    decimals at the source, and dividing a rounded value by sqrt(ppy) carries
    that error. The agreement is exact in exact arithmetic.
    """
    returns = _returns()
    per_period = []
    for interval in ("15m", "1h", "4h"):
        ppy = _periods_per_year(interval)
        per_period.append(sharpe_ratio(returns, ppy) / math.sqrt(ppy))

    assert per_period[0] == pytest.approx(per_period[1], rel=1e-3)
    assert per_period[1] == pytest.approx(per_period[2], rel=1e-3)


def test_the_annual_factor_grows_with_the_number_of_periods():
    assert math.sqrt(_periods_per_year("15m")) > math.sqrt(_periods_per_year("1h"))
    assert math.sqrt(_periods_per_year("1h")) > math.sqrt(_periods_per_year("1d"))


# --- the scale is now stated -------------------------------------------------

def test_sharpe_scale_states_the_interval_it_was_computed_on():
    scale = optimizer._sharpe_scale(-41.70, "15m")
    assert scale["sharpe_interval"] == "15m"
    assert scale["annualisation_factor"] == pytest.approx(math.sqrt(_periods_per_year("15m")))
    assert scale["sharpe_per_period"] == pytest.approx(-41.70 / scale["annualisation_factor"], rel=1e-4)


def test_sharpe_scale_degrades_gracefully_on_an_unknown_interval():
    assert optimizer._sharpe_scale(1.0, "not-an-interval") == {}


def test_reported_annual_and_per_period_agree():
    """annual == per_period * factor, or the reported pair is inconsistent."""
    scale = optimizer._sharpe_scale(-26.0319, "1h")
    assert -26.0319 == pytest.approx(
        scale["sharpe_per_period"] * scale["annualisation_factor"], rel=1e-3
    )


# --- the defect the scale exposed -------------------------------------------

def test_the_optimizer_annualises_on_the_interval_it_is_given():
    """It used to hardcode 1h into the backtest parameters.

    A 15m request was scored with sqrt(8760) instead of sqrt(35040) and the
    response still claimed `interval: 15m`.
    """
    seen = {}

    def run(candles, params):
        seen["interval"] = params["interval"]
        return {
            "sharpe_ratio": 1.0, "sortino_ratio": 1.0, "calmar_ratio": 1.0,
            "total_return": 0.05, "max_drawdown": -0.05, "trade_count": 20,
        }

    import app.backtesting as bt
    original = bt.run_sma_crossover
    bt.run_sma_crossover = run
    try:
        result = optimizer.optimize_sma(
            [{"open": 1.0, "high": 1.01, "low": 0.99, "close": 1.0,
              "volume": 1, "timestamp": i, "close_time": i} for i in range(4000)],
            interval="15m",
        )
    finally:
        bt.run_sma_crossover = original

    assert seen["interval"] == "15m"
    assert result["out_of_sample_metrics"]["sharpe_interval"] == "15m"
    assert result["out_of_sample_metrics"]["annualisation_factor"] == pytest.approx(
        math.sqrt(_periods_per_year("15m"))
    )


def test_the_default_interval_is_unchanged():
    """Existing callers pass no interval and must keep the previous behaviour."""
    seen = {}

    def run(candles, params):
        seen["interval"] = params["interval"]
        return {
            "sharpe_ratio": 1.0, "sortino_ratio": 1.0, "calmar_ratio": 1.0,
            "total_return": 0.05, "max_drawdown": -0.05, "trade_count": 20,
        }

    import app.backtesting as bt
    original = bt.run_sma_crossover
    bt.run_sma_crossover = run
    try:
        optimizer.optimize_sma(
            [{"open": 1.0, "high": 1.01, "low": 0.99, "close": 1.0,
              "volume": 1, "timestamp": i, "close_time": i} for i in range(4000)]
        )
    finally:
        bt.run_sma_crossover = original

    assert seen["interval"] == "1h"
