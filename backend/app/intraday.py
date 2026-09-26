"""Intraday strategy — session-based momentum with VWAP, RSI, and pivot points.

Designed for 15m-1h candles within a single trading day.
Uses VWAP for directional bias, RSI for momentum, and daily pivot
points for support/resistance. Positions closed before session end.
"""

import math
from statistics import fmean, stdev

from .indicators import ema_series, rsi_series, atr_series, periods_per_year as _ppy
from .execution_model import assert_no_lookahead, fill_price
from .metrics_core import max_drawdown, sharpe_ratio, signed_trade_returns


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


def run_intraday(candles: list[dict], parameters: dict,
    trades_out: list[dict] | None = None,
) -> dict:
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
    # Bar the position was filled on; no exit may trigger before it.
    fill_idx = -1

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

        # --- Long exit: decided on this bar, filled at the NEXT bar's open. ---
        if quantity > 0 and short_quantity == 0 and index > fill_idx:
            hit_stop = close < stop_loss
            rsi_exit = rsi_vals[index] > rsi_ob
            vwap_exit = below_vwap and ema_bearish
            if hit_stop or rsi_exit or vwap_exit:
                execution_price = fill_price(candles, index, "sell", slippage_rate)
                if execution_price is not None:
                    proceeds = quantity * execution_price
                    fee = proceeds * fee_rate
                    cash += proceeds - fee
                    pnl = (execution_price - entry_price) / entry_price
                    trades.append({
                        "side": "sell", "price": execution_price,
                        "time": candles[index + 1]["close_time"], "fee": fee,
                        "pnl_pct": round(pnl * 100, 3),
                        "exit_reason": "stop_loss" if hit_stop else ("rsi_overbought" if rsi_exit else "vwap_cross"),
                        "signal_index": index, "fill_index": index + 1,
                    })
                    quantity = 0.0

        # --- Short exit, same rule. ---
        elif short_quantity > 0 and quantity == 0 and index > fill_idx:
            hit_stop = close > stop_loss
            rsi_exit = rsi_vals[index] < rsi_os
            vwap_exit = above_vwap and ema_bullish
            if hit_stop or rsi_exit or vwap_exit:
                buy_price = fill_price(candles, index, "buy", slippage_rate)
                if buy_price is not None:
                    cost = short_quantity * buy_price
                    fee = cost * fee_rate
                    cash -= cost + fee  # Pay to cover the short
                    pnl = (entry_price - buy_price) / entry_price
                    trades.append({
                        "side": "buy_to_cover", "price": buy_price,
                        "time": candles[index + 1]["close_time"], "fee": fee,
                        "pnl_pct": round(pnl * 100, 3),
                        "exit_reason": "stop_loss" if hit_stop else ("rsi_oversold" if rsi_exit else "vwap_cross"),
                        "signal_index": index, "fill_index": index + 1,
                    })
                    short_quantity = 0.0

        # --- Entry: decided on this bar, filled at the NEXT bar's open. ---
        if quantity == 0 and short_quantity == 0:
            if above_vwap and ema_bullish and rsi_vals[index] > rsi_bull:
                execution_price = fill_price(candles, index, "buy", slippage_rate)
                if execution_price is not None:
                    order_value = cash * allocation
                    fee = order_value * fee_rate
                    quantity = (order_value - fee) / execution_price
                    cash -= order_value
                    entry_price = execution_price
                    stop_loss = entry_price - atr_stop_mult * atr_val
                    fill_idx = index + 1
                    trades.append({
                        "side": "buy", "price": execution_price,
                        "time": candles[index + 1]["close_time"], "fee": fee,
                        "stop_loss": round(stop_loss, 2),
                        "signal_index": index, "fill_index": index + 1,
                    })

            elif use_shorts and below_vwap and ema_bearish and rsi_vals[index] < rsi_bear:
                execution_price = fill_price(candles, index, "sell", slippage_rate)
                if execution_price is not None:
                    order_value = cash * allocation
                    fee = order_value * fee_rate
                    short_quantity = (order_value - fee) / execution_price
                    cash += order_value - fee  # Credit short proceeds
                    entry_price = execution_price
                    stop_loss = entry_price + atr_stop_mult * atr_val
                    fill_idx = index + 1
                    trades.append({
                        "side": "short", "price": execution_price,
                        "time": candles[index + 1]["close_time"], "fee": fee,
                        "stop_loss": round(stop_loss, 2),
                        "signal_index": index, "fill_index": index + 1,
                    })

        equity = cash + quantity * close - short_quantity * close
        if equity_curve:
            returns.append(equity / equity_curve[-1] - 1)
        equity_curve.append(equity)

    if not equity_curve:
        raise ValueError("Not enough data to compute results.")

    final_equity = equity_curve[-1]
    drawdown = max_drawdown(equity_curve)
    assert_no_lookahead(trades, candles)
    if trades_out is not None:
        trades_out.extend(trades)

    completed = list(zip(trades[::2], trades[1::2]))

    def _pair_return(open_trade: dict, close_trade: dict) -> float:
        """Signed return: long wins when price rises, short wins when it falls."""
        entry = open_trade["price"]
        if not entry:
            return 0.0
        if open_trade["side"] == "buy":
            return (close_trade["price"] - entry) / entry
        return (entry - close_trade["price"]) / entry

    wins = sum(1 for b, s in completed if s["price"] != b["price"] and
               ((s["side"] == "sell" and s["price"] > b["price"]) or
                (s["side"] == "buy_to_cover" and s["price"] < b["price"])))
    ppy = _ppy(interval)
    sharpe = sharpe_ratio(returns, ppy)

    return {
        "final_equity": round(final_equity, 2),
        "total_return": round(final_equity / initial_capital - 1, 6),
        "max_drawdown": round(drawdown, 6),
        "sharpe_ratio": round(sharpe, 4),
        "trade_count": len(completed),
        "win_rate": round(wins / len(completed), 6) if completed else 0.0,
        "avg_trade_return": round(
            fmean([_pair_return(b, s) for b, s in completed]), 6
        ) if completed else 0.0,
        "trade_returns": [_pair_return(b, s) for b, s in completed],
        "strategy": "intraday",
        "parameters_used": {
            "rsi_period": rsi_period, "ema_fast": ema_fast_period,
            "ema_slow": ema_slow_period, "atr_stop_multiplier": atr_stop_mult,
            "use_shorts": use_shorts,
        },
    }
