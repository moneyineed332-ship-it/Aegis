"""Scalping strategy — ultra-short-term EMA crossover + RSI + Stochastic.

Designed for 1m-5m candles. High-frequency entries with tight risk management.
Uses EMA(3)/EMA(8) fast crosses, RSI(3) for overbought/oversold, and
Stochastic(5,3,3) for momentum confirmation.
"""

import math
from statistics import fmean, stdev

from .indicators import ema_series, rsi_series, atr_series, stochastic, periods_per_year as _ppy
from .execution_model import assert_no_lookahead, fill_price, intrabar_exit_price
from .metrics_core import max_drawdown, sharpe_ratio, signed_trade_returns


def run_scalping(candles: list[dict], parameters: dict,
    trades_out: list[dict] | None = None,
) -> dict:
    """Run EMA(3)/EMA(8) scalping strategy.

    Parameters:
        ema_fast (int): Fast EMA period, default 3
        ema_slow (int): Slow EMA period, default 8
        rsi_period (int): RSI period, default 3
        rsi_overbought (float): RSI overbought threshold, default 75
        rsi_oversold (float): RSI oversold threshold, default 25
        stoch_k (int): Stochastic K period, default 5
        stoch_d (int): Stochastic D period, default 3
        stoch_overbought (float): Stochastic overbought, default 80
        stoch_oversold (float): Stochastic oversold, default 20
        atr_stop_multiplier (float): ATR multiplier for stop, default 1.5
        take_profit_ratio (float): TP/SL ratio, default 1.5
        initial_capital (float): Starting capital
        allocation (float): Fraction of capital per trade, default 0.05
        fee_bps (float): Fee in basis points
        slippage_bps (float): Slippage in basis points
        interval (str): Candle interval for annualization
        max_trades_per_day (int): Max trades per day, default 20
    """
    ema_fast_period = parameters.get("ema_fast", 3)
    ema_slow_period = parameters.get("ema_slow", 8)
    rsi_period = parameters.get("rsi_period", 3)
    rsi_ob = parameters.get("rsi_overbought", 75)
    rsi_os = parameters.get("rsi_oversold", 25)
    stoch_k_period = parameters.get("stoch_k", 5)
    stoch_d_period = parameters.get("stoch_d", 3)
    stoch_ob = parameters.get("stoch_overbought", 80)
    stoch_os = parameters.get("stoch_oversold", 20)
    atr_stop_mult = parameters.get("atr_stop_multiplier", 1.5)
    tp_ratio = parameters.get("take_profit_ratio", 1.5)
    initial_capital = parameters["initial_capital"]
    allocation = parameters.get("allocation", 0.05)
    fee_rate = parameters.get("fee_bps", 5) / 10_000
    slippage_rate = parameters.get("slippage_bps", 2) / 10_000
    interval = parameters.get("interval", "5m")
    max_trades_per_day = parameters.get("max_trades_per_day", 20)

    if len(candles) < max(ema_slow_period, stoch_k_period, 14) + 10:
        raise ValueError("Pas assez de candles pour le scalping (min ~25).")

    closes = [c["close"] for c in candles]
    ema_fast_vals = ema_series(closes, ema_fast_period)
    ema_slow_vals = ema_series(closes, ema_slow_period)
    rsi_vals = rsi_series(closes, rsi_period)
    k_vals, d_vals = stochastic(candles, stoch_k_period, stoch_d_period)

    atr_vals = atr_series(candles, 14)

    cash = initial_capital
    quantity = 0.0
    entry_price = 0.0
    stop_loss = 0.0
    take_profit = 0.0
    trades: list[dict] = []
    equity_curve: list[float] = []
    returns: list[float] = []
    trades_today = 0
    current_day = ""
    # Bar the position was filled on: stops may not trigger before it.
    fill_idx = -1

    for index, candle in enumerate(candles):
        close = candle["close"]
        candle_day = str(candle.get("close_time", ""))[:10]
        if candle_day != current_day:
            current_day = candle_day
            trades_today = 0

        if index < max(ema_slow_period, stoch_k_period, 14):
            equity_curve.append(cash)
            continue

        fast_cross_up = (ema_fast_vals[index] > ema_slow_vals[index] and
                         ema_fast_vals[index - 1] <= ema_slow_vals[index - 1])
        fast_cross_down = (ema_fast_vals[index] < ema_slow_vals[index] and
                           ema_fast_vals[index - 1] >= ema_slow_vals[index - 1])

        rsi_bullish = rsi_vals[index] < rsi_os or (rsi_vals[index] > 30 and rsi_vals[index] < 50)
        rsi_bearish = rsi_vals[index] > rsi_ob or (rsi_vals[index] < 70 and rsi_vals[index] > 50)
        stoch_bullish = k_vals[index] > stoch_os and k_vals[index] > d_vals[index]
        stoch_bearish = k_vals[index] < stoch_ob and k_vals[index] < d_vals[index]

        atr_val = atr_vals[index] if atr_vals[index] > 0 else close * 0.005

        # --- Exits: intrabar levels are only checked from the bar AFTER the
        # fill, and a signal exit is filled at the next bar's open. ---
        if quantity > 0 and index > fill_idx:
            hit = intrabar_exit_price(candle, "buy", stop_loss, take_profit)
            if hit is not None:
                # Intrabar trigger: the levels were armed before this bar.
                execution_price, reason, sig_idx, fill_i = hit[0], hit[1], index - 1, index
            elif fast_cross_down and stoch_bearish:
                # Signal decided on this bar -> filled at the next bar's open.
                execution_price = fill_price(candles, index, "sell", slippage_rate)
                reason, sig_idx, fill_i = "signal", index, index + 1
            else:
                execution_price = None
                reason, sig_idx, fill_i = None, index, index
            if execution_price is not None:
                proceeds = quantity * execution_price
                fee = proceeds * fee_rate
                cash += proceeds - fee
                pnl = (execution_price - entry_price) / entry_price
                trades.append({
                    "side": "sell", "price": execution_price,
                    "time": candles[fill_i]["close_time"], "fee": fee,
                    "pnl_pct": round(pnl * 100, 3),
                    "exit_reason": reason,
                    "signal_index": sig_idx, "fill_index": fill_i,
                })
                quantity = 0.0

        # --- Entry: decided on this bar, filled at the NEXT bar's open. ---
        if quantity == 0 and trades_today < max_trades_per_day:
            if fast_cross_up and rsi_bullish and stoch_bullish:
                execution_price = fill_price(candles, index, "buy", slippage_rate)
                if execution_price is not None:
                    order_value = cash * allocation
                    fee = order_value * fee_rate
                    quantity = (order_value - fee) / execution_price
                    cash -= order_value
                    entry_price = execution_price
                    stop_loss = entry_price - atr_stop_mult * atr_val
                    take_profit = entry_price + atr_stop_mult * tp_ratio * atr_val
                    fill_idx = index + 1
                    trades.append({
                        "side": "buy", "price": execution_price,
                        "time": candles[index + 1]["close_time"], "fee": fee,
                        "stop_loss": round(stop_loss, 2),
                        "take_profit": round(take_profit, 2),
                        "signal_index": index, "fill_index": index + 1,
                    })
                    trades_today += 1

        equity = cash + quantity * close
        if equity_curve:
            returns.append(equity / equity_curve[-1] - 1)
        equity_curve.append(equity)

    if not equity_curve:
        raise ValueError("Pas de données suffisantes pour calculer les résultats.")

    final_equity = equity_curve[-1]
    drawdown = max_drawdown(equity_curve)
    assert_no_lookahead(trades, candles)
    if trades_out is not None:
        trades_out.extend(trades)

    completed = list(zip(trades[::2], trades[1::2]))
    wins = sum(1 for buy, sell in completed if sell["price"] > buy["price"])
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
            fmean([s["price"] / b["price"] - 1 for b, s in completed]), 6
        ) if completed else 0.0,
        "trade_returns": [s["price"] / b["price"] - 1 for b, s in completed],
        "strategy": "scalping",
        "parameters_used": {
            "ema_fast": ema_fast_period, "ema_slow": ema_slow_period,
            "rsi_period": rsi_period, "atr_stop_multiplier": atr_stop_mult,
            "take_profit_ratio": tp_ratio,
        },
    }
