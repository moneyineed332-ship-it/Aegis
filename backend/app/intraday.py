"""Intraday strategy — session-based momentum with VWAP, RSI, and pivot points.

Designed for 15m-1h candles within a single trading day.
Uses VWAP for directional bias, RSI for momentum, and daily pivot
points for support/resistance. Positions closed before session end.
"""

import math
from statistics import fmean, stdev

from .indicators import ema_series, rsi_series, atr_series, periods_per_year as _ppy


def _vwap(candles: list[dict]) -> list[float]:
    cum_vol_price = 0.0
    cum_vol = 0.0
    result = []
    for c in candles:
        typical = (c["high"] + c["low"] + c["close"]) / 3
        vol = c.get("volume", 1)
        cum_vol_price += typical * vol
        cum_vol += vol
        result.append(cum_vol_price / cum_vol if cum_vol > 0 else typical)
    return result


def _pivot_points(high: float, low: float, close: float) -> dict:
    pp = (high + low + close) / 3
    return {
        "R3": round(close + 2 * (high - low), 2),
        "R2": round(high + (close - low), 2),
        "R1": round(2 * pp - low, 2),
        "PP": round(pp, 2),
        "S1": round(2 * pp - high, 2),
        "S2": round(low - (high - close), 2),
        "S3": round(close - 2 * (high - low), 2),
    }


def run_intraday(candles: list[dict], parameters: dict) -> dict:
    """Run VWAP + RSI intraday momentum strategy.

    Parameters:
        rsi_period (int): RSI period, default 14
        rsi_bull_threshold (float): RSI long entry, default 55
        rsi_bear_threshold (float): RSI short entry, default 45
        rsi_overbought (float): RSI exit long, default 75
        rsi_oversold (float): RSI exit short, default 25
        ema_fast (int): Fast EMA for trend, default 9
        ema_slow (int): Slow EMA for trend, default 21
        atr_period (int): ATR period, default 14
        atr_stop_multiplier (float): ATR stop multiplier, default 1.5
        use_shorts (bool): Allow short positions, default True
        initial_capital (float): Starting capital
        allocation (float): Fraction of capital per trade
        fee_bps (float): Fee in basis points
        slippage_bps (float): Slippage in basis points
        interval (str): Candle interval for annualization
    """
    rsi_period = parameters.get("rsi_period", 14)
    rsi_bull = parameters.get("rsi_bull_threshold", 55)
    rsi_bear = parameters.get("rsi_bear_threshold", 45)
    rsi_ob = parameters.get("rsi_overbought", 75)
    rsi_os = parameters.get("rsi_oversold", 25)
    ema_fast_period = parameters.get("ema_fast", 9)
    ema_slow_period = parameters.get("ema_slow", 21)
    atr_period = parameters.get("atr_period", 14)
    atr_stop_mult = parameters.get("atr_stop_multiplier", 1.5)
    use_shorts = parameters.get("use_shorts", True)
    initial_capital = parameters["initial_capital"]
    allocation = parameters.get("allocation", 0.10)
    fee_rate = parameters.get("fee_bps", 10) / 10_000
    slippage_rate = parameters.get("slippage_bps", 5) / 10_000
    interval = parameters.get("interval", "15m")

    if len(candles) < max(ema_slow_period, atr_period, rsi_period) + 10:
        raise ValueError("Not enough candles for intraday (min ~35).")

    closes = [c["close"] for c in candles]
    vwap_vals = _vwap(candles)
    rsi_vals = rsi_series(closes, rsi_period)
    ema_fast_vals = ema_series(closes, ema_fast_period)
    ema_slow_vals = ema_series(closes, ema_slow_period)
    atr_vals = atr_series(candles, atr_period)

    cash = initial_capital
    quantity = 0.0
    short_quantity = 0.0
    entry_price = 0.0
    stop_loss = 0.0
    trades: list[dict] = []
    equity_curve: list[float] = []
    returns: list[float] = []

    for index, candle in enumerate(candles):
        close = candle["close"]
        high = candle["high"]
        low = candle["low"]

        if index < max(ema_slow_period, atr_period, rsi_period):
            equity_curve.append(cash)
            continue

        vwap = vwap_vals[index]
        above_vwap = close > vwap
        below_vwap = close < vwap
        ema_bullish = ema_fast_vals[index] > ema_slow_vals[index]
        ema_bearish = ema_fast_vals[index] < ema_slow_vals[index]
        atr_val = atr_vals[index] if atr_vals[index] > 0 else close * 0.01

        prev_high = max(c["high"] for c in candles[max(0, index - 20):index])
        prev_low = min(c["low"] for c in candles[max(0, index - 20):index])
        prev_close = candles[index - 1]["close"] if index > 0 else close
        pivots = _pivot_points(prev_high, prev_low, prev_close)

        if quantity > 0 and short_quantity == 0:
            hit_stop = close < stop_loss
            rsi_exit = rsi_vals[index] > rsi_ob
            vwap_exit = below_vwap and ema_bearish

            if hit_stop or rsi_exit or vwap_exit:
                execution_price = close * (1 - slippage_rate)
                proceeds = quantity * execution_price
                fee = proceeds * fee_rate
                cash += proceeds - fee
                pnl = (execution_price - entry_price) / entry_price
                trades.append({
                    "side": "sell", "price": execution_price,
                    "time": candle["close_time"], "fee": fee,
                    "pnl_pct": round(pnl * 100, 3),
                    "exit_reason": "stop_loss" if hit_stop else ("rsi_overbought" if rsi_exit else "vwap_cross"),
                })
                quantity = 0.0

        elif short_quantity > 0 and quantity == 0:
            hit_stop = close > stop_loss
            rsi_exit = rsi_vals[index] < rsi_os
            vwap_exit = above_vwap and ema_bullish

            if hit_stop or rsi_exit or vwap_exit:
                buy_price = close * (1 + slippage_rate)
                cost = short_quantity * buy_price
                fee = cost * fee_rate
                cash += (entry_price * short_quantity) - cost - fee
                pnl = (entry_price - buy_price) / entry_price
                trades.append({
                    "side": "buy_to_cover", "price": buy_price,
                    "time": candle["close_time"], "fee": fee,
                    "pnl_pct": round(pnl * 100, 3),
                    "exit_reason": "stop_loss" if hit_stop else ("rsi_oversold" if rsi_exit else "vwap_cross"),
                })
                short_quantity = 0.0

        if quantity == 0 and short_quantity == 0:
            if above_vwap and ema_bullish and rsi_vals[index] > rsi_bull:
                order_value = cash * allocation
                execution_price = close * (1 + slippage_rate)
                fee = order_value * fee_rate
                quantity = (order_value - fee) / execution_price
                cash -= order_value
                entry_price = execution_price
                stop_loss = entry_price - atr_stop_mult * atr_val
                trades.append({
                    "side": "buy", "price": execution_price,
                    "time": candle["close_time"], "fee": fee,
                    "stop_loss": round(stop_loss, 2),
                })

            elif use_shorts and below_vwap and ema_bearish and rsi_vals[index] < rsi_bear:
                order_value = cash * allocation
                execution_price = close * (1 - slippage_rate)
                fee = order_value * fee_rate
                short_quantity = (order_value - fee) / execution_price
                cash -= fee
                entry_price = execution_price
                stop_loss = entry_price + atr_stop_mult * atr_val
                trades.append({
                    "side": "short", "price": execution_price,
                    "time": candle["close_time"], "fee": fee,
                    "stop_loss": round(stop_loss, 2),
                })

        equity = cash + quantity * close
        if short_quantity > 0:
            equity += short_quantity * (2 * entry_price - close)
        if equity_curve:
            returns.append(equity / equity_curve[-1] - 1)
        equity_curve.append(equity)

    if not equity_curve:
        raise ValueError("Not enough data to compute results.")

    final_equity = equity_curve[-1]
    peak, max_drawdown = equity_curve[0], 0.0
    for eq in equity_curve:
        peak = max(peak, eq)
        if peak > 0:
            max_drawdown = min(max_drawdown, eq / peak - 1)

    completed = list(zip(trades[::2], trades[1::2]))
    wins = sum(1 for b, s in completed if s["price"] != b["price"] and
               ((s["side"] == "sell" and s["price"] > b["price"]) or
                (s["side"] == "buy_to_cover" and s["price"] < b["price"])))
    ppy = _ppy(interval)
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
            fmean([abs(s["price"] - b["price"]) / b["price"] for b, s in completed]), 6
        ) if completed else 0.0,
        "strategy": "intraday",
        "parameters_used": {
            "rsi_period": rsi_period, "ema_fast": ema_fast_period,
            "ema_slow": ema_slow_period, "atr_stop_multiplier": atr_stop_mult,
            "use_shorts": use_shorts,
        },
    }
