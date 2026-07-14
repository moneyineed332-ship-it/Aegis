"""Advanced risk metrics: VaR/CVaR, stress tests, correlation, concentration."""

import math
from statistics import fmean, stdev


def historical_risk(candles: list[dict], capital: float, confidence: float = 0.95) -> dict:
    """Core VaR/CVaR calculation."""
    closes = [candle["close"] for candle in candles]
    if len(closes) < 30:
        raise ValueError("At least 30 candles are required for historical risk metrics.")
    returns = sorted(closes[index] / closes[index - 1] - 1 for index in range(1, len(closes)))
    tail_size = max(1, int((1 - confidence) * len(returns)))
    tail = returns[:tail_size]
    var_return = -tail[-1]
    cvar_return = -sum(tail) / len(tail)

    # Additional metrics
    max_drawdown = _max_drawdown(closes)
    volatility = stdev(returns) if len(returns) > 1 else 0
    annualized_vol = volatility * math.sqrt(8760)  # hourly candles

    return {
        "confidence": confidence,
        "observations": len(returns),
        "value_at_risk": round(capital * var_return, 2),
        "conditional_value_at_risk": round(capital * cvar_return, 2),
        "max_drawdown": round(max_drawdown, 6),
        "max_drawdown_pct": round(max_drawdown * 100, 2),
        "volatility": round(volatility, 6),
        "annualized_volatility": round(annualized_vol, 4),
    }


def _max_drawdown(closes: list[float]) -> float:
    """Calculate maximum drawdown from closes."""
    peak = closes[0]
    max_dd = 0.0
    for price in closes:
        peak = max(peak, price)
        dd = price / peak - 1
        max_dd = min(max_dd, dd)
    return max_dd


def stress_test(candles: list[dict], capital: float, position_value: float = 0) -> dict:
    """Simulate extreme market scenarios and compute impact."""
    closes = [candle["close"] for candle in candles]
    if len(closes) < 30:
        raise ValueError("At least 30 candles required for stress tests.")

    current_price = closes[-1]
    returns = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
    worst_day = min(returns)
    worst_week = min(_rolling_sum(returns, 7))
    worst_month = min(_rolling_sum(returns, 30))
    avg_vol = fmean([abs(r) for r in returns])
    max_vol = max([abs(r) for r in returns])

    scenarios = [
        {
            "name": "Flash Crash (-20%)",
            "price_impact": -0.20,
            "portfolio_impact": round(position_value * -0.20, 2) if position_value else 0,
            "description": "Similar to March 2020 COVID crash",
        },
        {
            "name": "Extreme Crash (-40%)",
            "price_impact": -0.40,
            "portfolio_impact": round(position_value * -0.40, 2) if position_value else 0,
            "description": "Similar to Luna/Terra collapse",
        },
        {
            "name": "Worst Historical Day",
            "price_impact": round(worst_day, 4),
            "portfolio_impact": round(position_value * worst_day, 2) if position_value else 0,
            "description": f"Based on worst observed daily return ({worst_day*100:.1f}%)",
        },
        {
            "name": "Worst Historical Week",
            "price_impact": round(worst_week, 4),
            "portfolio_impact": round(position_value * worst_week, 2) if position_value else 0,
            "description": f"Based on worst observed 7-day return ({worst_week*100:.1f}%)",
        },
        {
            "name": "Worst Historical Month",
            "price_impact": round(worst_month, 4),
            "portfolio_impact": round(position_value * worst_month, 2) if position_value else 0,
            "description": f"Based on worst observed 30-day return ({worst_month*100:.1f}%)",
        },
        {
            "name": "3x Volatility Spike",
            "price_impact": round(-3 * avg_vol, 4),
            "portfolio_impact": round(position_value * -3 * avg_vol, 2) if position_value else 0,
            "description": f"Price move of 3x average volatility ({3*avg_vol*100:.1f}%)",
        },
        {
            "name": "Exchange Outage Recovery",
            "price_impact": round(-max_vol * 1.5, 4),
            "portfolio_impact": round(position_value * -max_vol * 1.5, 2) if position_value else 0,
            "description": "1.5x worst observed move (simulates post-outage dump)",
        },
    ]

    return {
        "current_price": current_price,
        "position_value": position_value,
        "capital": capital,
        "worst_day_return": round(worst_day * 100, 2),
        "worst_week_return": round(worst_week * 100, 2),
        "worst_month_return": round(worst_month * 100, 2),
        "avg_daily_volatility": round(avg_vol * 100, 2),
        "max_daily_volatility": round(max_vol * 100, 2),
        "scenarios": scenarios,
    }


def _rolling_sum(data: list[float], window: int) -> list[float]:
    """Rolling sum over a window."""
    result = []
    for i in range(len(data) - window + 1):
        result.append(sum(data[i:i + window]))
    return result


def correlation_matrix(assets: dict[str, list[float]]) -> dict:
    """Compute correlation matrix between multiple assets.

    assets: {"BTCUSDT": [closes...], "ETHUSDT": [closes...], ...}
    """
    symbols = list(assets.keys())
    n = len(symbols)
    if n < 2:
        return {"symbols": symbols, "matrix": {}, "avg_correlation": None}

    # Compute returns for each asset
    returns = {}
    for sym, closes in assets.items():
        if len(closes) < 2:
            returns[sym] = []
        else:
            returns[sym] = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]

    # Align lengths
    min_len = min(len(r) for r in returns.values()) if returns else 0
    for sym in returns:
        returns[sym] = returns[sym][-min_len:]

    # Compute correlation matrix
    matrix = {}
    all_correlations = []
    for i, sym_a in enumerate(symbols):
        matrix[sym_a] = {}
        for j, sym_b in enumerate(symbols):
            if i == j:
                matrix[sym_a][sym_b] = 1.0
            elif sym_b in matrix and sym_a in matrix[sym_b]:
                matrix[sym_a][sym_b] = matrix[sym_b][sym_a]
            else:
                corr = _pearson_correlation(returns[sym_a], returns[sym_b])
                matrix[sym_a][sym_b] = round(corr, 4)
                if i != j:
                    all_correlations.append(corr)

    avg_corr = round(fmean(all_correlations), 4) if all_correlations else None

    return {
        "symbols": symbols,
        "matrix": matrix,
        "avg_correlation": avg_corr,
        "interpretation": _interpret_correlation(avg_corr),
    }


def _pearson_correlation(x: list[float], y: list[float]) -> float:
    """Pearson correlation coefficient."""
    if len(x) < 2 or len(y) < 2:
        return 0.0
    n = min(len(x), len(y))
    x, y = x[-n:], y[-n:]
    mx, my = fmean(x), fmean(y)
    num = sum((x[i] - mx) * (y[i] - my) for i in range(n))
    den_x = math.sqrt(sum((xi - mx) ** 2 for xi in x))
    den_y = math.sqrt(sum((yi - my) ** 2 for yi in y))
    if den_x == 0 or den_y == 0:
        return 0.0
    return num / (den_x * den_y)


def concentration_risk(positions: list[dict], prices: dict[str, float]) -> dict:
    """Calculate concentration risk from open positions."""
    if not positions:
        return {"total_exposure": 0, "herfindahl": 0, "max_concentration": 0, "positions": []}

    position_values = []
    for pos in positions:
        price = prices.get(pos["symbol"], pos["average_price"])
        value = abs(pos["quantity"] * price)
        position_values.append({"symbol": pos["symbol"], "value": round(value, 2), "quantity": pos["quantity"]})

    total = sum(p["value"] for p in position_values)
    if total == 0:
        return {"total_exposure": 0, "herfindahl": 0, "max_concentration": 0, "positions": []}

    # Herfindahl-Hirschman Index (0 = perfect diversification, 1 = full concentration)
    weights = [p["value"] / total for p in position_values]
    hhi = sum(w ** 2 for w in weights)

    for p in position_values:
        p["weight"] = round(p["value"] / total * 100, 2)

    return {
        "total_exposure": round(total, 2),
        "herfindahl": round(hhi, 4),
        "max_concentration": round(max(p["weight"] for p in position_values), 2),
        "position_count": len(position_values),
        "positions": position_values,
    }
