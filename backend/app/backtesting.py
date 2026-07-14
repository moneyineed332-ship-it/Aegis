"""Deterministic, long-only SMA crossover backtesting for paper research."""

import math
from statistics import fmean, stdev


def run_sma_crossover(candles: list[dict], parameters: dict) -> dict:
    fast_period = parameters["fast_period"]
    slow_period = parameters["slow_period"]
    initial_capital = parameters["initial_capital"]
    allocation = parameters["allocation"]
    fee_rate = parameters["fee_bps"] / 10_000
    slippage_rate = parameters["slippage_bps"] / 10_000
    if len(candles) <= slow_period:
        raise ValueError("Not enough candles for the requested slow moving average.")

    cash = initial_capital
    quantity = 0.0
    entry_value = 0.0
    trades: list[dict] = []
    equity_curve: list[float] = []
    returns: list[float] = []

    for index, candle in enumerate(candles):
        close = candle["close"]
        if index >= slow_period:
            fast_average = fmean(item["close"] for item in candles[index - fast_period:index])
            slow_average = fmean(item["close"] for item in candles[index - slow_period:index])
            should_hold = fast_average > slow_average
            if should_hold and quantity == 0:
                order_value = cash * allocation
                execution_price = close * (1 + slippage_rate)
                fee = order_value * fee_rate
                quantity = (order_value - fee) / execution_price
                cash -= order_value
                entry_value = order_value
                trades.append({"side": "buy", "price": execution_price, "time": candle["close_time"], "fee": fee})
            elif not should_hold and quantity > 0:
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
    high_water_mark = equity_curve[0]
    max_drawdown = 0.0
    for equity in equity_curve:
        high_water_mark = max(high_water_mark, equity)
        max_drawdown = min(max_drawdown, equity / high_water_mark - 1)

    completed_trades = list(zip(trades[::2], trades[1::2]))
    wins = sum(1 for buy, sell in completed_trades if sell["price"] > buy["price"])
    periods_per_year = {"5m": 105_120, "15m": 35_040, "1h": 8_760, "4h": 2_190}[parameters["interval"]]
    sharpe = 0.0
    if len(returns) > 1 and stdev(returns) > 0:
        sharpe = fmean(returns) / stdev(returns) * math.sqrt(periods_per_year)

    return {
        "final_equity": round(final_equity, 2),
        "total_return": round(final_equity / initial_capital - 1, 6),
        "max_drawdown": round(max_drawdown, 6),
        "sharpe_ratio": round(sharpe, 4),
        "trade_count": len(completed_trades),
        "win_rate": round(wins / len(completed_trades), 6) if completed_trades else 0.0,
    }


def run_walk_forward(candles: list[dict], base_parameters: dict, candidates: list[tuple[int, int]]) -> dict:
    train_size = base_parameters["train_candles"]
    test_size = base_parameters["test_candles"]
    if len(candles) < train_size + test_size:
        raise ValueError("Not enough stored candles for the requested walk-forward split.")
    selected = candles[-(train_size + test_size):]
    train_candles = selected[:train_size]
    test_candles = selected[train_size:]
    evaluations = []
    for fast_period, slow_period in candidates:
        metrics = run_sma_crossover(train_candles, {**base_parameters, "fast_period": fast_period, "slow_period": slow_period})
        evaluations.append({"fast_period": fast_period, "slow_period": slow_period, "train_metrics": metrics})
    winner = max(evaluations, key=lambda item: item["train_metrics"]["sharpe_ratio"])
    out_of_sample = run_sma_crossover(test_candles, {**base_parameters, "fast_period": winner["fast_period"], "slow_period": winner["slow_period"]})
    return {"selected_parameters": {"fast_period": winner["fast_period"], "slow_period": winner["slow_period"]}, "train_metrics": winner["train_metrics"], "out_of_sample_metrics": out_of_sample, "candidates": evaluations}


def run_donchian_breakout(candles: list[dict], parameters: dict) -> dict:
    breakout_period = parameters["breakout_period"]
    exit_period = parameters["exit_period"]
    initial_capital = parameters["initial_capital"]
    allocation = parameters["allocation"]
    fee_rate = parameters["fee_bps"] / 10_000
    slippage_rate = parameters["slippage_bps"] / 10_000
    if len(candles) <= breakout_period:
        raise ValueError("Not enough candles for the requested Donchian period.")
    cash, quantity, entry_price = initial_capital, 0.0, 0.0
    trades, equity_curve, returns = [], [], []
    for index, candle in enumerate(candles):
        close = candle["close"]
        if index >= breakout_period:
            previous = candles[index - breakout_period:index]
            channel_high = max(item["high"] for item in previous)
            channel_low = min(item["low"] for item in candles[index - exit_period:index])
            volatility = (channel_high - channel_low) / close
            if quantity == 0 and close > channel_high and volatility >= parameters["min_volatility"]:
                order_value = cash * allocation
                entry_price = close * (1 + slippage_rate)
                fee = order_value * fee_rate
                quantity = (order_value - fee) / entry_price
                cash -= order_value
                trades.append({"side": "buy", "price": entry_price, "time": candle["close_time"], "fee": fee})
            elif quantity > 0 and close < channel_low:
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
    peak, max_drawdown = equity_curve[0], 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1)
    completed = list(zip(trades[::2], trades[1::2]))
    wins = sum(1 for buy, sell in completed if sell["price"] > buy["price"])
    periods_per_year = {"5m": 105_120, "15m": 35_040, "1h": 8_760, "4h": 2_190}[parameters["interval"]]
    sharpe = fmean(returns) / stdev(returns) * math.sqrt(periods_per_year) if len(returns) > 1 and stdev(returns) > 0 else 0.0
    return {"final_equity": round(final_equity, 2), "total_return": round(final_equity / initial_capital - 1, 6), "max_drawdown": round(max_drawdown, 6), "sharpe_ratio": round(sharpe, 4), "trade_count": len(completed), "win_rate": round(wins / len(completed), 6) if completed else 0.0}


def run_donchian_walk_forward(candles: list[dict], base_parameters: dict, candidates: list[tuple[int, int]]) -> dict:
    train_size, test_size = base_parameters["train_candles"], base_parameters["test_candles"]
    if len(candles) < train_size + test_size:
        raise ValueError("Not enough stored candles for the requested walk-forward split.")
    train, test = candles[-(train_size + test_size):-test_size], candles[-test_size:]
    evaluations = []
    for breakout_period, exit_period in candidates:
        metrics = run_donchian_breakout(train, {**base_parameters, "breakout_period": breakout_period, "exit_period": exit_period})
        evaluations.append({"breakout_period": breakout_period, "exit_period": exit_period, "train_metrics": metrics})
    winner = max(evaluations, key=lambda item: item["train_metrics"]["sharpe_ratio"])
    out_of_sample = run_donchian_breakout(test, {**base_parameters, **winner})
    return {"selected_parameters": {"breakout_period": winner["breakout_period"], "exit_period": winner["exit_period"]}, "train_metrics": winner["train_metrics"], "out_of_sample_metrics": out_of_sample, "candidates": evaluations}
