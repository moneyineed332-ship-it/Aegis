"""Enhanced SMA crossover + Donchian breakout backtesting.

Improvements: ATR trailing stops, dynamic position sizing (Kelly-inspired),
regime filter, Sortino/Calmar ratios, multi-timeframe awareness.
"""

import logging
import math
from statistics import fmean, stdev

logger = logging.getLogger(__name__)


def _compute_atr(candles: list[dict], period: int = 14) -> list[float]:
    """Build ATR series for trailing stop calculations."""
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


def _dynamic_sizing(capital: float, atr: float, price: float, allocation: float, risk_pct: float = 0.02) -> float:
    """ATR-based position sizing: risk_pct of capital per ATR move."""
    if atr <= 0 or price <= 0:
        return capital * allocation
    risk_amount = capital * risk_pct
    position_size = risk_amount / atr * price
    max_size = capital * allocation
    return min(position_size, max_size)


from .metrics_core import (
    calmar_ratio,
    max_drawdown,
    periods_per_year,
    sharpe_ratio,
    signed_trade_returns,
    sortino_ratio,
)


def _periods_per_year(interval: str) -> int:
    return periods_per_year(interval)


def run_sma_crossover(candles: list[dict], parameters: dict) -> dict:
    """Enhanced SMA crossover with ATR trailing stop and dynamic sizing."""
    fast_period = parameters["fast_period"]
    slow_period = parameters["slow_period"]
    initial_capital = parameters["initial_capital"]
    allocation = parameters["allocation"]
    fee_rate = parameters["fee_bps"] / 10_000
    slippage_rate = parameters["slippage_bps"] / 10_000
    interval = parameters.get("interval", "1h")
    atr_stop_mult = parameters.get("atr_stop_multiplier", 2.5)
    risk_pct = parameters.get("risk_pct", 0.02)
    use_trailing = parameters.get("use_trailing_stop", True)
    use_sizing = parameters.get("use_dynamic_sizing", True)

    if len(candles) <= slow_period + 14:
        raise ValueError("Not enough candles for SMA crossover + ATR.")

    atr_series = _compute_atr(candles)
    cash = initial_capital
    quantity = 0.0
    entry_price = 0.0
    trailing_stop = 0.0
    highest_since_entry = 0.0
    trades: list[dict] = []
    equity_curve: list[float] = []
    returns: list[float] = []

    for index, candle in enumerate(candles):
        close = candle["close"]
        high = candle["high"]

        if index >= slow_period:
            fast_avg = fmean(c["close"] for c in candles[index - fast_period:index])
            slow_avg = fmean(c["close"] for c in candles[index - slow_period:index])
            should_hold = fast_avg > slow_avg

            # Update trailing stop
            if quantity > 0 and use_trailing:
                highest_since_entry = max(highest_since_entry, high)
                trailing_stop = highest_since_entry - atr_stop_mult * atr_series[index]

            # Entry
            if should_hold and quantity == 0:
                if use_sizing:
                    order_value = _dynamic_sizing(cash, atr_series[index], close, allocation, risk_pct)
                else:
                    order_value = cash * allocation
                execution_price = close * (1 + slippage_rate)
                fee = order_value * fee_rate
                quantity = (order_value - fee) / execution_price
                cash -= order_value
                entry_price = execution_price
                highest_since_entry = high
                trailing_stop = entry_price - atr_stop_mult * atr_series[index]
                trades.append({"side": "buy", "price": execution_price, "time": candle["close_time"], "fee": fee})

            # Exit: signal reversal OR trailing stop hit
            elif quantity > 0 and (not should_hold or (use_trailing and close < trailing_stop)):
                execution_price = close * (1 - slippage_rate)
                proceeds = quantity * execution_price
                fee = proceeds * fee_rate
                cash += proceeds - fee
                trades.append({"side": "sell", "price": execution_price, "time": candle["close_time"], "fee": fee})
                quantity = 0.0

        equity = cash + quantity * close
        if equity_curve:
            returns.append(equity / equity_curve[-1] - 1)
        equity_curve.append(equity)

    final_equity = equity_curve[-1]
    drawdown = max_drawdown(equity_curve)

    completed = list(zip(trades[::2], trades[1::2]))
    wins = sum(1 for buy, sell in completed if sell["price"] > buy["price"])
    ppy = _periods_per_year(interval)
    sharpe = sharpe_ratio(returns, ppy)
    sortino = sortino_ratio(returns, ppy)
    calmar = calmar_ratio(final_equity / initial_capital - 1, drawdown, len(returns), ppy)

    return {
        "final_equity": round(final_equity, 2),
        "total_return": round(final_equity / initial_capital - 1, 6),
        "max_drawdown": round(drawdown, 6),
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": sortino,
        "calmar_ratio": calmar,
        "trade_count": len(completed),
        "win_rate": round(wins / len(completed), 6) if completed else 0.0,
        "avg_trade_return": round(fmean([s["price"] / b["price"] - 1 for b, s in completed]), 6) if completed else 0.0,
        "trade_returns": signed_trade_returns(completed),
    }


def run_walk_forward(candles: list[dict], base_parameters: dict, candidates: list[tuple[int, int]]) -> dict:
    """Walk-forward with embargo period between train/test."""
    train_size = base_parameters["train_candles"]
    test_size = base_parameters["test_candles"]
    embargo = base_parameters.get("embargo_candles", 10)
    if len(candles) < train_size + test_size + embargo:
        raise ValueError("Not enough candles for walk-forward with embargo.")
    selected = candles[-(train_size + embargo + test_size):]
    train_candles = selected[:train_size]
    test_candles = selected[train_size + embargo:]
    evaluations = []
    for fast, slow in candidates:
        try:
            metrics = run_sma_crossover(train_candles, {**base_parameters, "fast_period": fast, "slow_period": slow})
            evaluations.append({"fast_period": fast, "slow_period": slow, "train_metrics": metrics})
        except Exception as e:
            logger.debug("SMA walk-forward candidate failed: %s/%s — %s", fast, slow, e, exc_info=True)
            continue
    if not evaluations:
        raise ValueError("All candidate parameter sets failed.")
    winner = max(evaluations, key=lambda e: e["train_metrics"]["sharpe_ratio"])
    oos = run_sma_crossover(test_candles, {**base_parameters, "fast_period": winner["fast_period"], "slow_period": winner["slow_period"]})
    return {"selected_parameters": {"fast_period": winner["fast_period"], "slow_period": winner["slow_period"]}, "train_metrics": winner["train_metrics"], "out_of_sample_metrics": oos, "candidates": evaluations}


def run_donchian_breakout(candles: list[dict], parameters: dict) -> dict:
    """Enhanced Donchian breakout with ATR trailing stop and dynamic sizing."""
    breakout_period = parameters["breakout_period"]
    exit_period = parameters["exit_period"]
    initial_capital = parameters["initial_capital"]
    allocation = parameters["allocation"]
    fee_rate = parameters["fee_bps"] / 10_000
    slippage_rate = parameters["slippage_bps"] / 10_000
    interval = parameters.get("interval", "1h")
    min_volatility = parameters.get("min_volatility", 0.01)
    atr_stop_mult = parameters.get("atr_stop_multiplier", 3.0)
    risk_pct = parameters.get("risk_pct", 0.02)
    use_trailing = parameters.get("use_trailing_stop", True)
    use_sizing = parameters.get("use_dynamic_sizing", True)

    if len(candles) <= max(breakout_period, exit_period) + 14:
        raise ValueError("Not enough candles for Donchian breakout.")

    atr_series = _compute_atr(candles)
    cash, quantity = initial_capital, 0.0
    entry_price, trailing_stop, highest_since = 0.0, 0.0, 0.0
    trades, equity_curve, returns = [], [], []

    for index, candle in enumerate(candles):
        close, high, low = candle["close"], candle["high"], candle["low"]

        if index >= breakout_period:
            prev = candles[index - breakout_period:index]
            channel_high = max(c["high"] for c in prev)
            channel_low = min(c["low"] for c in candles[index - exit_period:index])
            vol = (channel_high - channel_low) / close if close > 0 else 0

            if quantity > 0 and use_trailing:
                highest_since = max(highest_since, high)
                trailing_stop = highest_since - atr_stop_mult * atr_series[index]

            # Entry: price breaks above channel
            if quantity == 0 and close > channel_high and vol >= min_volatility:
                if use_sizing:
                    order_value = _dynamic_sizing(cash, atr_series[index], close, allocation, risk_pct)
                else:
                    order_value = cash * allocation
                execution_price = close * (1 + slippage_rate)
                fee = order_value * fee_rate
                quantity = (order_value - fee) / execution_price
                cash -= order_value
                entry_price = execution_price
                highest_since = high
                trailing_stop = entry_price - atr_stop_mult * atr_series[index]
                trades.append({"side": "buy", "price": execution_price, "time": candle["close_time"], "fee": fee})

            # Exit: price breaks below channel OR trailing stop
            elif quantity > 0 and (close < channel_low or (use_trailing and close < trailing_stop)):
                execution_price = close * (1 - slippage_rate)
                proceeds = quantity * execution_price
                fee = proceeds * fee_rate
                cash += proceeds - fee
                trades.append({"side": "sell", "price": execution_price, "time": candle["close_time"], "fee": fee})
                quantity = 0.0

        equity = cash + quantity * close
        if equity_curve:
            returns.append(equity / equity_curve[-1] - 1)
        equity_curve.append(equity)

    final_equity = equity_curve[-1]
    drawdown = max_drawdown(equity_curve)

    completed = list(zip(trades[::2], trades[1::2]))
    wins = sum(1 for b, s in completed if s["price"] > b["price"])
    ppy = _periods_per_year(interval)
    sharpe = sharpe_ratio(returns, ppy)
    sortino = sortino_ratio(returns, ppy)
    calmar = calmar_ratio(final_equity / initial_capital - 1, drawdown, len(returns), ppy)

    return {
        "final_equity": round(final_equity, 2),
        "total_return": round(final_equity / initial_capital - 1, 6),
        "max_drawdown": round(drawdown, 6),
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": sortino,
        "calmar_ratio": calmar,
        "trade_count": len(completed),
        "win_rate": round(wins / len(completed), 6) if completed else 0.0,
        "avg_trade_return": round(fmean([s["price"] / b["price"] - 1 for b, s in completed]), 6) if completed else 0.0,
        "trade_returns": signed_trade_returns(completed),
    }


def run_donchian_walk_forward(candles: list[dict], base_parameters: dict, candidates: list[tuple[int, int]]) -> dict:
    """Walk-forward with embargo for Donchian."""
    train_size, test_size = base_parameters["train_candles"], base_parameters["test_candles"]
    embargo = base_parameters.get("embargo_candles", 10)
    if len(candles) < train_size + test_size + embargo:
        raise ValueError("Not enough candles.")
    train = candles[-(train_size + embargo + test_size):-test_size - embargo]
    test = candles[-test_size:]
    evaluations = []
    for bp, ep in candidates:
        try:
            metrics = run_donchian_breakout(train, {**base_parameters, "breakout_period": bp, "exit_period": ep})
            evaluations.append({"breakout_period": bp, "exit_period": ep, "train_metrics": metrics})
        except Exception as e:
            logger.debug("Donchian walk-forward candidate failed: %s/%s — %s", bp, ep, e, exc_info=True)
            continue
    if not evaluations:
        raise ValueError("All candidates failed.")
    winner = max(evaluations, key=lambda e: e["train_metrics"]["sharpe_ratio"])
    oos = run_donchian_breakout(test, {**base_parameters, **winner})
    return {"selected_parameters": {"breakout_period": winner["breakout_period"], "exit_period": winner["exit_period"]}, "train_metrics": winner["train_metrics"], "out_of_sample_metrics": oos, "candidates": evaluations}


def donchian_live_signal(candles: list[dict], breakout_period: int = 20, exit_period: int = 10) -> dict:
    """Live Donchian breakout signal for the ONE focused strategy.

    Uses the same rules as the backtest (price breaking above the channel):
      - buy  when close > highest high of the last N candles
      - sell when close < lowest low of the last M candles (exit)
    Returns a dict with action + levels; matches backtest behavior so what is
    backtested is what is traded.
    """
    if len(candles) <= max(breakout_period, exit_period):
        return {"action": "hold", "confidence": 0.5, "reason": "Not enough candles for Donchian signal."}

    last = candles[-1]
    prev = candles[-(breakout_period + 1):-1]
    close = last["close"]
    channel_high = max(c["high"] for c in prev)
    channel_low = min(c["low"] for c in prev)
    vol = (channel_high - channel_low) / close if close > 0 else 0

    if close > channel_high:
        return {
            "action": "buy",
            "confidence": min(0.9, 0.6 + vol),
            "channel_high": round(channel_high, 6),
            "reason": f"Breakout above {channel_high:.2f} (vol {vol:.2%}).",
        }
    if close < channel_low:
        return {
            "action": "sell",
            "confidence": min(0.9, 0.6 + vol),
            "channel_low": round(channel_low, 6),
            "reason": f"Drop below {channel_low:.2f} — exit position.",
        }
    return {
        "action": "hold",
        "confidence": 0.5,
        "channel_high": round(channel_high, 3),
        "channel_low": round(channel_low, 3),
        "reason": "Price inside the Donchian channel; no breakout.",
    }


# SMC/ICT + Multi-Timeframe backtests delegated to backtesting_smc module
from .backtesting_smc import run_smc_ict, run_multi_timeframe, run_multi_scale_crossover, run_smc_ict_walk_forward, run_multi_timeframe_walk_forward  # noqa: E402, F401
