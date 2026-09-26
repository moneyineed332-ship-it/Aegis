"""Canonical performance metrics shared by every backtester.

These formulas used to be copy-pasted across six modules with slightly
different definitions, which made the same strategy report different Sharpe
ratios depending on which file produced the numbers. There is now one
implementation, one annualization table, and one set of edge-case rules.

Conventions
-----------
* ``returns`` are simple per-period returns (0.01 = +1%).
* ``max_drawdown`` is a NEGATIVE fraction (-0.2 = -20%), or 0.0 when the
  equity curve never fell below its starting point.
* ``ppy`` is the number of periods in a year for the candle interval.
"""

import math
from statistics import fmean, stdev

# Annualization factors, keyed by candle interval.
PERIODS_PER_YEAR = {
    "1m": 525_600,
    "3m": 175_200,
    "5m": 105_120,
    "15m": 35_040,
    "30m": 17_520,
    "1h": 8_760,
    "2h": 4_380,
    "4h": 2_190,
    "1d": 365,
}

DEFAULT_PPY = 8_760


def periods_per_year(interval: str) -> int:
    """Annualization factor for a candle interval, defaulting to hourly."""
    return PERIODS_PER_YEAR.get(interval, DEFAULT_PPY)


def max_drawdown(equity_curve: list[float]) -> float:
    """Largest peak-to-trough decline, as a negative fraction.

    The previous copies divided by the running peak, which reset the peak
    whenever a new high was printed and understated long drawdowns.
    """
    if len(equity_curve) < 2:
        return 0.0
    peak = equity_curve[0]
    worst = 0.0
    for value in equity_curve:
        if value > peak:
            peak = value
        if peak > 0:
            drawdown = value / peak - 1
            if drawdown < worst:
                worst = drawdown
    return worst


def max_drawdown_from_prices(prices: list[float]) -> float:
    """Max drawdown straight from a price series (no equity curve needed)."""
    return max_drawdown(list(prices))


def annualize_return(total_return: float, periods: int, ppy: int) -> float:
    """Geometrically annualize a cumulative return.

    Uses the geometric mean, which is the standard definition. A plain
    ``(1 + r) ** (ppy / periods)`` blows up on any backtest shorter than a
    year: +6% over 6 monthly periods became +236% instead of +12%.
    Returns -1.0 when the equity was wiped out, where the annualization is
    undefined.
    """
    if periods <= 0:
        return 0.0
    growth = 1.0 + total_return
    if growth <= 0:
        return -1.0
    years = periods / ppy if ppy > 0 else 0.0
    if years <= 0:
        return 0.0
    return growth ** (1.0 / years) - 1.0


def sharpe_ratio(returns: list[float], ppy: int, risk_free: float = 0.0) -> float:
    """Annualized Sharpe ratio.

    Computed on the per-period series and annualized once, by sqrt(ppy). The
    old Monte-Carlo variant annualized each single trade return, which
    inflated the result by roughly sqrt(365).
    """
    if len(returns) < 2:
        return 0.0
    volatility = stdev(returns)
    if volatility == 0:
        return 0.0
    excess = fmean(returns) - risk_free
    return round(excess / volatility * math.sqrt(ppy), 4)


def sortino_ratio(returns: list[float], ppy: int, target: float = 0.0) -> float:
    """Annualized Sortino ratio.

    Uses downside deviation measured against ``target``:
    ``sqrt(mean(min(r - target, 0) ** 2))``. The previous version took the
    standard deviation of the negative returns only, which measures how
    spread out the losses are rather than how large they are, and returned
    0.0 whenever there were fewer than two losing periods.
    """
    if len(returns) < 2:
        return 0.0
    downside_sq = [min(r - target, 0.0) ** 2 for r in returns]
    downside_dev = math.sqrt(fmean(downside_sq))
    if downside_dev == 0:
        # No downside at all: an unbounded ratio is reported as 0 rather than inf.
        return 0.0
    excess = fmean(returns) - target
    return round(excess / downside_dev * math.sqrt(ppy), 4)


def calmar_ratio(total_return: float, max_dd: float, periods: int, ppy: int) -> float:
    """Annualized return divided by the absolute max drawdown.

    ``max_dd`` is a negative fraction. Returns 0.0 when there is no drawdown
    to divide by, which is the only case where the ratio is undefined.
    """
    if max_dd >= 0 or periods <= 0:
        return 0.0
    annual = annualize_return(total_return, periods, ppy)
    if annual <= -1.0:
        return 0.0
    return round(annual / abs(max_dd), 4)


def signed_trade_returns(completed: list[tuple[dict, dict]]) -> list[float]:
    """Per-trade returns from (entry, exit) pairs, longs and shorts.

    The result is what a Monte-Carlo resample must draw from. Deriving trades
    from ``avg_trade_return`` instead cannot work: it forces a positive edge
    (win = 1.2x avg, loss = -0.8x avg), so a breakeven strategy was simulated
    as profitable.
    """
    out: list[float] = []
    for entry, exit_ in completed:
        entry_price = entry.get("price") or 0
        exit_price = exit_.get("price") or 0
        if not entry_price or not exit_price:
            continue
        if entry.get("side") == "sell":
            out.append((entry_price - exit_price) / entry_price)
        else:
            out.append((exit_price - entry_price) / entry_price)
    return out


def build_metrics(
    equity_curve: list[float],
    returns: list[float],
    trades: int,
    wins: int,
    interval: str,
    initial_capital: float,
) -> dict:
    """Assemble the standard metric block returned by every backtester.

    ``win_rate`` stays a FRACTION (0.6 = 60%) to match the existing backtest
    API contract. The ICT journal modules use percent for the same field,
    which is a separate inconsistency left untouched here.
    """
    ppy = periods_per_year(interval)
    dd = max_drawdown(equity_curve)
    final_equity = equity_curve[-1] if equity_curve else initial_capital
    total_return = (final_equity / initial_capital - 1) if initial_capital > 0 else 0.0
    return {
        "final_equity": round(final_equity, 2),
        "total_return": round(total_return, 6),
        "max_drawdown": round(dd, 6),
        "max_drawdown_pct": round(dd * 100, 2),
        "sharpe_ratio": sharpe_ratio(returns, ppy),
        "sortino_ratio": sortino_ratio(returns, ppy),
        "calmar_ratio": calmar_ratio(total_return, dd, len(returns), ppy),
        "trade_count": trades,
        "win_rate": round((wins / trades) if trades else 0.0, 6),
        "interval": interval,
    }
