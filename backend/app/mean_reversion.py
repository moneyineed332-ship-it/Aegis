"""Mean-reversion backtesting using Bollinger Bands z-score for paper research."""

import math
from statistics import fmean, stdev


def _bollinger_series(closes: list[float], period: int) -> list[tuple[float, float]]:
    """Return list of (lower_band, upper_band) for each index where full window exists."""
    bands = []
    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1 : i + 1]
        mid = fmean(window)
        std = math.sqrt(fmean((x - mid) ** 2 for x in window))
        bands.append((mid - 2 * std, mid + 2 * std))
    return bands


def run_mean_reversion(candles: list[dict], parameters: dict) -> dict:
    """Long-only mean reversion: buy when price < lower Bollinger, sell at SMA."""
    period = parameters["period"]
    entry_z = parameters["entry_z_score"]
    exit_z = parameters["exit_z_score"]
    initial_capital = parameters["initial_capital"]
    allocation = parameters["allocation"]
    fee_rate = parameters["fee_bps"] / 10_000
    slippage_rate = parameters["slippage_bps"] / 10_000

    if len(candles) <= period:
        raise ValueError("Not enough candles for the requested Bollinger period.")

    closes = [c["close"] for c in candles]
    bands = _bollinger_series(closes, period)

    cash = initial_capital
    quantity = 0.0
    trades: list[dict] = []
    equity_curve: list[float] = []
    returns: list[float] = []

    for offset, (lower_band, upper_band) in enumerate(bands):
        index = offset + period - 1
        close = closes[index]
        mid = (lower_band + upper_band) / 2  # SMA ≈ middle band
        std = (upper_band - lower_band) / 4

        if std == 0:
            z_score = 0
        else:
            z_score = (close - mid) / std

        if quantity == 0 and z_score <= entry_z:
            # Price below lower band — buy
            order_value = cash * allocation
            execution_price = close * (1 + slippage_rate)
            fee = order_value * fee_rate
            quantity = (order_value - fee) / execution_price
            cash -= order_value
            trades.append({"side": "buy", "price": execution_price, "time": candles[index]["close_time"], "fee": fee, "z_score": z_score})

        elif quantity > 0 and z_score >= exit_z:
            # Price back to SMA — sell
            execution_price = close * (1 - slippage_rate)
            proceeds = quantity * execution_price
            fee = proceeds * fee_rate
            cash += proceeds - fee
            trades.append({"side": "sell", "price": execution_price, "time": candles[index]["close_time"], "fee": fee, "z_score": z_score})
            quantity = 0.0

        equity = cash + quantity * close
        if equity_curve:
            returns.append(equity / equity_curve[-1] - 1)
        equity_curve.append(equity)

    if not equity_curve:
        return {"final_equity": initial_capital, "total_return": 0, "max_drawdown": 0, "sharpe_ratio": 0, "trade_count": 0, "win_rate": 0}

    final_equity = equity_curve[-1]
    high_water_mark = equity_curve[0]
    max_drawdown = 0.0
    for eq in equity_curve:
        high_water_mark = max(high_water_mark, eq)
        max_drawdown = min(max_drawdown, eq / high_water_mark - 1)

    completed_trades = list(zip(trades[::2], trades[1::2]))
    wins = sum(1 for buy, sell in completed_trades if sell["price"] > buy["price"])
    periods_per_year = {"5m": 105_120, "15m": 35_040, "1h": 8_760, "4h": 2_190}.get(parameters["interval"], 8_760)
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


def run_mean_reversion_walk_forward(candles: list[dict], base_parameters: dict, candidates: list[tuple[float, float]]) -> dict:
    """Walk-forward optimization for mean reversion (entry_z, exit_z)."""
    train_size = base_parameters["train_candles"]
    test_size = base_parameters["test_candles"]
    if len(candles) < train_size + test_size:
        raise ValueError("Not enough stored candles for the requested walk-forward split.")
    selected = candles[-(train_size + test_size):]
    train_candles = selected[:train_size]
    test_candles = selected[train_size:]
    evaluations = []
    for entry_z, exit_z in candidates:
        metrics = run_mean_reversion(
            train_candles,
            {**base_parameters, "entry_z_score": entry_z, "exit_z_score": exit_z},
        )
        evaluations.append({"entry_z_score": entry_z, "exit_z_score": exit_z, "train_metrics": metrics})
    winner = max(evaluations, key=lambda item: item["train_metrics"]["sharpe_ratio"])
    out_of_sample = run_mean_reversion(
        test_candles,
        {**base_parameters, "entry_z_score": winner["entry_z_score"], "exit_z_score": winner["exit_z_score"]},
    )
    return {
        "selected_parameters": {"entry_z_score": winner["entry_z_score"], "exit_z_score": winner["exit_z_score"]},
        "train_metrics": winner["train_metrics"],
        "out_of_sample_metrics": out_of_sample,
        "candidates": evaluations,
    }
