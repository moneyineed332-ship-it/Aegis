"""Swing Trading strategy — multi-day trend following with MACD, Fibonacci, and ATR.

Designed for 4h-1d candles. Holds positions for days to weeks.
Uses MACD(12,26,9) for trend, Fibonacci retracement for entries,
and ATR-based trailing stops with wider risk tolerance.
"""

import math
from statistics import fmean, stdev


def _ema(data: list[float], period: int) -> list[float]:
    if not data:
        return []
    k = 2 / (period + 1)
    ema_vals = [data[0]]
    for i in range(1, len(data)):
        ema_vals.append(data[i] * k + ema_vals[-1] * (1 - k))
    return ema_vals


def _macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[list[float], list[float], list[float]]:
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line = _ema(macd_line, signal)
    histogram = [m - s for m, s in zip(macd_line, signal_line)]
    return macd_line, signal_line, histogram


def _atr(candles: list[dict], period: int = 14) -> list[float]:
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


def _rsi(closes: list[float], period: int = 14) -> list[float]:
    if len(closes) < period + 1:
        return [50.0] * len(closes)
    rsi_vals = [50.0] * period
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = fmean(gains[:period])
    avg_loss = fmean(losses[:period])
    if avg_loss == 0:
        rsi_vals.append(100.0)
    else:
        rsi_vals.append(100 - 100 / (1 + avg_gain / avg_loss))
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi_vals.append(100.0)
        else:
            rsi_vals.append(100 - 100 / (1 + avg_gain / avg_loss))
    return rsi_vals


def _fib_levels(high: float, low: float) -> dict:
    diff = high - low
    return {
        "0.0": round(low, 2),
        "0.236": round(low + 0.236 * diff, 2),
        "0.382": round(low + 0.382 * diff, 2),
        "0.5": round(low + 0.5 * diff, 2),
        "0.618": round(low + 0.618 * diff, 2),
        "0.786": round(low + 0.786 * diff, 2),
        "1.0": round(high, 2),
    }


def _periods_per_year(interval: str) -> int:
    return {"4h": 2_190, "1d": 365}.get(interval, 365)


def run_swing(candles: list[dict], parameters: dict) -> dict:
    """Run MACD + Fibonacci swing trading strategy.

    Parameters:
        macd_fast (int): MACD fast period, default 12
        macd_slow (int): MACD slow period, default 26
        macd_signal (int): MACD signal period, default 9
        fibonacci_lookback (int): Bars to find swing high/low, default 30
        atr_period (int): ATR period, default 14
        atr_stop_multiplier (float): ATR multiplier for stop, default 3.0
        atr_trail_multiplier (float): ATR multiplier for trailing, default 2.5
        rsi_period (int): RSI period, default 14
        rsi_filter (bool): Use RSI to filter entries, default True
        initial_capital (float): Starting capital
        allocation (float): Fraction of capital per trade
        fee_bps (float): Fee in basis points
        slippage_bps (float): Slippage in basis points
        interval (str): Candle interval for annualization
    """
    macd_fast = parameters.get("macd_fast", 12)
    macd_slow = parameters.get("macd_slow", 26)
    macd_signal = parameters.get("macd_signal", 9)
    fib_lookback = parameters.get("fibonacci_lookback", 30)
    atr_period = parameters.get("atr_period", 14)
    atr_stop_mult = parameters.get("atr_stop_multiplier", 3.0)
    atr_trail_mult = parameters.get("atr_trail_multiplier", 2.5)
    rsi_period = parameters.get("rsi_period", 14)
    use_rsi_filter = parameters.get("rsi_filter", True)
    initial_capital = parameters["initial_capital"]
    allocation = parameters.get("allocation", 0.15)
    fee_rate = parameters.get("fee_bps", 10) / 10_000
    slippage_rate = parameters.get("slippage_bps", 5) / 10_000
    interval = parameters.get("interval", "4h")

    if len(candles) < max(macd_slow + macd_signal, fib_lookback, atr_period, rsi_period) + 10:
        raise ValueError("Pas assez de candles pour swing trading (min ~50).")

    closes = [c["close"] for c in candles]
    macd_line, signal_line, histogram = _macd(closes, macd_fast, macd_slow, macd_signal)
    atr_vals = _atr(candles, atr_period)
    rsi_vals = _rsi(closes, rsi_period)

    cash = initial_capital
    quantity = 0.0
    entry_price = 0.0
    trailing_stop = 0.0
    highest_since_entry = 0.0
    fib_entry = 0.0
    trades: list[dict] = []
    equity_curve: list[float] = []
    returns: list[float] = []

    for index, candle in enumerate(candles):
        close = candle["close"]
        high = candle["high"]

        if index < max(macd_slow + macd_signal, fib_lookback, atr_period, rsi_period):
            equity_curve.append(cash)
            continue

        macd_cross_up = histogram[index] > 0 and histogram[index - 1] <= 0
        macd_cross_down = histogram[index] < 0 and histogram[index - 1] >= 0
        macd_bullish = histogram[index] > 0

        lookback_high = max(c["high"] for c in candles[index - fib_lookback:index])
        lookback_low = min(c["low"] for c in candles[index - fib_lookback:index])
        fib = _fib_levels(lookback_high, lookback_low)

        rsi_ok = not use_rsi_filter or (30 < rsi_vals[index] < 70)
        atr_val = atr_vals[index] if atr_vals[index] > 0 else close * 0.02

        if quantity > 0:
            highest_since_entry = max(highest_since_entry, high)
            trailing_stop = highest_since_entry - atr_trail_mult * atr_val

        if quantity == 0:
            if macd_cross_up and rsi_ok:
                fib_entry = fib["0.382"]
                if close <= fib_entry * 1.01:
                    order_value = cash * allocation
                    execution_price = close * (1 + slippage_rate)
                    fee = order_value * fee_rate
                    quantity = (order_value - fee) / execution_price
                    cash -= order_value
                    entry_price = execution_price
                    highest_since_entry = high
                    trailing_stop = entry_price - atr_stop_mult * atr_val
                    trades.append({
                        "side": "buy", "price": execution_price,
                        "time": candle["close_time"], "fee": fee,
                        "stop_loss": round(trailing_stop, 2),
                        "fib_0382": fib["0.382"], "fib_0618": fib["0.618"],
                    })

        elif quantity > 0:
            hit_stop = close < trailing_stop
            signal_exit = macd_cross_down or (macd_bullish and rsi_vals[index] > 75)

            if hit_stop or signal_exit:
                execution_price = close * (1 - slippage_rate)
                proceeds = quantity * execution_price
                fee = proceeds * fee_rate
                cash += proceeds - fee
                pnl = (execution_price - entry_price) / entry_price
                trades.append({
                    "side": "sell", "price": execution_price,
                    "time": candle["close_time"], "fee": fee,
                    "pnl_pct": round(pnl * 100, 3),
                    "exit_reason": "trailing_stop" if hit_stop else "macd_signal",
                })
                quantity = 0.0

        equity = cash + quantity * close
        if equity_curve:
            returns.append(equity / equity_curve[-1] - 1)
        equity_curve.append(equity)

    if not equity_curve:
        raise ValueError("Pas de données suffisantes.")

    final_equity = equity_curve[-1]
    peak, max_drawdown = equity_curve[0], 0.0
    for eq in equity_curve:
        peak = max(peak, eq)
        if peak > 0:
            max_drawdown = min(max_drawdown, eq / peak - 1)

    completed = list(zip(trades[::2], trades[1::2]))
    wins = sum(1 for b, s in completed if s["price"] > b["price"])
    ppy = _periods_per_year(interval)
    sharpe = (fmean(returns) / stdev(returns) * math.sqrt(ppy)
              if len(returns) > 1 and stdev(returns) > 0 else 0.0)

    return {
        "final_equity": round(final_equity, 2),
        "total_return": round(final_equity / initial_capital - 1, 6),
        "max_drawdown": round(max_drawdown, 6),
        "sharpe_ratio": round(sharpe, 4),
        "trade_count": len(completed),
        "win_rate": round(wins / len(completed), 6) if completed else 0.0,
        "avg_trade_return": round(
            fmean([s["price"] / b["price"] - 1 for b, s in completed]), 6
        ) if completed else 0.0,
        "strategy": "swing",
        "parameters_used": {
            "macd_fast": macd_fast, "macd_slow": macd_slow, "macd_signal": macd_signal,
            "atr_stop_multiplier": atr_stop_mult, "atr_trail_multiplier": atr_trail_mult,
        },
    }
