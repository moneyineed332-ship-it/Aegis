"""Enhanced mean-reversion backtesting with regime filter, stop-loss, and bidirectional trading.

Uses Bollinger Bands z-score for entries with:
- Regime filter (only trade in ranging/low-volatility markets)
- ATR-based stop-loss
- Optional short selling when z-score is excessively high
- Sortino/Calmar ratios
"""

import logging
import math
from statistics import fmean, stdev

logger = logging.getLogger(__name__)


def _bollinger_series(closes: list[float], period: int) -> list[tuple[float, float, float]]:
    """Return (lower_band, upper_band, mid) for each index."""
    bands = []
    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1:i + 1]
        mid = fmean(window)
        std = stdev(window) if len(window) > 1 else 0
        bands.append((mid - 2 * std, mid + 2 * std, mid))
    return bands


def _compute_atr(candles: list[dict], period: int = 14) -> list[float]:
    """Build ATR series."""
    if len(candles) < period + 1:
        return [0.0] * len(candles)
    true_ranges = [0.0]
    for i in range(1, len(candles)):
        h, l, pc = candles[i]["high"], candles[i]["low"], candles[i - 1]["close"]
        true_ranges.append(max(h - l, abs(h - pc), abs(l - pc)))
    atr_series = [0.0] * period
    atr_val = fmean(true_ranges[1:period + 1])
    atr_series.append(atr_val)
    for i in range(period + 1, len(true_ranges)):
        atr_val = (atr_val * (period - 1) + true_ranges[i]) / period
        atr_series.append(atr_val)
    return atr_series


def _compute_adx(candles: list[dict], period: int = 14) -> list[float]:
    """Compute Average Directional Index (ADX) series."""
    if len(candles) < period * 2:
        return [25.0] * len(candles)  # Default neutral ADX

    # Calculate +DM and -DM
    plus_dm = [0.0]
    minus_dm = [0.0]
    for i in range(1, len(candles)):
        h, l, ph, pl = candles[i]["high"], candles[i]["low"], candles[i-1]["high"], candles[i-1]["low"]
        up = h - ph
        down = pl - l
        plus_dm.append(up if up > down and up > 0 else 0)
        minus_dm.append(down if down > up and down > 0 else 0)

    # Calculate TR
    tr = [0.0]
    for i in range(1, len(candles)):
        h, l, pc = candles[i]["high"], candles[i]["low"], candles[i-1]["close"]
        tr.append(max(h - l, abs(h - pc), abs(l - pc)))

    # Smoothed averages (Wilder's smoothing)
    atr_smooth = [0.0] * period
    plus_dm_smooth = [0.0] * period
    minus_dm_smooth = [0.0] * period

    atr_val = fmean(tr[1:period+1])
    plus_val = fmean(plus_dm[1:period+1])
    minus_val = fmean(minus_dm[1:period+1])

    atr_smooth.append(atr_val)
    plus_dm_smooth.append(plus_val)
    minus_dm_smooth.append(minus_val)

    for i in range(period + 1, len(candles)):
        atr_val = (atr_val * (period - 1) + tr[i]) / period
        plus_val = (plus_val * (period - 1) + plus_dm[i]) / period
        minus_val = (minus_val * (period - 1) + minus_dm[i]) / period
        atr_smooth.append(atr_val)
        plus_dm_smooth.append(plus_val)
        minus_dm_smooth.append(minus_val)

    # Calculate +DI and -DI
    plus_di = [100 * p / a if a > 0 else 0 for p, a in zip(plus_dm_smooth, atr_smooth)]
    minus_di = [100 * m / a if a > 0 else 0 for m, a in zip(minus_dm_smooth, atr_smooth)]

    # Calculate DX and ADX
    dx = []
    for p, m in zip(plus_di, minus_di):
        total = p + m
        dx.append(100 * abs(p - m) / total if total > 0 else 0)

    # ADX = smoothed DX
    adx_series = [25.0] * period
    if len(dx) > period:
        adx_val = fmean(dx[1:period+1])
        adx_series.append(adx_val)
        for i in range(period + 1, len(dx)):
            adx_val = (adx_val * (period - 1) + dx[i]) / period
            adx_series.append(adx_val)

    return adx_series


def _periods_per_year(interval: str) -> int:
    return {"5m": 105_120, "15m": 35_040, "1h": 8_760, "4h": 2_190, "1d": 365}.get(interval, 8_760)


def _sortino_ratio(returns: list[float], ppy: int) -> float:
    if len(returns) < 2:
        return 0.0
    downside = [r for r in returns if r < 0]
    if len(downside) < 2:
        return 0.0
    ds = stdev(downside)
    return round(fmean(returns) / ds * math.sqrt(ppy), 4) if ds > 0 else 0.0


def run_mean_reversion(candles: list[dict], parameters: dict) -> dict:
    """Enhanced mean reversion with regime filter, stop-loss, and optional shorts."""
    period = parameters["period"]
    entry_z = parameters["entry_z_score"]
    exit_z = parameters["exit_z_score"]
    initial_capital = parameters["initial_capital"]
    allocation = parameters["allocation"]
    fee_rate = parameters["fee_bps"] / 10_000
    slippage_rate = parameters["slippage_bps"] / 10_000
    interval = parameters.get("interval", "1h")
    atr_stop_mult = parameters.get("atr_stop_multiplier", 2.0)
    use_stop_loss = parameters.get("use_stop_loss", True)
    use_regime_filter = parameters.get("use_regime_filter", True)
    go_short = parameters.get("go_short", True)
    short_entry_z = parameters.get("short_entry_z_score", 2.5)

    if len(candles) <= period + 14:
        raise ValueError("Not enough candles for mean reversion.")

    closes = [c["close"] for c in candles]
    bands = _bollinger_series(closes, period)
    atr_series = _compute_atr(candles)
    adx_series = _compute_adx(candles)

    cash = initial_capital
    quantity = 0.0
    short_quantity = 0.0
    entry_price = 0.0
    stop_loss = 0.0
    trades: list[dict] = []
    equity_curve: list[float] = []
    returns: list[float] = []

    for offset, (lower_band, upper_band, mid) in enumerate(bands):
        index = offset + period - 1
        close = closes[index]
        std = (upper_band - lower_band) / 4
        z_score = (close - mid) / std if std > 0 else 0

        # Regime filter: skip entries in strong trends (ADX > 30),
        # but keep marking equity so the curve stays contiguous.
        adx = adx_series[index] if index < len(adx_series) else 25.0
        if use_regime_filter and adx > 30:
            equity = cash + quantity * close - short_quantity * close
            if equity_curve:
                returns.append(equity / equity_curve[-1] - 1)
            equity_curve.append(equity)
            continue  # Skip trade, market is trending

        # Update stop loss for long
        if quantity > 0 and use_stop_loss:
            stop_loss = entry_price - atr_stop_mult * atr_series[index]

        # Update stop loss for short
        if short_quantity > 0 and use_stop_loss:
            stop_loss = entry_price + atr_stop_mult * atr_series[index]

        # LONG ENTRY: price below lower band (oversold)
        if quantity == 0 and short_quantity == 0 and z_score <= entry_z:
            order_value = cash * allocation
            execution_price = close * (1 + slippage_rate)
            fee = order_value * fee_rate
            quantity = (order_value - fee) / execution_price
            cash -= order_value
            entry_price = execution_price
            stop_loss = entry_price - atr_stop_mult * atr_series[index]
            trades.append({"side": "buy", "price": execution_price, "time": candles[index]["close_time"], "fee": fee, "z_score": z_score})

        # LONG EXIT: z-score reverts to SMA OR stop-loss hit
        elif quantity > 0 and (z_score >= exit_z or (use_stop_loss and close < stop_loss)):
            execution_price = close * (1 - slippage_rate)
            proceeds = quantity * execution_price
            fee = proceeds * fee_rate
            cash += proceeds - fee
            trades.append({"side": "sell", "price": execution_price, "time": candles[index]["close_time"], "fee": fee, "z_score": z_score})
            quantity = 0.0

        # SHORT ENTRY: price above upper band (overbought)
        elif go_short and short_quantity == 0 and quantity == 0 and z_score >= short_entry_z:
            short_value = cash * allocation
            execution_price = close * (1 - slippage_rate)
            fee = short_value * fee_rate
            short_quantity = (short_value - fee) / execution_price
            cash += short_value - fee  # Credit short proceeds
            entry_price = execution_price
            stop_loss = entry_price + atr_stop_mult * atr_series[index]
            trades.append({"side": "short", "price": execution_price, "time": candles[index]["close_time"], "fee": fee, "z_score": z_score})

        # SHORT EXIT: z-score reverts to SMA OR stop-loss hit
        elif short_quantity > 0 and (z_score <= exit_z or (use_stop_loss and close > stop_loss)):
            execution_price = close * (1 + slippage_rate)
            cost = short_quantity * execution_price
            fee = cost * fee_rate
            cash -= cost + fee  # Pay to cover the short
            trades.append({"side": "cover", "price": execution_price, "time": candles[index]["close_time"], "fee": fee, "z_score": z_score})
            short_quantity = 0.0

        equity = cash + quantity * close - short_quantity * close
        if equity_curve:
            returns.append(equity / equity_curve[-1] - 1)
        equity_curve.append(equity)

    if not equity_curve:
        return {"final_equity": initial_capital, "total_return": 0, "max_drawdown": 0, "sharpe_ratio": 0, "sortino_ratio": 0, "trade_count": 0, "win_rate": 0}

    final_equity = equity_curve[-1]
    peak, max_drawdown = equity_curve[0], 0.0
    for eq in equity_curve:
        peak = max(peak, eq)
        max_drawdown = min(max_drawdown, eq / peak - 1)

    completed = list(zip(trades[::2], trades[1::2]))
    def _is_win(t1, t2):
        if t1["side"] == "buy":
            return t2["price"] > t1["price"]
        else:  # short
            return t2["price"] < t1["price"]
    wins = sum(1 for t1, t2 in completed if _is_win(t1, t2))
    ppy = _periods_per_year(interval)
    sharpe = fmean(returns) / stdev(returns) * math.sqrt(ppy) if len(returns) > 1 and stdev(returns) > 0 else 0.0
    sortino = _sortino_ratio(returns, ppy)

    return {
        "final_equity": round(final_equity, 2),
        "total_return": round(final_equity / initial_capital - 1, 6),
        "max_drawdown": round(max_drawdown, 6),
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": sortino,
        "trade_count": len(completed),
        "win_rate": round(wins / len(completed), 6) if completed else 0.0,
    }


def run_mean_reversion_walk_forward(candles: list[dict], base_parameters: dict, candidates: list[tuple[float, float]]) -> dict:
    """Walk-forward with embargo for mean reversion."""
    train_size = base_parameters["train_candles"]
    test_size = base_parameters["test_candles"]
    embargo = base_parameters.get("embargo_candles", 10)
    if len(candles) < train_size + test_size + embargo:
        raise ValueError("Not enough candles.")
    selected = candles[-(train_size + embargo + test_size):]
    train_candles = selected[:train_size]
    test_candles = selected[train_size + embargo:]
    evaluations = []
    for entry_z, exit_z in candidates:
        try:
            metrics = run_mean_reversion(train_candles, {**base_parameters, "entry_z_score": entry_z, "exit_z_score": exit_z})
            evaluations.append({"entry_z_score": entry_z, "exit_z_score": exit_z, "train_metrics": metrics})
        except Exception as e:
            logger.debug("Mean reversion walk-forward candidate failed: entry_z=%s exit_z=%s — %s", entry_z, exit_z, e, exc_info=True)
            continue
    if not evaluations:
        raise ValueError("All candidates failed.")
    winner = max(evaluations, key=lambda e: e["train_metrics"]["sharpe_ratio"])
    oos = run_mean_reversion(test_candles, {**base_parameters, "entry_z_score": winner["entry_z_score"], "exit_z_score": winner["exit_z_score"]})
    return {
        "selected_parameters": {"entry_z_score": winner["entry_z_score"], "exit_z_score": winner["exit_z_score"]},
        "train_metrics": winner["train_metrics"],
        "out_of_sample_metrics": oos,
        "candidates": evaluations,
    }
